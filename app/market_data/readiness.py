from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.market_data.freshness import PriceFreshness, assess_price_freshness
from app.market_data.policy import get_source_policy, quote_source_is_eligible
from app.market_data.validation import (
    MarketDataAlignment,
    validate_quote_history_alignment,
)


@dataclass(frozen=True)
class QuoteReadiness:
    ready: bool
    status: str
    source_eligible: bool
    freshness: PriceFreshness
    alignment: MarketDataAlignment | None


def assess_quote_readiness(
    quote: dict,
    history: pd.DataFrame | None = None,
    reference_date: date | None = None,
) -> QuoteReadiness:
    quote_date = _quote_date(quote)
    freshness = assess_price_freshness(quote_date, reference_date)
    source_eligible = quote_source_is_eligible(quote)
    alignment = (
        validate_quote_history_alignment(quote, history)
        if history is not None
        else None
    )
    reasons = []
    if not source_eligible:
        reasons.append(get_source_policy(quote.get("source")).disclosure)
    if not freshness.current:
        reasons.append(freshness.status)
    if alignment is not None and not alignment.valid:
        reasons.append(alignment.status)
    return QuoteReadiness(
        ready=(
            source_eligible
            and freshness.current
            and (alignment is None or alignment.valid)
        ),
        status="Karara uygun gecikmeli veri" if not reasons else "; ".join(reasons),
        source_eligible=source_eligible,
        freshness=freshness,
        alignment=alignment,
    )


def _quote_date(quote: dict) -> date | None:
    value = quote.get("as_of_date")
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
