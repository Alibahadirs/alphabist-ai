from collections.abc import Mapping, Sequence

from app.audit.models import CompanyDataAudit
from app.confidence.service import calculate_analysis_confidence
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.watchlist.models import WatchlistEntry, WatchlistRow, WatchlistSummary


def build_watchlist_summary(
    entries: Sequence[WatchlistEntry],
    companies: Mapping[str, FinancialMetrics],
    latest_audits: Mapping[str, CompanyDataAudit] | None = None,
) -> WatchlistSummary:
    audits = {
        symbol.upper(): audit for symbol, audit in (latest_audits or {}).items()
    }
    rows: list[WatchlistRow] = []
    for entry in entries:
        company = companies.get(entry.symbol)
        if company is None:
            continue
        score = calculate_alpha_score(company)
        confidence = (
            calculate_analysis_confidence(
                company, score, audits.get(company.symbol.upper())
            )
            if latest_audits is not None
            else None
        )
        rows.append(
            WatchlistRow(
                symbol=company.symbol,
                company_name=company.company_name,
                alpha_score=score.total,
                target_alpha_score=entry.target_alpha_score,
                grade=score.grade,
                decision=confidence.decision if confidence else score.decision,
                note=entry.note,
                target_reached=score.total >= entry.target_alpha_score,
                confidence_score=confidence.total if confidence else None,
                confidence_status=confidence.status if confidence else "",
                calculation_check_status=(
                    confidence.calculation_check_status
                    if confidence
                    else "Kayıt yok"
                ),
            )
        )

    rows.sort(key=lambda row: row.alpha_score, reverse=True)
    return WatchlistSummary(
        rows=rows,
        average_alpha_score=(
            round(sum(row.alpha_score for row in rows) / len(rows), 2)
            if rows
            else 0
        ),
        targets_reached=sum(row.target_reached for row in rows),
    )
