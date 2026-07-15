from app.data_quality.service import build_data_quality_summary
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


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
