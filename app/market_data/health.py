from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.market_data.freshness import assess_price_freshness
from app.market_data.models import (
    MarketDiagnosticSnapshot,
    market_snapshot_fingerprint,
)


@dataclass(frozen=True)
class MarketHealthItem:
    symbol: str
    status: str
    priority: int
    latest_date: date | None
    age_days: int | None
    cross_verified: bool
    integrity_valid: bool
    detail: str


@dataclass(frozen=True)
class MarketHealthSummary:
    items: tuple[MarketHealthItem, ...]
    verified: int
    partial: int
    unavailable: int
    stale: int
    invalid: int

    @property
    def total(self) -> int:
        return len(self.items)


def build_market_health_summary(
    symbols: list[str],
    snapshots: list[MarketDiagnosticSnapshot],
    reference_date: date | None = None,
) -> MarketHealthSummary:
    normalized_symbols = sorted(
        {symbol.strip().upper() for symbol in symbols if symbol.strip()}
    )
    latest_by_symbol = {
        snapshot.symbol.strip().upper(): snapshot for snapshot in snapshots
    }
    items = [
        _build_health_item(
            symbol,
            latest_by_symbol.get(symbol),
            reference_date,
        )
        for symbol in normalized_symbols
    ]
    items.sort(key=lambda item: (-item.priority, item.symbol))
    return MarketHealthSummary(
        items=tuple(items),
        verified=sum(item.status == "Doğrulandı" for item in items),
        partial=sum(item.status == "Kısmi" for item in items),
        unavailable=sum(item.status == "Veri yok" for item in items),
        stale=sum(item.status == "Eski" for item in items),
        invalid=sum(item.status == "Bütünlük hatası" for item in items),
    )


def _build_health_item(
    symbol: str,
    snapshot: MarketDiagnosticSnapshot | None,
    reference_date: date | None,
) -> MarketHealthItem:
    if snapshot is None:
        return MarketHealthItem(
            symbol=symbol,
            status="Veri yok",
            priority=80,
            latest_date=None,
            age_days=None,
            cross_verified=False,
            integrity_valid=True,
            detail="Henüz piyasa veri kontrolü kaydedilmedi.",
        )

    integrity_valid = (
        snapshot.fingerprint == market_snapshot_fingerprint(snapshot)
    )
    latest_date = _latest_quote_date(snapshot)
    freshness = assess_price_freshness(latest_date, reference_date)
    if not integrity_valid:
        status, priority = "Bütünlük hatası", 100
        detail = "Kayıt içeriği parmak iziyle eşleşmiyor."
    elif not snapshot.primary_available and not snapshot.secondary_available:
        status, priority = "Veri yok", 80
        detail = snapshot.status
    elif not freshness.current:
        status, priority = "Eski", 90
        detail = freshness.status
    elif snapshot.cross_verified:
        status, priority = "Doğrulandı", 0
        detail = snapshot.status
    elif snapshot.primary_available or snapshot.secondary_available:
        status, priority = "Kısmi", 50
        detail = snapshot.status
    else:
        status, priority = "Veri yok", 80
        detail = snapshot.status
    return MarketHealthItem(
        symbol=symbol,
        status=status,
        priority=priority,
        latest_date=latest_date,
        age_days=freshness.age_days,
        cross_verified=snapshot.cross_verified,
        integrity_valid=integrity_valid,
        detail=detail,
    )


def _latest_quote_date(
    snapshot: MarketDiagnosticSnapshot,
) -> date | None:
    available_dates = [
        value
        for value in (snapshot.primary_date, snapshot.secondary_date)
        if value is not None
    ]
    return max(available_dates) if available_dates else None
