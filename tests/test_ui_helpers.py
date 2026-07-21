from app.sector.profiles import CompanyProfile
from app.audit.models import CompanyDataAudit, DataSourceType
from app.validation.service import WarningConfirmationStatus
from app.ui.pages import (
    WARNING_CONFIRMATION_OPTIONS,
    _audit_warning_confirmation_label,
    _format_metric_snapshot_value,
    _format_turkish_amount,
    _market_data_disclosure,
    _pdf_source_fields,
    _subjective_score_confirmation_error,
    _validation_warning_confirmation_error,
)


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


def test_metric_snapshot_values_follow_field_type():
    assert (
        _format_metric_snapshot_value("operating_cash_flow", 1_250_000)
        == "1.250.000 TL"
    )
    assert _format_metric_snapshot_value("roe", 18.5) == "%18,50"
    assert _format_metric_snapshot_value("current_ratio", 1.25) == "1,25"
    assert (
        _format_metric_snapshot_value("valuation_score_input", 75)
        == "75/100"
    )
    assert _format_metric_snapshot_value("roe", None) == "-"


def test_subjective_score_inputs_require_explicit_confirmation():
    assert _subjective_score_confirmation_error(True) is None
    assert "doğrulamadan" in _subjective_score_confirmation_error(False)


def test_validation_warnings_require_confirmation_only_when_present():
    warnings = ["Kredi / mevduat oranını kontrol edin."]

    assert _validation_warning_confirmation_error([], False) is None
    assert _validation_warning_confirmation_error(warnings, True) is None
    assert "kaydedilemez" in _validation_warning_confirmation_error(
        warnings,
        False,
    )


def test_audit_warning_confirmation_label_distinguishes_evidence_states():
    base = CompanyDataAudit(
        symbol="TEST",
        source_type=DataSourceType.MANUAL,
        company_profile=CompanyProfile.STANDARD,
        completeness=100,
        alpha_score=70,
    )
    unconfirmed = base.model_copy(
        update={"validation_warnings": ["Bir uyarı"]}
    )
    confirmed = unconfirmed.model_copy(
        update={"validation_warnings_confirmed": True}
    )

    assert _audit_warning_confirmation_label(None) == "Uygulanamaz"
    assert _audit_warning_confirmation_label(base) == "Uygulanamaz"
    assert _audit_warning_confirmation_label(unconfirmed) == "Onaylanmadı"
    assert _audit_warning_confirmation_label(confirmed) == "Onaylandı"


def test_warning_confirmation_filter_contains_every_status():
    assert set(WARNING_CONFIRMATION_OPTIONS) == {
        status.value for status in WarningConfirmationStatus
    }


def test_market_data_disclosure_never_calls_delayed_data_live():
    primary = _market_data_disclosure(
        {
            "data_mode": "delayed",
            "official": False,
            "fallback_used": False,
        }
    )
    fallback = _market_data_disclosure(
        {
            "data_mode": "delayed",
            "official": False,
            "fallback_used": True,
        }
    )

    assert primary == (
        "Gecikmeli veri | Resmi BIST kaynağı değil | Birincil sağlayıcı"
    )
    assert fallback.endswith("Yedek sağlayıcı kullanıldı")
    assert "Canlı" not in primary
    assert "Canlı" not in fallback
