from __future__ import annotations

from dataclasses import dataclass

from app.market_data.models import (
    MarketDiagnosticSnapshot,
    market_snapshot_fingerprint,
)


@dataclass(frozen=True)
class MarketDiagnosticTrend:
    total_records: int
    valid_records: int
    invalid_records: int
    verified_records: int
    verified_rate: float
    consecutive_unverified: int
    latest_status: str
    status_changed: bool
    latest_price_difference_percent: float | None
    price_difference_delta: float | None


def build_market_diagnostic_trend(
    snapshots: list[MarketDiagnosticSnapshot],
) -> MarketDiagnosticTrend:
    valid = [
        item
        for item in snapshots
        if item.fingerprint == market_snapshot_fingerprint(item)
    ]
    verified_records = sum(item.cross_verified for item in valid)
    consecutive_unverified = 0
    for item in reversed(valid):
        if item.cross_verified:
            break
        consecutive_unverified += 1

    latest = valid[-1] if valid else None
    previous = valid[-2] if len(valid) > 1 else None
    latest_difference = (
        latest.price_difference_percent if latest is not None else None
    )
    previous_difference = (
        previous.price_difference_percent if previous is not None else None
    )
    difference_delta = (
        latest_difference - previous_difference
        if latest_difference is not None and previous_difference is not None
        else None
    )
    return MarketDiagnosticTrend(
        total_records=len(snapshots),
        valid_records=len(valid),
        invalid_records=len(snapshots) - len(valid),
        verified_records=verified_records,
        verified_rate=(
            round(verified_records / len(valid) * 100, 2) if valid else 0.0
        ),
        consecutive_unverified=consecutive_unverified,
        latest_status=latest.status if latest is not None else "Kayıt yok",
        status_changed=bool(
            latest is not None
            and previous is not None
            and latest.status != previous.status
        ),
        latest_price_difference_percent=latest_difference,
        price_difference_delta=(
            round(difference_delta, 4)
            if difference_delta is not None
            else None
        ),
    )
