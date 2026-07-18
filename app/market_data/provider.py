import pandas as pd
import yfinance as yf

from app.core.exceptions import DataProviderError
from app.technical.engine import enrich_history


def yahoo_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    return normalized if normalized.endswith(".IS") else f"{normalized}.IS"


def get_quote(symbol: str) -> dict[str, float | str | None]:
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
    change = None if previous is None else last - previous
    change_percent = None if not previous else change / previous * 100
    as_of_date = pd.Timestamp(closes.index[-1]).date().isoformat()
    return {
        "last": last,
        "previous": previous,
        "change": change,
        "change_percent": change_percent,
        "as_of_date": as_of_date,
        "source": "Yahoo Finance",
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
