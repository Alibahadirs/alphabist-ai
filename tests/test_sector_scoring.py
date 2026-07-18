import pytest

from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.sector.profiles import (
    CompanyProfile,
    detect_company_profile,
    reconcile_company_profiles,
)
from app.validation.service import (
    get_profile_requirements,
    validate_financial_metrics,
)


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


def test_bank_revenue_growth_is_required_when_growth_score_uses_it():
    metrics = FinancialMetrics(
        symbol="TBNK",
        company_name="Test Bankası A.Ş.",
        company_profile=CompanyProfile.BANK,
        net_profit_growth=30,
        roe=25,
        capital_adequacy_ratio=18,
        npl_ratio=2.5,
        loan_to_deposit_ratio=100,
        net_interest_margin=5,
        cost_income_ratio=40,
    )

    report = validate_financial_metrics(metrics)

    assert "revenue_growth" in report.missing_fields
    assert report.completeness < 100


def test_insurance_requires_every_metric_used_by_its_score():
    metrics = FinancialMetrics(
        symbol="TSGR",
        company_name="Test Sigorta A.Ş.",
        company_profile=CompanyProfile.INSURANCE,
        net_profit_growth=25,
        roe=24,
        premium_growth=30,
        combined_ratio=92,
        solvency_ratio=160,
    )

    report = validate_financial_metrics(metrics)

    assert "net_margin" in report.missing_fields
    assert "current_ratio" in report.missing_fields
    assert report.completeness < 100


def test_financial_services_accepts_debt_to_equity_as_leverage_alternative():
    metrics = FinancialMetrics(
        symbol="TFIN",
        company_name="Test Faktoring A.Ş.",
        company_profile=CompanyProfile.FINANCIAL_SERVICES,
        revenue_growth=20,
        net_profit_growth=30,
        net_margin=18,
        roe=25,
        debt_to_equity=4,
        current_ratio=1.3,
        npl_ratio=2.5,
        cost_income_ratio=40,
    )

    report = validate_financial_metrics(metrics)

    assert "debt_to_equity" in get_profile_requirements(metrics)
    assert "capital_adequacy_ratio" not in get_profile_requirements(metrics)
    assert report.completeness == 100


def test_financial_services_prefers_capital_adequacy_when_available():
    metrics = FinancialMetrics(
        symbol="TFIN",
        company_name="Test Menkul Değerler A.Ş.",
        company_profile=CompanyProfile.FINANCIAL_SERVICES,
        revenue_growth=20,
        net_profit_growth=30,
        net_margin=18,
        roe=25,
        debt_to_equity=4,
        current_ratio=1.3,
        capital_adequacy_ratio=18,
        npl_ratio=2.5,
        cost_income_ratio=40,
    )

    required = get_profile_requirements(metrics)

    assert "capital_adequacy_ratio" in required
    assert "debt_to_equity" not in required


@pytest.mark.parametrize(
    ("financial", "activity", "expected"),
    [
        (
            CompanyProfile.STANDARD,
            CompanyProfile.BANK,
            CompanyProfile.BANK,
        ),
        (
            CompanyProfile.INSURANCE,
            CompanyProfile.STANDARD,
            CompanyProfile.INSURANCE,
        ),
        (
            CompanyProfile.REIT,
            CompanyProfile.REIT,
            CompanyProfile.REIT,
        ),
        (
            CompanyProfile.FINANCIAL_SERVICES,
            None,
            CompanyProfile.FINANCIAL_SERVICES,
        ),
    ],
)
def test_profile_reconciliation_uses_nonstandard_evidence_without_conflict(
    financial,
    activity,
    expected,
):
    resolution = reconcile_company_profiles(financial, activity)

    assert resolution.profile == expected
    assert resolution.has_conflict is False


def test_profile_reconciliation_flags_two_different_sector_profiles():
    resolution = reconcile_company_profiles(
        CompanyProfile.BANK,
        CompanyProfile.FINANCIAL_SERVICES,
    )

    assert resolution.profile == CompanyProfile.BANK
    assert resolution.financial_profile == CompanyProfile.BANK
    assert resolution.activity_profile == CompanyProfile.FINANCIAL_SERVICES
    assert resolution.has_conflict is True
