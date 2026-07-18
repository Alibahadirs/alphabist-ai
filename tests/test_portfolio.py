import pytest

from app.database import repository
from app.portfolio.models import PortfolioPosition
from app.portfolio.service import build_portfolio_summary
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


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
    assert summary.rows[0].weight_percent == 100
    assert summary.largest_position_symbol == "TEST"
    assert summary.largest_position_percent == 100
    assert summary.profile_exposure == {"standard": 100}
    assert summary.concentration_warnings
    assert summary.concentration_index == 100
    assert summary.effective_position_count == 1
    assert summary.diversification_status == "Yoğun"
    scenarios = {
        scenario.shock_percent: scenario
        for scenario in summary.stress_scenarios
    }
    assert set(scenarios) == {-20, -10, 10}
    assert scenarios[-20].label == "%20 düşüş"
    assert scenarios[-20].projected_market_value == 200
    assert scenarios[-20].value_change == -50
    assert scenarios[-20].projected_profit_loss == 0
    assert scenarios[-20].projected_return_percent == 0
    assert scenarios[-10].projected_market_value == 225
    assert scenarios[-10].value_change == -25
    assert scenarios[-10].projected_profit_loss == 25
    assert scenarios[-10].projected_return_percent == 12.5
    assert scenarios[10].label == "%10 yükseliş"
    assert scenarios[10].projected_market_value == 275
    assert scenarios[10].value_change == 25
    assert scenarios[10].projected_profit_loss == 75
    assert scenarios[10].projected_return_percent == 37.5


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
