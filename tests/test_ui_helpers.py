from app.sector.profiles import CompanyProfile
from app.ui.pages import _format_turkish_amount, _pdf_source_fields


def test_turkish_amount_format_preserves_amount_semantics():
    assert _format_turkish_amount(None) == "-"
    assert _format_turkish_amount(1_234_567) == "1.234.567"
    assert _format_turkish_amount(1_234_567.5) == "1.234.567,50"


def test_pdf_source_fields_are_sector_specific():
    standard = _pdf_source_fields(CompanyProfile.STANDARD)
    bank = _pdf_source_fields(CompanyProfile.BANK)
    insurance = _pdf_source_fields(CompanyProfile.INSURANCE)

    assert "total_debt" in standard
    assert "current_assets" in standard
    assert "total_debt" not in bank
    assert "current_assets" not in bank
    assert "premium_revenue" in insurance
    assert "premium_revenue" not in standard
