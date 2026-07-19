import pytest

from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.sector.profiles import (
    CompanyProfile,
    detect_company_profile,
    reconcile_company_profiles,
)
from app.validation.service import (
    WarningConfirmationStatus,
    get_validation_warning_confirmation_status,
    get_profile_requirements,
    validate_financial_metrics,
    warning_confirmation_recommended_action,
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


def test_extreme_bank_ratios_require_review_without_blocking_record():
    metrics = FinancialMetrics(
        symbol="TBNK",
        company_name="Test Bankası A.Ş.",
        company_profile=CompanyProfile.BANK,
        revenue_growth=20,
        net_profit_growth=30,
        roe=25,
        capital_adequacy_ratio=18,
        npl_ratio=35,
        loan_to_deposit_ratio=700,
        net_interest_margin=60,
        cost_income_ratio=500,
    )

    report = validate_financial_metrics(metrics)

    assert report.is_valid
    assert len(report.warnings) >= 4
    assert any("Kredi / mevduat" in warning for warning in report.warnings)
    assert any("Net faiz marjı" in warning for warning in report.warnings)
    assert any("Maliyet / gelir" in warning for warning in report.warnings)


def test_extreme_insurance_ratios_require_review():
    metrics = FinancialMetrics(
        symbol="TSGR",
        company_name="Test Sigorta A.Ş.",
        company_profile=CompanyProfile.INSURANCE,
        net_profit_growth=25,
        net_margin=12,
        roe=24,
        current_ratio=50,
        premium_growth=1_500,
        combined_ratio=250,
        solvency_ratio=900,
    )

    report = validate_financial_metrics(metrics)

    assert report.is_valid
    assert len(report.warnings) >= 4
    assert any("Prim büyümesi" in warning for warning in report.warnings)
    assert any("Ödeme gücü" in warning for warning in report.warnings)


def test_reit_nav_discount_above_one_hundred_is_invalid():
    metrics = FinancialMetrics(
        symbol="TGYOR",
        company_name="Test GYO A.Ş.",
        company_profile=CompanyProfile.REIT,
        nav_discount=120,
    )

    report = validate_financial_metrics(metrics)

    assert not report.is_valid
    assert "NAD iskontosu %100'den büyük olamaz." in report.errors


def test_extreme_reit_nav_premium_requires_review():
    metrics = FinancialMetrics(
        symbol="TGYOR",
        company_name="Test GYO A.Ş.",
        company_profile=CompanyProfile.REIT,
        nav_discount=-300,
    )

    report = validate_financial_metrics(metrics)

    assert report.is_valid
    assert any("NAD iskontosu" in warning for warning in report.warnings)


def test_normal_bank_ratios_do_not_create_sector_range_warnings():
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
    )

    report = validate_financial_metrics(metrics)

    assert report.is_valid
    assert report.warnings == []


@pytest.mark.parametrize(
    ("current", "stored", "confirmed", "stored_methodology", "expected"),
    [
        ([], [], False, "alpha-2026.4", WarningConfirmationStatus.NOT_APPLICABLE),
        (["Uyarı"], [], False, "alpha-2026.4", WarningConfirmationStatus.REQUIRED),
        (
            ["Uyarı"],
            ["Uyarı"],
            True,
            "alpha-2025.1",
            WarningConfirmationStatus.METHODOLOGY_CHANGED,
        ),
        (
            ["Yeni uyarı"],
            ["Eski uyarı"],
            True,
            "alpha-2026.4",
            WarningConfirmationStatus.WARNINGS_CHANGED,
        ),
        (
            ["Uyarı"],
            ["Uyarı"],
            True,
            "alpha-2026.4",
            WarningConfirmationStatus.CONFIRMED,
        ),
    ],
)
def test_warning_confirmation_status_explains_evidence_state(
    current,
    stored,
    confirmed,
    stored_methodology,
    expected,
):
    assert get_validation_warning_confirmation_status(
        current,
        stored,
        confirmed,
        stored_methodology,
        "alpha-2026.4",
    ) == expected


@pytest.mark.parametrize("status", list(WarningConfirmationStatus))
def test_every_warning_confirmation_status_has_a_recommended_action(status):
    action = warning_confirmation_recommended_action(status)

    assert action
    if status == WarningConfirmationStatus.EVIDENCE_DAMAGED:
        assert "kaydı kullanma" in action.lower()
