from collections.abc import Mapping, Sequence
from hashlib import sha256

from app.data_quality.models import (
    DataQualitySummary,
    DecisionReadinessSummary,
    RemediationQueueRow,
    RemediationQueueSummary,
    RemediationTaskState,
)
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


PROFILE_FINANCIAL_ACTIONS = {
    CompanyProfile.STANDARD: (
        "Gelir, net kâr, faaliyet nakdi ve borç alanlarını resmi "
        "finansal tablodan doğrula"
    ),
    CompanyProfile.BANK: (
        "Net dönem kârı, özkaynak, sermaye yeterliliği ve takipteki "
        "kredi göstergelerini banka raporundan doğrula"
    ),
    CompanyProfile.INSURANCE: (
        "Prim üretimi, teknik sonuç, özkaynak ve sermaye yeterliliği "
        "göstergelerini sigorta raporundan doğrula"
    ),
    CompanyProfile.REIT: (
        "Hasılat, net kâr, portföy/NAD, nakit ve yükümlülük alanlarını "
        "GYO raporundan doğrula"
    ),
    CompanyProfile.FINANCIAL_SERVICES: (
        "Faaliyet geliri, net kâr, özkaynak ve sermaye yapısı "
        "göstergelerini finansal hizmet raporundan doğrula"
    ),
}


def remediation_task_id(symbol: str, task_category: str) -> str:
    normalized = f"{symbol.upper().strip()}|{task_category.strip()}"
    return sha256(normalized.encode("utf-8")).hexdigest()[:20]


def _priority_level(score: int) -> str:
    if score >= 90:
        return "Acil"
    if score >= 70:
        return "Yüksek"
    if score >= 45:
        return "Orta"
    if score > 0:
        return "Düşük"
    return "Hazır"


def build_remediation_queue(
    companies: Sequence[FinancialMetrics],
    readiness: DecisionReadinessSummary,
    data_quality: DataQualitySummary,
    task_states: Mapping[str, RemediationTaskState] | None = None,
) -> RemediationQueueSummary:
    companies_by_symbol: Mapping[str, FinancialMetrics] = {
        company.symbol.upper().strip(): company for company in companies
    }
    quality_by_symbol = {
        row.symbol.upper().strip(): row for row in data_quality.rows
    }
    rows: list[RemediationQueueRow] = []
    states = task_states or {}

    for readiness_row in readiness.rows:
        if readiness_row.financial_ready and readiness_row.technical_ready:
            continue
        company = companies_by_symbol.get(readiness_row.symbol)
        if company is None:
            continue
        quality = quality_by_symbol.get(readiness_row.symbol)
        actions: list[str] = []
        priority_score = readiness_row.priority_score

        if not readiness_row.financial_ready:
            if quality and quality.errors:
                actions.append(
                    "Önce kritik veri ve hesaplama hatalarını düzelt"
                )
                priority_score += 10
            actions.append(PROFILE_FINANCIAL_ACTIONS[company.company_profile])
            if quality and quality.warning_recommended_action != (
                "İşlem gerekmiyor"
            ):
                actions.append(quality.warning_recommended_action)
        if not readiness_row.technical_ready:
            actions.append(
                "Güncel fiyat geçmişini al ve teknik puanı yeniden hesapla"
            )

        if (
            not readiness_row.financial_ready
            and not readiness_row.technical_ready
        ):
            task_category = "Finansal + teknik"
        elif not readiness_row.financial_ready:
            task_category = "Finansal"
        else:
            task_category = "Teknik"

        priority_score = min(priority_score, 100)
        task_id = remediation_task_id(
            readiness_row.symbol,
            task_category,
        )
        state = states.get(task_id)
        rows.append(
            RemediationQueueRow(
                task_id=task_id,
                symbol=readiness_row.symbol,
                company_name=readiness_row.company_name,
                company_profile=company.company_profile,
                priority_score=priority_score,
                priority_level=_priority_level(priority_score),
                task_category=task_category,
                recommended_action="; ".join(dict.fromkeys(actions)),
                blockers=readiness_row.blockers,
                workflow_status=(
                    state.status if state else "Açık"
                ),
                workflow_note=state.note if state else "",
                workflow_updated_at=(
                    state.updated_at if state else None
                ),
            )
        )

    rows.sort(key=lambda row: (-row.priority_score, row.symbol))
    profile_counts: dict[str, int] = {}
    for row in rows:
        profile_counts[row.company_profile.value] = (
            profile_counts.get(row.company_profile.value, 0) + 1
        )

    return RemediationQueueSummary(
        rows=rows,
        total_tasks=len(rows),
        urgent_count=sum(row.priority_level == "Acil" for row in rows),
        high_count=sum(row.priority_level == "Yüksek" for row in rows),
        financial_task_count=sum(
            row.task_category in {"Finansal", "Finansal + teknik"}
            for row in rows
        ),
        technical_task_count=sum(
            row.task_category in {"Teknik", "Finansal + teknik"}
            for row in rows
        ),
        profile_counts=profile_counts,
    )
