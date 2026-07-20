from app.database.repository import add_company_report_snapshot
from app.reporting.exchange import (
    validate_company_report_exchange_package,
)
from app.reporting.models import CompanyReportImportResult


def import_company_report_exchange_package(
    payload: bytes | str,
    *,
    expected_symbol: str,
) -> CompanyReportImportResult:
    validation = validate_company_report_exchange_package(payload)
    if not validation.valid or validation.package is None:
        return CompanyReportImportResult(
            valid=False,
            errors=validation.errors,
        )

    normalized_symbol = expected_symbol.upper().strip()
    if validation.package.symbol.upper().strip() != normalized_symbol:
        return CompanyReportImportResult(
            valid=False,
            errors=[
                "Paket seçili şirkete ait değil: "
                f"{validation.package.symbol}."
            ],
        )

    imported_count = 0
    duplicate_count = 0
    for report in validation.package.reports:
        if add_company_report_snapshot(report):
            imported_count += 1
        else:
            duplicate_count += 1

    return CompanyReportImportResult(
        valid=True,
        imported_count=imported_count,
        duplicate_count=duplicate_count,
    )
