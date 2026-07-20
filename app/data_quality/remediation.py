from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json

from app.data_quality.models import (
    DataQualitySummary,
    DecisionReadinessSummary,
    RemediationQueueRow,
    RemediationQueueSummary,
    RemediationTaskState,
    RemediationTaskStatus,
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


@dataclass(frozen=True)
class RemediationTransitionResult:
    allowed: bool
    message: str


@dataclass(frozen=True)
class RemediationEventChainResult:
    valid: bool
    status: str
    invalid_event_id: int | None = None


def remediation_event_hash(
    *,
    previous_event_hash: str,
    task_id: str,
    symbol: str,
    task_category: str,
    previous_status: RemediationTaskStatus | str | None,
    new_status: RemediationTaskStatus | str,
    note: str,
    issue_fingerprint: str,
) -> str:
    payload = {
        "previous_event_hash": previous_event_hash,
        "task_id": task_id,
        "symbol": symbol.upper().strip(),
        "task_category": task_category,
        "previous_status": (
            previous_status.value
            if isinstance(previous_status, RemediationTaskStatus)
            else previous_status
        ),
        "new_status": (
            new_status.value
            if isinstance(new_status, RemediationTaskStatus)
            else new_status
        ),
        "note": note,
        "issue_fingerprint": issue_fingerprint,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def verify_remediation_event_chain(
    events: Sequence,
) -> RemediationEventChainResult:
    previous_hash = ""
    for event in events:
        expected_hash = remediation_event_hash(
            previous_event_hash=previous_hash,
            task_id=event.task_id,
            symbol=event.symbol,
            task_category=event.task_category,
            previous_status=event.previous_status,
            new_status=event.new_status,
            note=event.note,
            issue_fingerprint=event.issue_fingerprint,
        )
        if (
            event.previous_event_hash != previous_hash
            or event.event_hash != expected_hash
        ):
            return RemediationEventChainResult(
                valid=False,
                status="Görev olay zinciri bütünlüğü bozuk.",
                invalid_event_id=event.id,
            )
        previous_hash = event.event_hash
    return RemediationEventChainResult(
        valid=True,
        status=(
            "Görev olay zinciri doğrulandı."
            if events
            else "Doğrulanacak görev olayı yok."
        ),
    )


def validate_remediation_transition(
    current: RemediationTaskStatus,
    requested: RemediationTaskStatus,
) -> RemediationTransitionResult:
    if requested == RemediationTaskStatus.REOPEN_REQUIRED:
        return RemediationTransitionResult(
            allowed=False,
            message="Yeniden açılmalı durumu yalnız sistem tarafından atanır.",
        )
    if current == requested:
        return RemediationTransitionResult(
            allowed=True,
            message="Görev durumu korunarak not güncellenebilir.",
        )
    if current in {
        RemediationTaskStatus.COMPLETED,
        RemediationTaskStatus.DISMISSED,
        RemediationTaskStatus.REOPEN_REQUIRED,
    } and requested not in {
        RemediationTaskStatus.OPEN,
        RemediationTaskStatus.IN_PROGRESS,
    }:
        return RemediationTransitionResult(
            allowed=False,
            message=(
                "Kapalı veya kanıtı değişmiş görev önce yeniden açılmalıdır."
            ),
        )
    return RemediationTransitionResult(
        allowed=True,
        message="Görev durumu değiştirilebilir.",
    )


def remediation_task_id(symbol: str, task_category: str) -> str:
    normalized = f"{symbol.upper().strip()}|{task_category.strip()}"
    return sha256(normalized.encode("utf-8")).hexdigest()[:20]


def remediation_issue_fingerprint(
    symbol: str,
    company_profile: CompanyProfile,
    task_category: str,
    recommended_action: str,
    blockers: Sequence[str],
) -> str:
    payload = {
        "symbol": symbol.upper().strip(),
        "company_profile": company_profile.value,
        "task_category": task_category.strip(),
        "recommended_action": recommended_action.strip(),
        "blockers": sorted(
            blocker.strip() for blocker in blockers if blocker.strip()
        ),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


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
        recommended_action = "; ".join(dict.fromkeys(actions))
        task_id = remediation_task_id(
            readiness_row.symbol,
            task_category,
        )
        issue_fingerprint = remediation_issue_fingerprint(
            readiness_row.symbol,
            company.company_profile,
            task_category,
            recommended_action,
            readiness_row.blockers,
        )
        state = states.get(task_id)
        issue_fingerprint_matches = bool(
            not state
            or state.status == RemediationTaskStatus.OPEN
            or (
                state.issue_fingerprint
                and state.issue_fingerprint == issue_fingerprint
            )
        )
        workflow_status = state.status if state else RemediationTaskStatus.OPEN
        if state and not issue_fingerprint_matches:
            workflow_status = RemediationTaskStatus.REOPEN_REQUIRED
        rows.append(
            RemediationQueueRow(
                task_id=task_id,
                issue_fingerprint=issue_fingerprint,
                symbol=readiness_row.symbol,
                company_name=readiness_row.company_name,
                company_profile=company.company_profile,
                priority_score=priority_score,
                priority_level=_priority_level(priority_score),
                task_category=task_category,
                recommended_action=recommended_action,
                blockers=readiness_row.blockers,
                workflow_status=workflow_status,
                workflow_note=state.note if state else "",
                workflow_updated_at=(
                    state.updated_at if state else None
                ),
                issue_fingerprint_matches=issue_fingerprint_matches,
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
        open_count=sum(
            row.workflow_status == RemediationTaskStatus.OPEN
            for row in rows
        ),
        in_progress_count=sum(
            row.workflow_status == RemediationTaskStatus.IN_PROGRESS
            for row in rows
        ),
        completed_count=sum(
            row.workflow_status == RemediationTaskStatus.COMPLETED
            for row in rows
        ),
        dismissed_count=sum(
            row.workflow_status == RemediationTaskStatus.DISMISSED
            for row in rows
        ),
        reopen_required_count=sum(
            row.workflow_status
            == RemediationTaskStatus.REOPEN_REQUIRED
            for row in rows
        ),
    )
