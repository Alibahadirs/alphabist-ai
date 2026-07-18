from collections.abc import Mapping, Sequence
from datetime import date

from app.audit.models import CompanyDataAudit
from app.confidence.service import calculate_analysis_confidence
from app.market_data.freshness import assess_price_freshness
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.technical.models import TechnicalHistoryEntry
from app.watchlist.models import WatchlistEntry, WatchlistRow, WatchlistSummary


def build_watchlist_summary(
    entries: Sequence[WatchlistEntry],
    companies: Mapping[str, FinancialMetrics],
    latest_audits: Mapping[str, CompanyDataAudit] | None = None,
    technical_histories: Mapping[
        str, Sequence[TechnicalHistoryEntry]
    ] | None = None,
    reference_date: date | None = None,
) -> WatchlistSummary:
    audits = {
        symbol.upper(): audit for symbol, audit in (latest_audits or {}).items()
    }
    histories = {
        symbol.upper(): list(history)
        for symbol, history in (technical_histories or {}).items()
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
        decision_ready = (
            confidence.decision_ready if confidence else True
        )
        technical_history = histories.get(company.symbol.upper(), [])
        latest_technical = (
            technical_history[-1] if technical_history else None
        )
        previous_technical = (
            technical_history[-2]
            if len(technical_history) >= 2
            else None
        )
        technical_freshness = assess_price_freshness(
            latest_technical.price_date if latest_technical else None,
            reference_date,
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
                target_reached=(
                    score.total >= entry.target_alpha_score
                    and decision_ready
                ),
                confidence_score=confidence.total if confidence else None,
                confidence_status=confidence.status if confidence else "",
                calculation_check_status=(
                    confidence.calculation_check_status
                    if confidence
                    else "Kayıt yok"
                ),
                decision_ready=decision_ready,
                technical_score=(
                    latest_technical.total_score
                    if latest_technical
                    else None
                ),
                technical_delta=(
                    latest_technical.total_score
                    - previous_technical.total_score
                    if latest_technical and previous_technical
                    else None
                ),
                technical_signal=(
                    latest_technical.signal if latest_technical else ""
                ),
                technical_price_date=(
                    latest_technical.price_date
                    if latest_technical
                    else None
                ),
                technical_status=(
                    technical_freshness.status
                    if latest_technical
                    else "Kayıt yok"
                ),
                technical_current=(
                    bool(latest_technical)
                    and technical_freshness.current
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
        decision_ready_count=sum(row.decision_ready for row in rows),
        current_technical_count=sum(
            row.technical_current for row in rows
        ),
        technical_strengthening_count=sum(
            row.technical_current
            and row.technical_delta is not None
            and row.technical_delta > 0
            for row in rows
        ),
    )
