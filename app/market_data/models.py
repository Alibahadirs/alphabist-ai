from __future__ import annotations

import hashlib
import json
from datetime import date

from pydantic import BaseModel, Field

from app.market_data.diagnostics import MarketDiagnostic


class MarketDiagnosticSnapshot(BaseModel):
    id: int | None = None
    symbol: str = Field(min_length=1, max_length=12)
    primary_available: bool
    secondary_available: bool
    primary_eligible: bool
    secondary_eligible: bool
    primary_price: float | None = None
    secondary_price: float | None = None
    primary_date: date | None = None
    secondary_date: date | None = None
    price_difference_percent: float | None = None
    change_difference_points: float | None = None
    date_gap_days: int | None = None
    cross_verified: bool
    status: str
    fingerprint: str = ""
    created_at: str | None = None


def build_market_diagnostic_snapshot(
    diagnostic: MarketDiagnostic,
) -> MarketDiagnosticSnapshot:
    comparison = diagnostic.comparison
    snapshot = MarketDiagnosticSnapshot(
        symbol=diagnostic.symbol.strip().upper(),
        primary_available=diagnostic.primary.available,
        secondary_available=diagnostic.secondary.available,
        primary_eligible=diagnostic.primary.eligible,
        secondary_eligible=diagnostic.secondary.eligible,
        primary_price=_quote_float(diagnostic.primary.quote, "last"),
        secondary_price=_quote_float(diagnostic.secondary.quote, "last"),
        primary_date=_quote_date(diagnostic.primary.quote),
        secondary_date=_quote_date(diagnostic.secondary.quote),
        price_difference_percent=(
            comparison.price_difference_percent if comparison else None
        ),
        change_difference_points=(
            comparison.change_difference_points if comparison else None
        ),
        date_gap_days=comparison.date_gap_days if comparison else None,
        cross_verified=diagnostic.cross_verified,
        status=diagnostic.status,
    )
    return snapshot.model_copy(
        update={"fingerprint": market_snapshot_fingerprint(snapshot)}
    )


def market_snapshot_fingerprint(
    snapshot: MarketDiagnosticSnapshot,
) -> str:
    payload = snapshot.model_dump(
        mode="json",
        exclude={"id", "fingerprint", "created_at"},
    )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _quote_float(quote: dict | None, field: str) -> float | None:
    value = (quote or {}).get(field)
    return float(value) if value is not None else None


def _quote_date(quote: dict | None) -> date | None:
    value = (quote or {}).get("as_of_date")
    return date.fromisoformat(str(value)) if value else None
