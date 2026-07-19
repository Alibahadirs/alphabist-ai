from datetime import date, datetime, timezone

from app.audit.models import CompanyDataAudit, DataSourceType
from app.data_quality.evidence import (
    EVIDENCE_SCHEMA_VERSION,
    build_validation_evidence_package,
)
from app.data_quality.models import DataQualityRow
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile
from app.validation.service import (
    WarningConfirmationStatus,
    validation_warning_fingerprint,
)


def test_validation_evidence_package_contains_verifiable_warning_proof():
    warnings = ["Cari oranı resmi rapordan kontrol edin."]
    methodology = "alpha-2026.4"
    fingerprint = validation_warning_fingerprint(warnings, methodology)
    company = FinancialMetrics(
        symbol="TEST",
        company_name="Test Sanayi A.Ş.",
    )
    audit = CompanyDataAudit(
        symbol="TEST",
        source_type=DataSourceType.PDF,
        company_profile=CompanyProfile.STANDARD,
        report_period_end=date(2026, 6, 30),
        completeness=100,
        alpha_score=80,
        confidence_score=90,
        methodology_version=methodology,
        input_fingerprint="b" * 64,
        validation_warnings_confirmed=True,
        validation_warnings=warnings,
        validation_warning_fingerprint=fingerprint,
    )
    row = DataQualityRow(
        symbol="TEST",
        company_name=company.company_name,
        company_profile=CompanyProfile.STANDARD,
        completeness=100,
        status="Doğrulandı",
        warnings=warnings,
        warnings_confirmed=True,
        warning_confirmation_status=WarningConfirmationStatus.CONFIRMED,
    )
    generated_at = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)

    package = build_validation_evidence_package(
        company,
        row,
        audit,
        generated_at=generated_at,
    )

    assert package["schema_version"] == EVIDENCE_SCHEMA_VERSION
    assert package["generated_at"] == "2026-07-19T12:00:00+00:00"
    assert package["company"]["symbol"] == "TEST"
    assert package["analysis"]["report_period_end"] == "2026-06-30"
    assert package["warning_evidence"]["status"] == "Onaylandı"
    assert package["warning_evidence"]["stored_fingerprint"] == fingerprint
    assert package["warning_evidence"]["fingerprint_matches"] is True
    assert package["data_quality"]["status"] == "Doğrulandı"
