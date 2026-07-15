from collections.abc import Mapping, Sequence

from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.watchlist.models import WatchlistEntry, WatchlistRow, WatchlistSummary


def build_watchlist_summary(
    entries: Sequence[WatchlistEntry],
    companies: Mapping[str, FinancialMetrics],
) -> WatchlistSummary:
    rows: list[WatchlistRow] = []
    for entry in entries:
        company = companies.get(entry.symbol)
        if company is None:
            continue
        score = calculate_alpha_score(company)
        rows.append(
            WatchlistRow(
                symbol=company.symbol,
                company_name=company.company_name,
                alpha_score=score.total,
                target_alpha_score=entry.target_alpha_score,
                grade=score.grade,
                decision=score.decision,
                note=entry.note,
                target_reached=score.total >= entry.target_alpha_score,
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
