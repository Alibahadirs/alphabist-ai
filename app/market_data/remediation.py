from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from app.market_data.health import MarketHealthItem, MarketHealthSummary


@dataclass(frozen=True)
class MarketHealthTask:
    task_id: str
    symbol: str
    health_status: str
    priority: int
    severity: str
    reason: str
    suggested_action: str
    issue_fingerprint: str
    latest_date: date | None
    age_days: int | None


@dataclass(frozen=True)
class MarketHealthQueueSummary:
    total: int
    critical: int
    high: int
    medium: int
    affected_symbols: int


_ACTIONS = {
    "Bütünlük hatası": (
        "Kayıt bütünlüğünü incele ve kaynağı yeniden doğrula."
    ),
    "Eski": "Gecikmeli piyasa verisini yeniden kontrol et.",
    "Veri yok": "Birincil ve yedek veri sağlayıcılarını kontrol et.",
    "Kısmi": "Eksik veya uyumsuz sağlayıcıyı yeniden doğrula.",
}


def build_market_health_queue(
    summary: MarketHealthSummary,
) -> tuple[MarketHealthTask, ...]:
    tasks = [
        _build_task(item)
        for item in summary.items
        if item.status != "Doğrulandı"
    ]
    tasks.sort(key=lambda task: (-task.priority, task.symbol))
    return tuple(tasks)


def filter_market_health_queue(
    tasks: tuple[MarketHealthTask, ...],
    *,
    query: str = "",
    statuses: set[str] | None = None,
    severities: set[str] | None = None,
    minimum_priority: int = 0,
) -> tuple[MarketHealthTask, ...]:
    normalized_query = query.strip().casefold()
    filtered = [
        task
        for task in tasks
        if task.priority >= minimum_priority
        and (statuses is None or task.health_status in statuses)
        and (severities is None or task.severity in severities)
        and (
            not normalized_query
            or normalized_query
            in " ".join(
                (
                    task.symbol,
                    task.reason,
                    task.suggested_action,
                )
            ).casefold()
        )
    ]
    return tuple(filtered)


def summarize_market_health_queue(
    tasks: tuple[MarketHealthTask, ...],
) -> MarketHealthQueueSummary:
    return MarketHealthQueueSummary(
        total=len(tasks),
        critical=sum(task.severity == "Kritik" for task in tasks),
        high=sum(task.severity == "Yüksek" for task in tasks),
        medium=sum(task.severity == "Orta" for task in tasks),
        affected_symbols=len({task.symbol for task in tasks}),
    )


def _build_task(item: MarketHealthItem) -> MarketHealthTask:
    return MarketHealthTask(
        task_id=_stable_task_id(item.symbol),
        symbol=item.symbol,
        health_status=item.status,
        priority=item.priority,
        severity=_severity(item.priority),
        reason=item.detail,
        suggested_action=_ACTIONS.get(
            item.status,
            "Piyasa veri kaydını incele ve yeniden doğrula.",
        ),
        issue_fingerprint=_issue_fingerprint(item),
        latest_date=item.latest_date,
        age_days=item.age_days,
    )


def _stable_task_id(symbol: str) -> str:
    digest = hashlib.sha256(
        f"market-health:{symbol}".encode("utf-8")
    ).hexdigest()
    return f"market-{digest[:16]}"


def _issue_fingerprint(item: MarketHealthItem) -> str:
    payload = {
        "symbol": item.symbol,
        "status": item.status,
        "priority": item.priority,
        "latest_date": (
            item.latest_date.isoformat() if item.latest_date else None
        ),
        "age_days": item.age_days,
        "integrity_valid": item.integrity_valid,
        "detail": item.detail,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _severity(priority: int) -> str:
    if priority >= 90:
        return "Kritik"
    if priority >= 75:
        return "Yüksek"
    return "Orta"
