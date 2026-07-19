import json
from hashlib import sha256
from datetime import datetime, timezone
from typing import Any

from app.audit.models import CompanyDataAudit
from app.data_quality.models import DataQualityRow
from app.scoring.models import FinancialMetrics
from app.validation.service import validation_warning_fingerprint


EVIDENCE_SCHEMA_VERSION = "alphabist-validation-evidence-1"
EVIDENCE_INTEGRITY_ALGORITHM = "sha256"


def _canonical_evidence_bytes(package: dict[str, Any]) -> bytes:
    return json.dumps(
        package,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def validation_evidence_digest(package: dict[str, Any]) -> str:
    unsigned_package = {
        key: value
        for key, value in package.items()
        if key != "integrity"
    }
    return sha256(_canonical_evidence_bytes(unsigned_package)).hexdigest()


def serialize_validation_evidence_package(
    package: dict[str, Any],
) -> bytes:
    return (
        json.dumps(
            package,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def build_validation_evidence_package(
    company: FinancialMetrics,
    row: DataQualityRow,
    audit: CompanyDataAudit | None,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or datetime.now(timezone.utc)
    stored_warnings = audit.validation_warnings if audit else []
    stored_methodology = audit.methodology_version if audit else "legacy"
    expected_warning_fingerprint = validation_warning_fingerprint(
        stored_warnings,
        stored_methodology,
    )
    stored_warning_fingerprint = (
        audit.validation_warning_fingerprint if audit else ""
    )
    warning_fingerprint_matches = (
        stored_warning_fingerprint == expected_warning_fingerprint
        if stored_warning_fingerprint or expected_warning_fingerprint
        else True
    )

    package = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "generated_at": timestamp.isoformat(),
        "company": {
            "symbol": company.symbol,
            "name": company.company_name,
            "profile": company.company_profile.value,
        },
        "analysis": {
            "source_type": audit.source_type.value if audit else "legacy",
            "report_period_end": (
                audit.report_period_end.isoformat()
                if audit and audit.report_period_end
                else None
            ),
            "methodology_version": stored_methodology,
            "input_fingerprint": audit.input_fingerprint if audit else "",
            "alpha_score": audit.alpha_score if audit else None,
            "confidence_score": audit.confidence_score if audit else None,
        },
        "warning_evidence": {
            "status": row.warning_confirmation_status.value,
            "recommended_action": row.warning_recommended_action,
            "confirmed": bool(
                audit and audit.validation_warnings_confirmed
            ),
            "warnings": stored_warnings,
            "stored_fingerprint": stored_warning_fingerprint,
            "expected_fingerprint": expected_warning_fingerprint,
            "fingerprint_matches": warning_fingerprint_matches,
        },
        "data_quality": {
            "status": row.status,
            "completeness": row.completeness,
            "missing_fields": row.missing_fields,
            "warnings": row.warnings,
            "errors": row.errors,
            "calculation_check_status": row.calculation_check_status,
            "calculation_mismatch_fields": (
                row.calculation_mismatch_fields
            ),
        },
    }
    package["integrity"] = {
        "algorithm": EVIDENCE_INTEGRITY_ALGORITHM,
        "digest": validation_evidence_digest(package),
    }
    return package
