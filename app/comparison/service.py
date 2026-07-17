from collections.abc import Mapping, Sequence

from app.audit.models import CompanyDataAudit
from app.comparison.models import CompanyComparisonRow, ComparisonSummary
from app.confidence.service import calculate_analysis_confidence
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.technical.engine import calculate_combined_score
from app.technical.models import TechnicalScoreBreakdown


def build_comparison(
    companies: Sequence[FinancialMetrics],
    technical_scores: Mapping[str, TechnicalScoreBreakdown] | None = None,
    latest_audits: Mapping[str, CompanyDataAudit] | None = None,
) -> ComparisonSummary:
    if len(companies) < 2:
        raise ValueError("Karşılaştırma için en az iki şirket seçilmelidir.")

    technical_scores = technical_scores or {}
    audits = {
        symbol.upper(): audit for symbol, audit in (latest_audits or {}).items()
    }
    rows: list[CompanyComparisonRow] = []

    for company in companies:
        alpha = calculate_alpha_score(company)
        confidence = (
            calculate_analysis_confidence(
                company, alpha, audits.get(company.symbol.upper())
            )
            if latest_audits is not None
            else None
        )
        technical = technical_scores.get(company.symbol)
        rows.append(
            CompanyComparisonRow(
                symbol=company.symbol,
                company_name=company.company_name,
                alpha_score=alpha.total,
                grade=alpha.grade,
                decision=confidence.decision if confidence else alpha.decision,
                technical_score=technical.total if technical else None,
                technical_signal=technical.signal if technical else None,
                combined_score=(
                    calculate_combined_score(alpha.total, technical.total)
                    if technical
                    else None
                ),
                atr_percent=technical.atr_percent if technical else None,
                confidence_score=confidence.total if confidence else None,
                confidence_status=confidence.status if confidence else "",
                calculation_check_status=(
                    confidence.calculation_check_status
                    if confidence
                    else "Kayıt yok"
                ),
            )
        )

    rows.sort(
        key=lambda row: (
            row.combined_score
            if row.combined_score is not None
            else row.alpha_score
        ),
        reverse=True,
    )
    combined_values = [
        row.combined_score for row in rows if row.combined_score is not None
    ]
    return ComparisonSummary(
        rows=rows,
        leader_symbol=rows[0].symbol,
        average_alpha_score=round(
            sum(row.alpha_score for row in rows) / len(rows),
            2,
        ),
        average_combined_score=(
            round(sum(combined_values) / len(combined_values), 2)
            if combined_values
            else None
        ),
    )
