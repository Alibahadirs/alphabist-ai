from calendar import monthrange
from datetime import date, datetime

import pytest

from app.audit.models import (
    CompanyDataAudit,
    DataSourceType,
    MetricSourceType,
)
from app.core.settings import settings
from app.database import repository
from app.portfolio.models import PortfolioMarketPrice, PortfolioPosition
from app.portfolio.service import build_portfolio_summary
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile
from app.technical.models import TechnicalHistoryEntry
from app.validation.service import PROFILE_REQUIREMENTS


def _company(
    symbol: str = "TEST",
    profile: CompanyProfile = CompanyProfile.STANDARD,
) -> FinancialMetrics:
    return FinancialMetrics(
        symbol=symbol,
        company_name=f"{symbol} Test Şirketi",
        company_profile=profile,
        revenue_growth=20,
        net_profit_growth=25,
        net_margin=15,
        roe=25,
        debt_to_equity=0.5,
        current_ratio=1.8,
        operating_cash_flow=100,
        free_cash_flow=50,
        asset_turnover=0.8,
        valuation_score_input=75,
        management_score_input=80,
        risk_score_input=70,
    )


def _verified_audit(symbol: str) -> CompanyDataAudit:
    today = date.today()
    quarter_ends = [
        date(today.year - 1, 12, 31),
        *[
            date(today.year, month, monthrange(today.year, month)[1])
            for month in (3, 6, 9, 12)
        ],
    ]
    report_period_end = max(
        value for value in quarter_ends if value <= today
    )
    required = PROFILE_REQUIREMENTS[CompanyProfile.STANDARD]
    return CompanyDataAudit(
        symbol=symbol,
        source_type=DataSourceType.PDF,
        company_profile=CompanyProfile.STANDARD,
        period_months=report_period_end.month,
        report_period_end=report_period_end,
        financial_report_name=f"{symbol}.pdf",
        financial_report_hash="a" * 64,
        comparison_period_end=report_period_end.replace(
            year=report_period_end.year - 1
        ),
        comparison_period_confirmed=True,
        completeness=100,
        alpha_score=80,
        methodology_version=settings.scoring_methodology_version,
        field_sources={
            field: MetricSourceType.FINANCIAL_REPORT
            for field in required
        },
    )


def test_portfolio_repository_adds_updates_and_removes(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.upsert_company(_company())

    repository.upsert_portfolio_position(
        PortfolioPosition(symbol="test", quantity=10, average_cost=20)
    )
    repository.upsert_portfolio_position(
        PortfolioPosition(symbol="TEST", quantity=12, average_cost=22)
    )

    positions = repository.list_portfolio_positions()
    assert positions == [
        PortfolioPosition(symbol="TEST", quantity=12, average_cost=22)
    ]

    repository.remove_portfolio_position("test")
    assert repository.list_portfolio_positions() == []


def test_portfolio_summary_calculates_return_and_weighted_alpha():
    company = _company()
    summary = build_portfolio_summary(
        [PortfolioPosition(symbol="TEST", quantity=10, average_cost=20)],
        {"TEST": company},
        {"TEST": 25},
    )

    assert summary.total_cost == 200
    assert summary.total_market_value == 250
    assert summary.total_profit_loss == 50
    assert summary.total_return_percent == pytest.approx(25)
    assert summary.weighted_alpha_score == pytest.approx(
        summary.rows[0].alpha_score
    )
    assert summary.weighted_confidence_score is None
    assert summary.decision_ready_count == 1
    assert summary.verification_required_count == 0
    assert summary.decision_ready_value_percent == 100
    assert summary.combined_decision_ready_value_percent == 0
    assert summary.rows[0].combined_decision_ready is False
    assert summary.rows[0].weight_percent == 100
    assert summary.largest_position_symbol == "TEST"
    assert summary.largest_position_percent == 100
    assert summary.profile_exposure == {"standard": 100}
    assert summary.concentration_warnings
    assert summary.concentration_index == 100
    assert summary.effective_position_count == 1
    assert summary.diversification_status == "Yoğun"
    scenarios = {
        scenario.label: scenario
        for scenario in summary.stress_scenarios
    }
    assert set(scenarios) == {
        "%20 düşüş",
        "%10 düşüş",
        "%10 yükseliş",
        "En büyük pozisyon düşüşü",
        "En büyük profil düşüşü",
    }
    assert scenarios["%20 düşüş"].affected_scope == "Tüm portföy"
    assert scenarios["%20 düşüş"].projected_market_value == 200
    assert scenarios["%20 düşüş"].value_change == -50
    assert scenarios["%20 düşüş"].projected_profit_loss == 0
    assert scenarios["%20 düşüş"].projected_return_percent == 0
    assert scenarios["%10 düşüş"].projected_market_value == 225
    assert scenarios["%10 düşüş"].value_change == -25
    assert scenarios["%10 düşüş"].projected_profit_loss == 25
    assert scenarios["%10 düşüş"].projected_return_percent == 12.5
    assert scenarios["%10 yükseliş"].projected_market_value == 275
    assert scenarios["%10 yükseliş"].value_change == 25
    assert scenarios["%10 yükseliş"].projected_profit_loss == 75
    assert scenarios["%10 yükseliş"].projected_return_percent == 37.5


def test_portfolio_stress_return_handles_zero_cost():
    company = _company()
    summary = build_portfolio_summary(
        [PortfolioPosition(symbol="TEST", quantity=10, average_cost=0)],
        {"TEST": company},
        {"TEST": 25},
    )

    assert summary.total_cost == 0
    assert all(
        scenario.projected_return_percent == 0
        for scenario in summary.stress_scenarios
    )


def test_portfolio_exposes_unverified_position_value_and_confidence():
    company = _company()
    summary = build_portfolio_summary(
        [PortfolioPosition(symbol="TEST", quantity=10, average_cost=20)],
        {"TEST": company},
        {"TEST": 25},
        {},
    )

    row = summary.rows[0]
    assert row.confidence_score == 60
    assert row.confidence_status == "Düşük"
    assert row.decision == "Doğrula / Karar verme"
    assert row.decision_ready is False
    assert summary.weighted_confidence_score == 60
    assert summary.decision_ready_count == 0
    assert summary.verification_required_count == 1
    assert summary.decision_ready_value_percent == 0
    assert summary.combined_decision_ready_value_percent == 0


def test_portfolio_calculates_position_and_profile_concentration():
    standard = _company("STND", CompanyProfile.STANDARD)
    bank = _company("BANK", CompanyProfile.BANK)
    summary = build_portfolio_summary(
        [
            PortfolioPosition(
                symbol="STND", quantity=1, average_cost=70
            ),
            PortfolioPosition(
                symbol="BANK", quantity=1, average_cost=30
            ),
        ],
        {"STND": standard, "BANK": bank},
        {"STND": 70, "BANK": 30},
    )

    rows = {row.symbol: row for row in summary.rows}
    assert rows["STND"].weight_percent == 70
    assert rows["BANK"].weight_percent == 30
    assert summary.largest_position_symbol == "STND"
    assert summary.largest_position_percent == 70
    assert summary.profile_exposure == {
        "standard": 70,
        "bank": 30,
    }
    assert any("STND" in warning for warning in summary.concentration_warnings)
    assert any(
        "standard" in warning
        for warning in summary.concentration_warnings
    )
    assert summary.concentration_index == pytest.approx(58)
    assert summary.effective_position_count == pytest.approx(1.72)
    assert summary.diversification_status == "Yoğun"
    scenarios = {
        scenario.label: scenario
        for scenario in summary.stress_scenarios
    }
    position_stress = scenarios["En büyük pozisyon düşüşü"]
    assert position_stress.affected_scope == "STND"
    assert position_stress.shock_percent == -25
    assert position_stress.projected_market_value == 82.5
    assert position_stress.value_change == -17.5
    assert position_stress.projected_profit_loss == -17.5
    assert position_stress.projected_return_percent == -17.5
    profile_stress = scenarios["En büyük profil düşüşü"]
    assert profile_stress.affected_scope == "standard profili"
    assert profile_stress.shock_percent == -15
    assert profile_stress.projected_market_value == 89.5
    assert profile_stress.value_change == -10.5
    assert profile_stress.projected_profit_loss == -10.5
    assert profile_stress.projected_return_percent == -10.5


def test_equal_weight_portfolio_is_classified_as_diversified():
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    companies = {
        symbol: _company(symbol) for symbol in symbols
    }
    positions = [
        PortfolioPosition(
            symbol=symbol,
            quantity=1,
            average_cost=20,
        )
        for symbol in symbols
    ]

    summary = build_portfolio_summary(
        positions,
        companies,
        {symbol: 20 for symbol in symbols},
    )

    assert summary.concentration_index == pytest.approx(20)
    assert summary.effective_position_count == pytest.approx(5)
    assert summary.diversification_status == "Dengeli"


def test_portfolio_marks_current_and_stale_market_prices():
    companies = {
        "FRESH": _company("FRESH"),
        "STALE": _company("STALE"),
    }
    summary = build_portfolio_summary(
        [
            PortfolioPosition(
                symbol="FRESH", quantity=1, average_cost=20
            ),
            PortfolioPosition(
                symbol="STALE", quantity=1, average_cost=20
            ),
        ],
        companies,
        {
            "FRESH": PortfolioMarketPrice(
                value=25,
                as_of_date=date(2026, 7, 17),
                source="Yahoo Finance",
            ),
            "STALE": PortfolioMarketPrice(
                value=22,
                as_of_date=date(2026, 7, 1),
                source="Yahoo Finance",
            ),
        },
        reference_date=date(2026, 7, 18),
    )

    rows = {row.symbol: row for row in summary.rows}
    assert rows["FRESH"].price_current is True
    assert rows["FRESH"].price_age_days == 1
    assert rows["FRESH"].price_status == "Güncel günlük veri"
    assert rows["STALE"].price_current is False
    assert rows["STALE"].price_age_days == 17
    assert rows["STALE"].price_status == "Eski fiyat"
    assert summary.current_price_count == 1
    assert summary.price_warning_count == 1
    assert summary.current_price_value_percent == pytest.approx(53.19)
    assert summary.stress_test_ready is False
    issues = {
        issue.symbol: issue
        for issue in summary.score_readiness_issues
    }
    assert issues["FRESH"].price_status == "Tamam"
    assert issues["FRESH"].technical_status == "Kayıt yok"
    assert issues["STALE"].price_status == "Eski fiyat"


def test_portfolio_stress_is_ready_with_sufficient_current_price_coverage():
    companies = {
        "FRESH": _company("FRESH"),
        "SMALL": _company("SMALL"),
    }
    summary = build_portfolio_summary(
        [
            PortfolioPosition(
                symbol="FRESH", quantity=9, average_cost=10
            ),
            PortfolioPosition(
                symbol="SMALL", quantity=1, average_cost=10
            ),
        ],
        companies,
        {
            "FRESH": PortfolioMarketPrice(
                value=10,
                as_of_date=date(2026, 7, 17),
                source="Yahoo Finance",
            ),
            "SMALL": PortfolioMarketPrice(
                value=10,
                as_of_date=date(2026, 7, 17),
                source="Yahoo Finance",
            ),
        },
        reference_date=date(2026, 7, 18),
    )

    assert summary.current_price_value_percent == 100
    assert summary.stress_test_ready is True


def _technical_history(
    symbol: str,
    identifier: int,
    score: float,
) -> TechnicalHistoryEntry:
    return TechnicalHistoryEntry(
        id=identifier,
        symbol=symbol,
        price_date=date(2026, 7, 17),
        source="Yahoo Finance",
        total_score=score,
        signal="Al",
        rsi_value=55,
        atr_percent=3,
        score_breakdown={},
        alignment_status="Fiyat ve grafik verisi uyumlu",
        methodology_version="technical-2026.1",
        created_at=datetime(2026, 7, 18, 10, identifier),
    )


def test_portfolio_builds_combined_score_from_verified_coverage():
    companies = {
        "AAA": _company("AAA"),
        "BBB": _company("BBB"),
    }
    summary = build_portfolio_summary(
        [
            PortfolioPosition(
                symbol="AAA", quantity=1, average_cost=25
            ),
            PortfolioPosition(
                symbol="BBB", quantity=3, average_cost=25
            ),
        ],
        companies,
        {
            "AAA": PortfolioMarketPrice(
                value=25,
                as_of_date=date(2026, 7, 17),
                source="Yahoo Finance",
            ),
            "BBB": PortfolioMarketPrice(
                value=25,
                as_of_date=date(2026, 7, 17),
                source="Yahoo Finance",
            ),
        },
        technical_histories={
            "AAA": [_technical_history("AAA", 1, 60)],
            "BBB": [_technical_history("BBB", 2, 80)],
        },
        reference_date=date(2026, 7, 18),
    )

    assert summary.current_price_value_percent == 100
    assert summary.current_technical_value_percent == 100
    assert summary.decision_ready_value_percent == 100
    assert summary.combined_decision_ready_value_percent == 100
    assert summary.combined_decision_ready_count == 2
    assert all(row.combined_decision_ready for row in summary.rows)
    assert all(row.combined_score is not None for row in summary.rows)
    assert summary.weighted_technical_score == 75
    assert summary.weighted_combined_score == pytest.approx(
        round(summary.weighted_alpha_score * 0.7 + 75 * 0.3, 2)
    )
    assert summary.portfolio_score_ready is True
    assert summary.score_readiness_issues == []


def test_portfolio_combined_coverage_uses_same_positions():
    companies = {
        symbol: _company(symbol)
        for symbol in ("FINON", "TECHON", "BOTH")
    }
    positions = [
        PortfolioPosition(
            symbol="FINON", quantity=1, average_cost=10
        ),
        PortfolioPosition(
            symbol="TECHON", quantity=1, average_cost=10
        ),
        PortfolioPosition(
            symbol="BOTH", quantity=8, average_cost=10
        ),
    ]
    prices = {
        position.symbol: PortfolioMarketPrice(
            value=10,
            as_of_date=date(2026, 7, 17),
            source="Yahoo Finance",
        )
        for position in positions
    }
    summary = build_portfolio_summary(
        positions,
        companies,
        prices,
        latest_audits={
            "FINON": _verified_audit("FINON"),
            "BOTH": _verified_audit("BOTH"),
        },
        technical_histories={
            "TECHON": [
                _technical_history("TECHON", 1, 70)
            ],
            "BOTH": [_technical_history("BOTH", 2, 80)],
        },
        reference_date=date(2026, 7, 18),
    )

    assert summary.decision_ready_value_percent == 90
    assert summary.current_technical_value_percent == 90
    assert summary.combined_decision_ready_value_percent == 80
    assert summary.combined_decision_ready_count == 1
    assert summary.portfolio_score_ready is False
    assert summary.weighted_combined_score is None
