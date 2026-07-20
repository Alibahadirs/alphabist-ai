import json
from datetime import datetime, timezone

import pytest

from app.reporting.company_report import company_report_fingerprint
from app.reporting.exchange import (
    build_company_report_exchange_package,
    company_report_package_fingerprint,
    serialize_company_report_exchange_package,
    validate_company_report_exchange_package,
)
from app.reporting.models import CompanyInvestmentReport
from app.sector.profiles import CompanyProfile


def _report(symbol: str = "TEST") -> CompanyInvestmentReport:
    report = CompanyInvestmentReport(
        symbol=symbol,
        company_name="Test A.Ş.",
        company_profile=CompanyProfile.STANDARD,
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        alpha_score=80,
        alpha_grade="A",
        alpha_decision="Al",
        confidence_score=90,
        confidence_status="Yüksek",
        decision_ready=True,
        combined_decision="Teknik doğrulama gerekli",
        summary="Özet",
        scoring_methodology_version="alpha-2026.4",
        technical_methodology_version="technical-2026.1",
    )
    return report.model_copy(
        update={"report_fingerprint": company_report_fingerprint(report)}
    )


def test_company_report_exchange_package_is_deterministic():
    first = build_company_report_exchange_package(
        [_report()],
        exported_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )
    second = build_company_report_exchange_package(
        [_report()],
        exported_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )

    assert first.content_fingerprint == second.content_fingerprint
    assert first.content_fingerprint == company_report_package_fingerprint(
        first
    )
    assert first.report_count == 1


def test_company_report_exchange_package_serializes_as_utf8_json():
    package = build_company_report_exchange_package([_report()])

    payload = serialize_company_report_exchange_package(package)

    assert payload.startswith(b"\xef\xbb\xbf")
    assert '"schema_version": "company-report-package-1"' in payload.decode(
        "utf-8-sig"
    )


def test_company_report_exchange_package_rejects_mixed_symbols():
    with pytest.raises(ValueError, match="tek bir şirket"):
        build_company_report_exchange_package(
            [_report("TEST"), _report("OTHER")]
        )


def test_company_report_exchange_validation_accepts_untouched_package():
    payload = serialize_company_report_exchange_package(
        build_company_report_exchange_package([_report()])
    )

    result = validate_company_report_exchange_package(payload)

    assert result.valid is True
    assert result.package is not None
    assert result.errors == []


def test_company_report_exchange_validation_detects_report_tampering():
    package = build_company_report_exchange_package([_report()])
    raw = package.model_dump(mode="json")
    raw["reports"][0]["alpha_score"] = 5

    result = validate_company_report_exchange_package(
        json.dumps(raw, ensure_ascii=False)
    )

    assert result.valid is False
    assert any("raporun içerik parmak izi" in item for item in result.errors)
    assert any("Paket bütünlük" in item for item in result.errors)


def test_company_report_exchange_validation_rejects_invalid_json():
    result = validate_company_report_exchange_package(b"{not-json")

    assert result.valid is False
    assert result.package is None
    assert "JSON paketi okunamadı" in result.errors[0]
