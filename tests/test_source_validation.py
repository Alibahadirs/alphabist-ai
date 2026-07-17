from app.parser.models import FinancialReportDraft
from app.sector.profiles import CompanyProfile
from app.validation.service import validate_financial_draft


def test_standard_company_rejects_impossible_balance_sheet_relationships():
    draft = FinancialReportDraft(
        company_profile=CompanyProfile.STANDARD,
        revenue=1_000,
        equity=1_200,
        cash=800,
        current_assets=700,
        total_assets=1_000,
    )

    report = validate_financial_draft(draft)

    assert not report.is_valid
    assert any("Özkaynak toplam varlıktan" in error for error in report.errors)
    assert any("Nakit dönen varlıktan" in error for error in report.errors)


def test_bank_does_not_use_industrial_current_asset_relationship():
    draft = FinancialReportDraft(
        company_profile=CompanyProfile.BANK,
        revenue=1_000,
        cash=800,
        current_assets=700,
        total_assets=1_000,
        equity=200,
    )

    report = validate_financial_draft(draft)

    assert report.is_valid
    assert not any("dönen varlıktan" in error.lower() for error in report.errors)


def test_period_scale_mismatch_is_reported_as_warning():
    draft = FinancialReportDraft(
        revenue=1_000_000,
        previous_revenue=1_000,
        equity=500_000,
        total_assets=1_000_000,
    )

    report = validate_financial_draft(draft)

    assert report.is_valid
    assert any("en az 1.000 kat" in warning for warning in report.warnings)


def test_negative_balance_sheet_amount_is_rejected():
    draft = FinancialReportDraft(total_debt=-1)

    report = validate_financial_draft(draft)

    assert not report.is_valid
    assert "Finansal borç negatif olamaz." in report.errors


def test_reit_allows_large_profit_from_fair_value_changes():
    draft = FinancialReportDraft(
        company_profile=CompanyProfile.REIT,
        revenue=100,
        net_profit=1_000,
        equity=800,
        current_assets=400,
        cash=100,
        total_assets=1_200,
    )

    report = validate_financial_draft(draft)

    assert report.is_valid
    assert not any("Net dönem kârı" in warning for warning in report.warnings)
