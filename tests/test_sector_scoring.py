import pytest

from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile, detect_company_profile
from app.validation.service import validate_financial_metrics


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Örnek Bankası A.Ş.", CompanyProfile.BANK),
        ("Örnek Sigorta A.Ş.", CompanyProfile.INSURANCE),
        ("Örnek Gayrimenkul Yatırım Ortaklığı A.Ş.", CompanyProfile.REIT),
        ("Örnek Faktoring A.Ş.", CompanyProfile.FINANCIAL_SERVICES),
        ("Örnek Sanayi A.Ş.", CompanyProfile.STANDARD),
    ],
)
def test_company_profile_detection(name, expected):
    assert detect_company_profile(name) == expected


def test_bank_loan_note_does_not_turn_industrial_company_into_bank():
    profile = detect_company_profile(
        "Örnek Sanayi A.Ş.",
        "Şirketin banka kredileri ve finansman giderleri bulunmaktadır.",
    )

    assert profile == CompanyProfile.STANDARD


def test_bank_uses_bank_specific_metrics_and_is_complete():
    metrics = FinancialMetrics(
        symbol="TBNK",
        company_name="Test Bankası A.Ş.",
        company_profile=CompanyProfile.BANK,
        revenue_growth=20,
        net_profit_growth=30,
        roe=25,
        capital_adequacy_ratio=18,
        npl_ratio=2.5,
        loan_to_deposit_ratio=100,
        net_interest_margin=5,
        cost_income_ratio=40,
        valuation_score_input=70,
        management_score_input=80,
        risk_score_input=75,
    )

    score = calculate_alpha_score(metrics)

    assert score.company_profile == CompanyProfile.BANK
    assert score.data_completeness == 100
    assert score.leverage > 10
    assert score.cash_flow > 10
    assert score.decision != "Eksik veri / Doğrula"


def test_incomplete_bank_is_flagged_instead_of_silently_scored():
    metrics = FinancialMetrics(
        symbol="TBNK",
        company_name="Eksik Bankası A.Ş.",
        company_profile=CompanyProfile.BANK,
        net_profit_growth=20,
        roe=20,
    )

    report = validate_financial_metrics(metrics)
    score = calculate_alpha_score(metrics)

    assert report.completeness < 70
    assert "capital_adequacy_ratio" in report.missing_fields
    assert score.decision == "Eksik veri / Doğrula"


def test_insurance_uses_combined_and_solvency_ratios():
    metrics = FinancialMetrics(
        symbol="TSGR",
        company_name="Test Sigorta A.Ş.",
        company_profile=CompanyProfile.INSURANCE,
        net_profit_growth=25,
        net_margin=12,
        roe=24,
        current_ratio=1.4,
        premium_growth=30,
        combined_ratio=92,
        solvency_ratio=160,
    )

    score = calculate_alpha_score(metrics)

    assert score.data_completeness == 100
    assert score.leverage > 10
    assert score.cash_flow > 10


def test_reit_requires_nav_and_occupancy_data():
    metrics = FinancialMetrics(
        symbol="TGYOR",
        company_name="Test Gayrimenkul Yatırım Ortaklığı A.Ş.",
        company_profile=CompanyProfile.REIT,
        revenue_growth=15,
        net_profit_growth=20,
        net_margin=25,
        roe=12,
        debt_to_equity=0.4,
        operating_cash_flow=100,
    )

    report = validate_financial_metrics(metrics)

    assert "nav_discount" in report.missing_fields
    assert "occupancy_rate" in report.missing_fields
