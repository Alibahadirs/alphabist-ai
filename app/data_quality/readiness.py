from collections.abc import Mapping, Sequence

from app.confidence.models import AnalysisConfidence
from app.data_quality.models import (
    DecisionReadinessRow,
    DecisionReadinessSummary,
)
from app.scoring.models import FinancialMetrics
from app.technical.models import TechnicalQualitySummary


READY_STATUS = "Karara hazır"
FINANCIAL_STATUS = "Finansal doğrulama gerekli"
TECHNICAL_STATUS = "Teknik yenileme gerekli"
COMBINED_STATUS = "Finansal ve teknik doğrulama gerekli"
READINESS_STATUS_OPTIONS = [
    READY_STATUS,
    FINANCIAL_STATUS,
    TECHNICAL_STATUS,
    COMBINED_STATUS,
]
PRIORITY_LEVEL_OPTIONS = ["Acil", "Yüksek", "Orta", "Düşük", "Hazır"]


def _readiness_priority(
    financial_ready: bool,
    technical_ready: bool,
    *,
    financial_evaluation_missing: bool,
    technical_evaluation_missing: bool,
) -> tuple[int, str]:
    score = 0
    if not financial_ready:
        score += 55
    if not technical_ready:
        score += 30
    if financial_evaluation_missing:
        score += 10
    if technical_evaluation_missing:
        score += 5
    score = min(score, 100)

    if score >= 90:
        level = "Acil"
    elif score >= 70:
        level = "Yüksek"
    elif score >= 45:
        level = "Orta"
    elif score > 0:
        level = "Düşük"
    else:
        level = "Hazır"
    return score, level


def _readiness_status(
    financial_ready: bool,
    technical_ready: bool,
) -> tuple[str, str]:
    if financial_ready and technical_ready:
        return READY_STATUS, "İzlemeye devam et"
    if not financial_ready and technical_ready:
        return FINANCIAL_STATUS, "Finansal raporu ve kaynakları doğrula"
    if financial_ready and not technical_ready:
        return TECHNICAL_STATUS, "Teknik kaydı yenile"
    return (
        COMBINED_STATUS,
        "Önce finansal raporu doğrula, ardından teknik kaydı yenile",
    )


def build_decision_readiness_summary(
    companies: Sequence[FinancialMetrics],
    confidences: Mapping[str, AnalysisConfidence],
    technical_quality: TechnicalQualitySummary,
) -> DecisionReadinessSummary:
    normalized_confidences = {
        symbol.upper().strip(): confidence
        for symbol, confidence in confidences.items()
    }
    technical_rows = {
        row.symbol.upper().strip(): row
        for row in technical_quality.rows
    }
    rows: list[DecisionReadinessRow] = []

    for company in companies:
        symbol = company.symbol.upper().strip()
        confidence = normalized_confidences.get(symbol)
        technical = technical_rows.get(symbol)
        financial_ready = bool(confidence and confidence.decision_ready)
        technical_ready = bool(technical and technical.current)
        status, action = _readiness_status(
            financial_ready,
            technical_ready,
        )
        priority_score, priority_level = _readiness_priority(
            financial_ready,
            technical_ready,
            financial_evaluation_missing=confidence is None,
            technical_evaluation_missing=technical is None,
        )

        blockers: list[str] = []
        if not financial_ready:
            if confidence and confidence.reasons:
                blockers.append(confidence.reasons[0])
            else:
                blockers.append("Finansal güven değerlendirmesi bulunmuyor.")
        if not technical_ready:
            blockers.append(
                f"Teknik kayıt: {technical.status}"
                if technical
                else "Teknik kayıt bulunmuyor."
            )

        rows.append(
            DecisionReadinessRow(
                symbol=symbol,
                company_name=company.company_name,
                financial_ready=financial_ready,
                technical_ready=technical_ready,
                status=status,
                recommended_action=action,
                blockers=blockers,
                priority_score=priority_score,
                priority_level=priority_level,
            )
        )

    priority = {
        COMBINED_STATUS: 0,
        FINANCIAL_STATUS: 1,
        TECHNICAL_STATUS: 2,
        READY_STATUS: 3,
    }
    rows.sort(
        key=lambda row: (
            -row.priority_score,
            priority[row.status],
            row.symbol,
        )
    )
    return DecisionReadinessSummary(
        rows=rows,
        total=len(rows),
        ready_count=sum(row.status == READY_STATUS for row in rows),
        financial_only_count=sum(
            row.status == FINANCIAL_STATUS for row in rows
        ),
        technical_only_count=sum(
            row.status == TECHNICAL_STATUS for row in rows
        ),
        combined_issue_count=sum(
            row.status == COMBINED_STATUS for row in rows
        ),
    )
