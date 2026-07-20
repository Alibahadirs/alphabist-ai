import hashlib
import json
from datetime import datetime, timezone

from app.reporting.company_report import company_report_fingerprint
from app.reporting.models import (
    CompanyInvestmentReport,
    CompanyReportExchangePackage,
)


def company_report_package_fingerprint(
    package: CompanyReportExchangePackage,
) -> str:
    payload = package.model_dump(
        mode="json",
        exclude={"exported_at", "content_fingerprint"},
    )
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_company_report_exchange_package(
    reports: list[CompanyInvestmentReport],
    *,
    exported_at: datetime | None = None,
) -> CompanyReportExchangePackage:
    if not reports:
        raise ValueError("Aktarım paketi için en az bir rapor gerekli.")
    symbol = reports[0].symbol.upper().strip()
    if any(report.symbol.upper().strip() != symbol for report in reports):
        raise ValueError("Aktarım paketi yalnızca tek bir şirket içerebilir.")
    for report in reports:
        if (
            not report.report_fingerprint
            or report.report_fingerprint
            != company_report_fingerprint(report)
        ):
            raise ValueError("Rapor içerik parmak izi doğrulanamadı.")

    package = CompanyReportExchangePackage(
        exported_at=exported_at or datetime.now(timezone.utc),
        symbol=symbol,
        report_count=len(reports),
        reports=reports,
    )
    return package.model_copy(
        update={
            "content_fingerprint": company_report_package_fingerprint(
                package
            )
        }
    )


def serialize_company_report_exchange_package(
    package: CompanyReportExchangePackage,
) -> bytes:
    payload = json.dumps(
        package.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return payload.encode("utf-8-sig")
