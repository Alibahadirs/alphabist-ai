from dataclasses import dataclass
from datetime import date

import pandas as pd


DEFAULT_PRICE_TOLERANCE_PERCENT = 0.5
DEFAULT_MAX_DATE_GAP_DAYS = 1


@dataclass(frozen=True)
class MarketDataAlignment:
    valid: bool
    status: str
    quote_date: date | None
    history_date: date | None
    price_difference_percent: float | None


def validate_quote_history_alignment(
    quote: dict,
    history: pd.DataFrame,
    price_tolerance_percent: float = DEFAULT_PRICE_TOLERANCE_PERCENT,
    max_date_gap_days: int = DEFAULT_MAX_DATE_GAP_DAYS,
) -> MarketDataAlignment:
    quote_date_value = quote.get("as_of_date")
    quote_date = (
        date.fromisoformat(str(quote_date_value))
        if quote_date_value
        else None
    )
    if history.empty or "Close" not in history.columns:
        return MarketDataAlignment(
            valid=False,
            status="Fiyat geçmişi eksik",
            quote_date=quote_date,
            history_date=None,
            price_difference_percent=None,
        )

    closes = history["Close"].dropna()
    if closes.empty:
        return MarketDataAlignment(
            valid=False,
            status="Kapanış verisi eksik",
            quote_date=quote_date,
            history_date=None,
            price_difference_percent=None,
        )

    history_date = pd.Timestamp(closes.index[-1]).date()
    quote_price = quote.get("last")
    if quote_date is None or quote_price is None:
        return MarketDataAlignment(
            valid=False,
            status="Son fiyat tarihi veya değeri eksik",
            quote_date=quote_date,
            history_date=history_date,
            price_difference_percent=None,
        )

    history_price = float(closes.iloc[-1])
    quote_price = float(quote_price)
    price_difference_percent = (
        abs(quote_price - history_price) / abs(quote_price) * 100
        if quote_price
        else (0 if history_price == 0 else 100)
    )
    date_gap_days = abs((quote_date - history_date).days)
    if date_gap_days > max_date_gap_days:
        return MarketDataAlignment(
            valid=False,
            status=f"Fiyat tarihleri {date_gap_days} gün farklı",
            quote_date=quote_date,
            history_date=history_date,
            price_difference_percent=round(
                price_difference_percent, 4
            ),
        )
    if price_difference_percent > price_tolerance_percent:
        return MarketDataAlignment(
            valid=False,
            status=(
                "Son fiyat ile grafik kapanışı "
                f"%{price_difference_percent:.2f} farklı"
            ),
            quote_date=quote_date,
            history_date=history_date,
            price_difference_percent=round(
                price_difference_percent, 4
            ),
        )
    return MarketDataAlignment(
        valid=True,
        status="Fiyat ve grafik verisi uyumlu",
        quote_date=quote_date,
        history_date=history_date,
        price_difference_percent=round(price_difference_percent, 4),
    )
