import json
from datetime import date, datetime, timezone

from app.audit.models import CompanyDataAudit, DataSourceType
from app.data_quality.evidence import (
    EVIDENCE_INTEGRITY_ALGORITHM,
    EVIDENCE_SCHEMA_VERSION,
    build_validation_evidence_package,
    compare_validation_evidence_packages,
    serialize_validation_evidence_package,
    validation_evidence_digest,
    verify_validation_evidence_package,
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
    assert package["integrity"]["algorithm"] == EVIDENCE_INTEGRITY_ALGORITHM
    assert package["integrity"]["digest"] == validation_evidence_digest(
        package
    )
    assert len(package["integrity"]["digest"]) == 64

    serialized = serialize_validation_evidence_package(package)
    decoded = json.loads(serialized.decode("utf-8"))

    assert decoded == package
    assert "Test Sanayi A.Ş.".encode("utf-8") in serialized


def _valid_evidence_bytes() -> bytes:
    company = FinancialMetrics(symbol="TEST", company_name="Test A.Ş.")
    row = DataQualityRow(
        symbol="TEST",
        company_name=company.company_name,
        company_profile=CompanyProfile.STANDARD,
        completeness=100,
        status="Doğrulandı",
    )
    return serialize_validation_evidence_package(
        build_validation_evidence_package(company, row, None)
    )


def test_evidence_verifier_accepts_intact_package():
    result = verify_validation_evidence_package(_valid_evidence_bytes())

    assert result.valid is True
    assert result.status == "Doğrulandı"
    assert result.errors == []
    assert result.package["company"]["symbol"] == "TEST"


def test_evidence_verifier_rejects_modified_package():
    package = json.loads(_valid_evidence_bytes())
    package["company"]["symbol"] = "FAKE"

    result = verify_validation_evidence_package(
        json.dumps(package).encode("utf-8")
    )

    assert result.valid is False
    assert "bütünlük özetiyle eşleşmiyor" in " ".join(result.errors)


def test_evidence_verifier_rejects_invalid_json_and_schema():
    invalid_json = verify_validation_evidence_package(b"{")
    assert invalid_json.status == "Geçersiz JSON"

    package = json.loads(_valid_evidence_bytes())
    package["schema_version"] = "future-schema"
    package["integrity"]["digest"] = validation_evidence_digest(package)
    invalid_schema = verify_validation_evidence_package(
        json.dumps(package)
    )

    assert invalid_schema.valid is False
    assert "şema sürümü" in " ".join(invalid_schema.errors)


def test_evidence_comparison_orders_packages_and_lists_changes():
    previous = json.loads(_valid_evidence_bytes())
    previous["generated_at"] = "2026-07-18T12:00:00+00:00"
    previous["analysis"]["alpha_score"] = 70
    previous["data_quality"]["completeness"] = 80
    previous["integrity"]["digest"] = validation_evidence_digest(previous)
    current = json.loads(_valid_evidence_bytes())
    current["generated_at"] = "2026-07-19T12:00:00+00:00"
    current["analysis"]["alpha_score"] = 82
    current["data_quality"]["completeness"] = 100
    current["integrity"]["digest"] = validation_evidence_digest(current)

    result = compare_validation_evidence_packages(current, previous)

    assert result.comparable is True
    assert result.symbol == "TEST"
    assert result.previous_generated_at.startswith("2026-07-18")
    assert [change.field for change in result.changes] == [
        "Alpha Score",
        "Veri yeterliliği",
    ]


def test_evidence_comparison_rejects_different_companies():
    first = json.loads(_valid_evidence_bytes())
    second = json.loads(_valid_evidence_bytes())
    second["company"]["symbol"] = "OTHER"

    result = compare_validation_evidence_packages(first, second)

    assert result.comparable is False
    assert result.status == "Paketler aynı şirkete ait değil."
