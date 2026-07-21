from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from app.market_data.borsa_api import get_borsa_api_quote
from app.market_data.comparison import QuoteComparison, compare_quotes
from app.market_data.freshness import assess_price_freshness
from app.market_data.policy import quote_source_is_eligible
from app.market_data.provider import get_yahoo_quote


QuoteLoader = Callable[[str], dict]


@dataclass(frozen=True)
class ProviderDiagnostic:
    provider: str
    available: bool
    eligible: bool
    freshness_status: str
    quote: dict | None
    error: str | None


@dataclass(frozen=True)
class MarketDiagnostic:
    symbol: str
    primary: ProviderDiagnostic
    secondary: ProviderDiagnostic
    comparison: QuoteComparison | None
    cross_verified: bool
    status: str


def diagnose_market_data(
    symbol: str,
    reference_date: date | None = None,
    yahoo_loader: QuoteLoader = get_yahoo_quote,
    borsa_loader: QuoteLoader = get_borsa_api_quote,
) -> MarketDiagnostic:
    normalized_symbol = symbol.strip().upper()
    primary = _run_provider(
        "Yahoo Finance",
        normalized_symbol,
        yahoo_loader,
        reference_date,
    )
    secondary = _run_provider(
        "borsa-api",
        normalized_symbol,
        borsa_loader,
        reference_date,
    )
    comparison = (
        compare_quotes(primary.quote, secondary.quote)
        if primary.quote is not None and secondary.quote is not None
        else None
    )
    cross_verified = bool(
        primary.eligible
        and secondary.eligible
        and comparison is not None
        and comparison.valid
    )
    if cross_verified:
        status = "İki gecikmeli sağlayıcı çapraz doğrulandı"
    elif comparison is not None:
        status = f"Sağlayıcı uyumsuzluğu: {comparison.status}"
    elif primary.available or secondary.available:
        status = "Yalnız bir sağlayıcıdan veri alınabildi"
    else:
        status = "Hiçbir sağlayıcıdan veri alınamadı"
    return MarketDiagnostic(
        symbol=normalized_symbol,
        primary=primary,
        secondary=secondary,
        comparison=comparison,
        cross_verified=cross_verified,
        status=status,
    )


def _run_provider(
    provider: str,
    symbol: str,
    loader: QuoteLoader,
    reference_date: date | None,
) -> ProviderDiagnostic:
    try:
        quote = loader(symbol)
    except Exception as exc:
        return ProviderDiagnostic(
            provider=provider,
            available=False,
            eligible=False,
            freshness_status="Veri alınamadı",
            quote=None,
            error=str(exc),
        )

    quote_date = _quote_date(quote)
    freshness = assess_price_freshness(quote_date, reference_date)
    eligible = freshness.current and quote_source_is_eligible(quote)
    return ProviderDiagnostic(
        provider=provider,
        available=True,
        eligible=eligible,
        freshness_status=freshness.status,
        quote=quote,
        error=None,
    )


def _quote_date(quote: dict) -> date | None:
    value = quote.get("as_of_date")
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
