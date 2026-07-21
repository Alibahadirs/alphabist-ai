import pandas as pd
import yfinance as yf

from app.core.exceptions import DataProviderError
from app.market_data.borsa_api import get_borsa_api_quote
from app.market_data.quote import normalize_quote_values
from app.technical.engine import enrich_history


def yahoo_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    return normalized if normalized.endswith(".IS") else f"{normalized}.IS"


def get_quote(symbol: str) -> dict[str, float | str | bool | None]:
    try:
        return get_yahoo_quote(symbol)
    except DataProviderError as yahoo_error:
        try:
            quote = get_borsa_api_quote(symbol)
        except DataProviderError as borsa_error:
            raise DataProviderError(
                "Fiyat verisi alınamadı. "
                f"Yahoo Finance: {yahoo_error} | borsa-api: {borsa_error}"
            ) from borsa_error
        return {**quote, "fallback_used": True}


def get_yahoo_quote(symbol: str) -> dict[str, float | str | bool | None]:
    try:
        history = yf.Ticker(yahoo_symbol(symbol)).history(
            period="5d",
            interval="1d",
            auto_adjust=False,
        )
    except Exception as exc:
        raise DataProviderError(f"Fiyat verisi alınamadı: {exc}") from exc

    if history.empty:
        raise DataProviderError("Fiyat verisi bulunamadı.")

    closes = history["Close"].dropna()
    last = float(closes.iloc[-1])
    previous = float(closes.iloc[-2]) if len(closes) > 1 else None
    normalized = normalize_quote_values(last=last, previous=previous)
    as_of_date = pd.Timestamp(closes.index[-1]).date().isoformat()
    return {
        "last": normalized.last,
        "previous": normalized.previous,
        "change": normalized.change,
        "change_percent": normalized.change_percent,
        "as_of_date": as_of_date,
        "source": "Yahoo Finance",
        "data_mode": "delayed",
        "official": False,
        "percent_corrected": normalized.percent_corrected,
        "fallback_used": False,
    }


def get_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    try:
        frame = yf.download(
            yahoo_symbol(symbol),
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        raise DataProviderError(f"Tarihsel fiyat verisi alınamadı: {exc}") from exc

    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    if frame.empty:
        raise DataProviderError("Tarihsel fiyat verisi bulunamadı.")

    price_columns = ["Open", "High", "Low", "Close", "Volume"]
    frame = frame[price_columns].dropna(subset=["Close"])
    return enrich_history(frame)
