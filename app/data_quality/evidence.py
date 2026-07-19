import json
import re
from dataclasses import dataclass, field
from hashlib import sha256
from datetime import datetime, timezone
from typing import Any

from app.audit.models import CompanyDataAudit
from app.data_quality.models import DataQualityRow
from app.scoring.models import FinancialMetrics
from app.validation.service import validation_warning_fingerprint


EVIDENCE_SCHEMA_VERSION = "alphabist-validation-evidence-1"
EVIDENCE_INTEGRITY_ALGORITHM = "sha256"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class EvidenceVerificationResult:
    valid: bool
    status: str
    errors: list[str] = field(default_factory=list)
    package: dict[str, Any] | None = None


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


def verify_validation_evidence_package(
    content: bytes | str,
) -> EvidenceVerificationResult:
    try:
        raw_content = (
            content.decode("utf-8-sig")
            if isinstance(content, bytes)
            else content
        )
        package = json.loads(raw_content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return EvidenceVerificationResult(
            valid=False,
            status="Geçersiz JSON",
            errors=["Dosya geçerli UTF-8 JSON biçiminde değil."],
        )

    if not isinstance(package, dict):
        return EvidenceVerificationResult(
            valid=False,
            status="Geçersiz yapı",
            errors=["Kanıt paketinin kök değeri bir JSON nesnesi olmalıdır."],
        )

    errors: list[str] = []
    required_sections = {
        "schema_version",
        "generated_at",
        "company",
        "analysis",
        "warning_evidence",
        "data_quality",
        "integrity",
    }
    missing_sections = sorted(required_sections.difference(package))
    if missing_sections:
        errors.append(
            "Zorunlu bölümler eksik: " + ", ".join(missing_sections)
        )

    if package.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append("Kanıt paketi şema sürümü desteklenmiyor.")

    try:
        datetime.fromisoformat(str(package.get("generated_at", "")))
    except ValueError:
        errors.append("Paket oluşturulma zamanı geçerli ISO-8601 değil.")

    company = package.get("company")
    if not isinstance(company, dict):
        errors.append("Şirket bölümü geçerli bir nesne değil.")
    elif not str(company.get("symbol", "")).strip():
        errors.append("Şirket hisse kodu eksik.")

    integrity = package.get("integrity")
    if not isinstance(integrity, dict):
        errors.append("Bütünlük bölümü geçerli bir nesne değil.")
    else:
        algorithm = integrity.get("algorithm")
        stored_digest = str(integrity.get("digest", ""))
        if algorithm != EVIDENCE_INTEGRITY_ALGORITHM:
            errors.append("Bütünlük algoritması desteklenmiyor.")
        if not _SHA256_PATTERN.fullmatch(stored_digest):
            errors.append("Bütünlük özeti geçerli bir SHA-256 değeri değil.")
        elif stored_digest != validation_evidence_digest(package):
            errors.append("Kanıt paketi içeriği bütünlük özetiyle eşleşmiyor.")

    analysis = package.get("analysis")
    warning_evidence = package.get("warning_evidence")
    if isinstance(analysis, dict) and isinstance(warning_evidence, dict):
        warnings = warning_evidence.get("warnings")
        methodology = str(analysis.get("methodology_version", ""))
        expected_fingerprint = warning_evidence.get(
            "expected_fingerprint"
        )
        if not isinstance(warnings, list):
            errors.append("Uyarı kanıtı listesi geçerli değil.")
        elif expected_fingerprint != validation_warning_fingerprint(
            [str(warning) for warning in warnings],
            methodology,
        ):
            errors.append("Uyarı kanıtı parmak izi yeniden üretilemedi.")
    else:
        errors.append("Analiz veya uyarı kanıtı bölümü geçerli değil.")

    return EvidenceVerificationResult(
        valid=not errors,
        status="Doğrulandı" if not errors else "Doğrulama başarısız",
        errors=errors,
        package=package,
    )


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
