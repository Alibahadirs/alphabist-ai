from datetime import date

from app.audit.models import CompanyDataAudit, DataSourceType, MetricSourceType
from app.core.settings import settings
from app.data_quality.service import build_data_quality_summary
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


def _complete_company() -> FinancialMetrics:
    return FinancialMetrics(
        symbol="CALC", company_name="Calculation Sanayi A.Ş.",
        revenue_growth=20, net_profit_growth=20, net_margin=10, roe=20,
        debt_to_equity=0.5, current_ratio=1.5, operating_cash_flow=100,
        free_cash_flow=50, asset_turnover=0.8,
    )


def _calculation_audit(stored_growth: float) -> CompanyDataAudit:
    return CompanyDataAudit(
        symbol="CALC",
        source_type=DataSourceType.PDF,
        company_profile=CompanyProfile.STANDARD,
        period_months=12,
        report_period_end=date(2026, 12, 31),
        completeness=100,
        alpha_score=80,
        methodology_version=settings.scoring_methodology_version,
        field_sources={
            "revenue_growth": MetricSourceType.FINANCIAL_REPORT,
        },
        source_values={
            "revenue": 1_200_000,
            "previous_revenue": 1_000_000,
        },
        metric_values={
            "company_name": "Calculation Sanayi A.Ş.",
            "revenue_growth": stored_growth,
        },
    )


def test_data_quality_summary_separates_verified_and_critical_companies():
    verified = FinancialMetrics(
        symbol="GOOD", company_name="Good Sanayi A.Ş.", revenue_growth=10,
        net_profit_growth=10, net_margin=10, roe=15, debt_to_equity=0.5,
        current_ratio=1.5, operating_cash_flow=100, free_cash_flow=50,
        asset_turnover=0.8,
    )
    incomplete_bank = FinancialMetrics(
        symbol="TBNK", company_name="Test Bankası A.Ş.",
        company_profile=CompanyProfile.BANK, net_profit_growth=20, roe=20,
    )

    summary = build_data_quality_summary([verified, incomplete_bank])

    assert summary.total_companies == 2
    assert summary.verified_count == 1
    assert summary.critical_count == 1
    assert summary.rows[0].symbol == "TBNK"
    assert "Sermaye yeterliliği" in summary.rows[0].missing_fields


def test_outlier_warning_requires_review_even_with_complete_data():
    company = FinancialMetrics(
        symbol="OUTL", company_name="Outlier Sanayi A.Ş.", revenue_growth=10,
        net_profit_growth=10, net_margin=150, roe=15, debt_to_equity=0.5,
        current_ratio=1.5, operating_cash_flow=100, free_cash_flow=50,
        asset_turnover=0.8,
    )

    summary = build_data_quality_summary([company])

    assert summary.rows[0].status == "Kontrol gerekli"
    assert summary.review_count == 1


def test_extreme_standard_ratios_require_review():
    company = FinancialMetrics(
        symbol="RATE", company_name="Rate Sanayi A.Ş.", revenue_growth=-100,
        net_profit_growth=10, net_margin=10, roe=15, debt_to_equity=0.5,
        current_ratio=250, operating_cash_flow=100, free_cash_flow=50,
        asset_turnover=500,
    )

    row = build_data_quality_summary([company]).rows[0]

    assert row.status == "Kontrol gerekli"
    assert len(row.warnings) >= 3


def test_matching_calculation_is_verified_in_data_quality_summary():
    company = _complete_company()

    row = build_data_quality_summary(
        [company], {company.symbol: _calculation_audit(20)}
    ).rows[0]

    assert row.status == "Doğrulandı"
    assert row.calculation_check_status == "Doğrulandı"
    assert row.calculation_mismatch_fields == []


def test_calculation_mismatch_is_a_critical_data_quality_error():
    company = _complete_company()

    summary = build_data_quality_summary(
        [company], {company.symbol: _calculation_audit(25)}
    )
    row = summary.rows[0]

    assert row.status == "Hatalı"
    assert row.calculation_check_status == "Uyuşmazlık"
    assert row.calculation_mismatch_fields == ["Gelir büyümesi"]
    assert any("yeniden hesaplanan" in error for error in row.errors)
    assert summary.critical_count == 1


def test_old_methodology_does_not_raise_calculation_error():
    company = _complete_company()
    old_audit = _calculation_audit(25).model_copy(
        update={"methodology_version": "alpha-2025.1"}
    )

    row = build_data_quality_summary(
        [company], {company.symbol: old_audit}
    ).rows[0]

    assert row.status == "Doğrulandı"
    assert row.calculation_check_status == "Eski metodoloji"
    assert row.calculation_mismatch_fields == []
