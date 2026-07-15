from app.analysis.service import build_company_analysis
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


def _build(metrics: FinancialMetrics):
    return build_company_analysis(metrics, calculate_alpha_score(metrics))


def test_bank_analysis_uses_asset_quality_instead_of_cash_flow():
    analysis = _build(
        FinancialMetrics(
            symbol="TBNK",
            company_name="Test Bankası A.Ş.",
            company_profile=CompanyProfile.BANK,
            revenue_growth=12,
            net_profit_growth=25,
            roe=24,
            capital_adequacy_ratio=18,
            npl_ratio=2,
            loan_to_deposit_ratio=100,
            net_interest_margin=5,
            cost_income_ratio=40,
        )
    )

    labels = {item.label for item in analysis.indicators}
    assert "Takipteki kredi / alacak oranı" in labels
    assert "Cari oran" not in labels
    assert any("Takipteki kredi" in item for item in analysis.strengths)


def test_incomplete_financial_company_explains_missing_fields():
    analysis = _build(
        FinancialMetrics(
            symbol="TFIN",
            company_name="Test Faktoring A.Ş.",
            company_profile=CompanyProfile.FINANCIAL_SERVICES,
            revenue_growth=20,
            net_profit_growth=15,
            net_margin=8,
            roe=18,
        )
    )

    assert analysis.data_completeness < 70
    assert "yeterli değil" in analysis.summary
    assert any("Sermaye yeterliliği" in item for item in analysis.risks)


def test_insurance_combined_ratio_below_one_hundred_is_strong():
    analysis = _build(
        FinancialMetrics(
            symbol="TSGR",
            company_name="Test Sigorta A.Ş.",
            company_profile=CompanyProfile.INSURANCE,
            net_profit_growth=20,
            net_margin=10,
            roe=22,
            current_ratio=1.3,
            premium_growth=25,
            combined_ratio=95,
            solvency_ratio=150,
        )
    )

    combined = next(item for item in analysis.indicators if item.field == "combined_ratio")
    assert combined.status == "Güçlü"


def test_reit_nav_discount_is_reported_with_occupancy():
    analysis = _build(
        FinancialMetrics(
            symbol="TGYOR",
            company_name="Test Gayrimenkul Yatırım Ortaklığı A.Ş.",
            company_profile=CompanyProfile.REIT,
            revenue_growth=20,
            net_profit_growth=20,
            net_margin=30,
            roe=15,
            debt_to_equity=0.4,
            current_ratio=1.2,
            operating_cash_flow=100,
            nav_discount=30,
            occupancy_rate=90,
        )
    )

    statuses = {item.field: item.status for item in analysis.indicators}
    assert statuses["nav_discount"] == "Güçlü"
    assert statuses["occupancy_rate"] == "Güçlü"
