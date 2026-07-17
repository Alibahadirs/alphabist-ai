from collections.abc import Mapping, Sequence

from app.audit.models import CompanyDataAudit
from app.confidence.service import calculate_analysis_confidence
from app.scanner.models import ScannerFilters, ScannerRow, ScannerSummary
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


def scan_companies(
    companies: Sequence[FinancialMetrics],
    filters: ScannerFilters,
    latest_audits: Mapping[str, CompanyDataAudit] | None = None,
) -> ScannerSummary:
    audits = {
        symbol.upper(): audit for symbol, audit in (latest_audits or {}).items()
    }
    rows: list[ScannerRow] = []
    for company in companies:
        score = calculate_alpha_score(company)
        confidence = (
            calculate_analysis_confidence(
                company, score, audits.get(company.symbol.upper())
            )
            if latest_audits is not None
            else None
        )
        if (
            filters.decision_ready_only
            and confidence is not None
            and not confidence.decision_ready
        ):
            continue
        if score.total < filters.minimum_alpha_score:
            continue
        profile = CompanyProfile(company.company_profile)
        if profile in (CompanyProfile.STANDARD, CompanyProfile.REIT):
            if (company.revenue_growth or 0) < filters.minimum_revenue_growth:
                continue
            if (company.net_margin or 0) < filters.minimum_net_margin:
                continue
            if (company.debt_to_equity or 0) > filters.maximum_debt_to_equity:
                continue
            if filters.positive_operating_cash_flow_only and (company.operating_cash_flow or 0) <= 0:
                continue

        rows.append(
            ScannerRow(
                symbol=company.symbol,
                company_name=company.company_name,
                alpha_score=score.total,
                grade=score.grade,
                decision=confidence.decision if confidence else score.decision,
                revenue_growth=company.revenue_growth or 0,
                net_margin=company.net_margin or 0,
                roe=company.roe or 0,
                debt_to_equity=company.debt_to_equity or 0,
                current_ratio=company.current_ratio or 0,
                operating_cash_flow=company.operating_cash_flow or 0,
                company_profile=profile.value,
                data_completeness=score.data_completeness,
                confidence_score=confidence.total if confidence else None,
                confidence_status=confidence.status if confidence else "",
                calculation_check_status=(
                    confidence.calculation_check_status
                    if confidence
                    else "Kayıt yok"
                ),
                decision_ready=(
                    confidence.decision_ready if confidence else True
                ),
            )
        )

    rows.sort(key=lambda row: row.alpha_score, reverse=True)
    average_alpha_score = (
        round(sum(row.alpha_score for row in rows) / len(rows), 2)
        if rows
        else 0
    )
    return ScannerSummary(
        rows=rows,
        total_scanned=len(companies),
        matched_count=len(rows),
        average_alpha_score=average_alpha_score,
    )
