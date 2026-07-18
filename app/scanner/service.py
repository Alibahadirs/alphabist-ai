from collections.abc import Mapping, Sequence
from datetime import date

from app.audit.models import CompanyDataAudit
from app.confidence.service import calculate_analysis_confidence
from app.scanner.models import ScannerFilters, ScannerRow, ScannerSummary
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile
from app.technical.models import TechnicalHistoryEntry
from app.technical.quality import assess_technical_record


def scan_companies(
    companies: Sequence[FinancialMetrics],
    filters: ScannerFilters,
    latest_audits: Mapping[str, CompanyDataAudit] | None = None,
    technical_histories: Mapping[
        str, Sequence[TechnicalHistoryEntry]
    ] | None = None,
    reference_date: date | None = None,
) -> ScannerSummary:
    audits = {
        symbol.upper(): audit for symbol, audit in (latest_audits or {}).items()
    }
    histories = {
        symbol.upper(): list(history)
        for symbol, history in (technical_histories or {}).items()
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
        technical_history = histories.get(company.symbol.upper(), [])
        latest_technical = (
            technical_history[-1] if technical_history else None
        )
        previous_technical = (
            technical_history[-2]
            if len(technical_history) >= 2
            else None
        )
        technical_health = assess_technical_record(
            latest_technical,
            reference_date,
        )
        technical_current = technical_health.current
        technical_delta = (
            latest_technical.total_score - previous_technical.total_score
            if latest_technical and previous_technical
            else None
        )
        financial_decision_ready = (
            confidence.decision_ready if confidence else True
        )
        combined_decision_ready = (
            financial_decision_ready and technical_current
        )
        technical_filter_active = (
            filters.current_technical_only
            or filters.minimum_technical_score is not None
            or filters.technical_strengthening_only
            or filters.combined_decision_ready_only
        )
        if technical_filter_active and not technical_current:
            continue
        if (
            filters.minimum_technical_score is not None
            and latest_technical is not None
            and latest_technical.total_score
            < filters.minimum_technical_score
        ):
            continue
        if (
            filters.technical_strengthening_only
            and (technical_delta is None or technical_delta <= 0)
        ):
            continue
        if (
            filters.decision_ready_only
            and not financial_decision_ready
        ):
            continue
        if (
            filters.combined_decision_ready_only
            and not combined_decision_ready
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
                decision_ready=financial_decision_ready,
                combined_decision_ready=combined_decision_ready,
                technical_score=(
                    latest_technical.total_score
                    if latest_technical
                    else None
                ),
                technical_delta=technical_delta,
                technical_signal=(
                    latest_technical.signal if latest_technical else ""
                ),
                technical_price_date=(
                    latest_technical.price_date
                    if latest_technical
                    else None
                ),
                technical_status=(
                    technical_health.status
                    if latest_technical
                    else technical_health.status
                ),
                technical_current=technical_current,
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
        current_technical_count=sum(
            row.technical_current for row in rows
        ),
        combined_decision_ready_count=sum(
            row.combined_decision_ready for row in rows
        ),
    )
