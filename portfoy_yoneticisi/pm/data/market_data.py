"""yfinance üzerinden fiyat verisi çekme katmanı.

Tek enstrüman ekranları (Detaylı Analiz, Portföyüm) `fetch_instrument_history*`
fonksiyonlarını kullanır. Çok sayıda enstrümanın aynı anda tarandığı Öneri
Tarama ekranı ise `fetch_instruments_history_with_warmup` ile TEK bir
yfinance toplu indirme çağrısı (yfinance'in kendi iç thread havuzuyla
paralelleştirdiği) üzerinden veri çeker; böylece N ayrı istek yerine tek
istek yapılır ve aynı ticker'ı paylaşan enstrümanlar (ör. ons altın ve gram
altının ortak kullandığı USD/TRY kuru) bir kez indirilir.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

import pandas as pd
import streamlit as st
import yfinance as yf

from ..core.settings import settings
from ..core.symbols import GRAMS_PER_TROY_OUNCE, Instrument

OHLC_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


class MarketDataError(RuntimeError):
    """Fiyat verisi çekilemediğinde veya boş döndüğünde fırlatılır."""


NOT_FOUND_MESSAGE = (
    "piyasa verisi alınamadı (toplu ve tekil denemede de bulunamadı; sembol hatalı/"
    "pasif olabilir ya da sağlayıcı geçici olarak yanıt vermiyor olabilir)."
)


def _clean_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    frame = frame.loc[:, [c for c in OHLC_COLUMNS if c in frame.columns]].copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    frame = frame.dropna(how="all")
    if frame.empty:
        raise MarketDataError(f"'{ticker}' için piyasa verisi bulunamadı.")
    return frame


def _tickers_for_instrument(instrument: Instrument) -> tuple[str, ...]:
    if instrument.kind == "simple":
        if not instrument.ticker:
            raise MarketDataError(f"'{instrument.code}' için ticker tanımlı değil.")
        return (instrument.ticker,)
    if instrument.kind == "gram_try":
        if not instrument.metal_ticker or not instrument.fx_ticker:
            raise MarketDataError(f"'{instrument.code}' için bileşen ticker'lar eksik.")
        return (instrument.metal_ticker, instrument.fx_ticker)
    raise MarketDataError(f"Bilinmeyen enstrüman türü: {instrument.kind}")


def _combine_gram_try(metal: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    joined = metal[["Close"]].join(fx[["Close"]], how="inner", lsuffix="_metal", rsuffix="_fx")
    if joined.empty:
        raise MarketDataError("Emtia ve döviz kuru verileri ortak bir tarihte eşleşmedi.")

    gram_close = (joined["Close_metal"] / GRAMS_PER_TROY_OUNCE) * joined["Close_fx"]
    result = pd.DataFrame(index=joined.index)
    result["Close"] = gram_close
    # Bileşik (hesaplanmış) seri için gün içi OHLC anlamlı olmadığından
    # kapanışla eşitlenir; hacim mevcut değildir.
    result["Open"] = gram_close
    result["High"] = gram_close
    result["Low"] = gram_close
    result["Volume"] = 0
    return result


@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def _download_raw(ticker: str, start: date, end: date) -> pd.DataFrame:
    raw = yf.download(
        ticker,
        start=start,
        end=end + timedelta(days=1),
        progress=False,
        auto_adjust=True,
        threads=False,
    )
    if raw is None or raw.empty:
        raise MarketDataError(f"'{ticker}' için piyasa verisi bulunamadı.")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return _clean_frame(raw, ticker)


@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def _download_raw_many(tickers: tuple[str, ...], start: date, end: date) -> dict[str, pd.DataFrame]:
    """Birden çok ticker'ı yfinance'in toplu indirme moduyla TEK istekte çeker."""

    if not tickers:
        return {}

    raw = yf.download(
        list(tickers),
        start=start,
        end=end + timedelta(days=1),
        progress=False,
        auto_adjust=True,
        group_by="ticker",
        threads=True,
    )
    result: dict[str, pd.DataFrame] = {}
    if raw is None or raw.empty:
        return result

    available = set(raw.columns.get_level_values(0))
    for ticker in tickers:
        if ticker not in available:
            continue
        try:
            result[ticker] = _clean_frame(raw[ticker], ticker)
        except MarketDataError:
            continue
    return result


def fetch_ticker_history(ticker: str, start: date, end: date) -> pd.DataFrame:
    if start > end:
        raise ValueError("Başlangıç tarihi bitiş tarihinden sonra olamaz.")
    return _download_raw(ticker, start, end)


def fetch_many_tickers_history(tickers: Sequence[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    """Birden çok ticker için tekilleştirilmiş, tek seferlik toplu indirme.

    Toplu yanıtta eksik kalan ticker'lar (sağlayıcının o anki toplu istekte
    atladığı, genelde geçici bir durum) tek tek yeniden denenir. Bu ikinci
    denemede de bulunamayan ticker'lar sonuçta yer almaz.
    """

    if start > end:
        raise ValueError("Başlangıç tarihi bitiş tarihinden sonra olamaz.")

    unique = tuple(sorted(set(tickers)))
    result = dict(_download_raw_many(unique, start, end))

    missing = [t for t in unique if t not in result]
    for ticker in missing:
        try:
            result[ticker] = fetch_ticker_history(ticker, start, end)
        except MarketDataError:
            continue
    return result


def fetch_instrument_history(instrument: Instrument, start: date, end: date) -> pd.DataFrame:
    """Verilen enstrüman için [start, end] aralığını kapsayan OHLC verisi döndürür."""

    tickers = _tickers_for_instrument(instrument)
    if instrument.kind == "simple":
        return fetch_ticker_history(tickers[0], start, end)
    # gram_try
    metal = fetch_ticker_history(tickers[0], start, end)
    fx = fetch_ticker_history(tickers[1], start, end)
    return _combine_gram_try(metal, fx)


def fetch_instrument_history_with_warmup(
    instrument: Instrument, start: date, end: date, warmup_days: int | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gösterge ısınma payı eklenmiş tam veri ile, görüntülenecek aralığa kırpılmış veriyi döndürür.

    Dönüş: (padded_df, visible_df)
    """

    warmup = settings.warmup_days if warmup_days is None else warmup_days
    padded_start = start - timedelta(days=warmup)
    padded = fetch_instrument_history(instrument, padded_start, end)
    visible = padded.loc[(padded.index.date >= start) & (padded.index.date <= end)]
    if visible.empty:
        raise MarketDataError(
            "Seçilen tarih aralığında işlem günü bulunamadı (hafta sonu/tatil olabilir)."
        )
    return padded, visible


def fetch_instruments_history_with_warmup(
    instruments: Sequence[Instrument], start: date, end: date, warmup_days: int | None = None
) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    """Birden çok enstrüman için TEK toplu yfinance isteğiyle ısınma paylı veri çeker.

    Aynı ticker'ı paylaşan enstrümanlar (ör. ons altın ile gram altının ortak
    USD/TRY bacağı) yalnızca bir kez indirilir. Dönüş sözlüğü yalnızca verisi
    başarıyla alınan ve seçilen aralıkta işlem günü bulunan enstrümanları
    içerir; `instrument.code` anahtarıyla (padded_df, visible_df) döner.
    """

    warmup = settings.warmup_days if warmup_days is None else warmup_days
    padded_start = start - timedelta(days=warmup)

    instrument_tickers: dict[str, tuple[str, ...]] = {}
    needed_tickers: set[str] = set()
    for inst in instruments:
        try:
            tickers = _tickers_for_instrument(inst)
        except MarketDataError:
            continue
        instrument_tickers[inst.code] = tickers
        needed_tickers.update(tickers)

    raw_by_ticker = fetch_many_tickers_history(tuple(needed_tickers), padded_start, end)

    results: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for inst in instruments:
        tickers = instrument_tickers.get(inst.code)
        if tickers is None:
            continue
        try:
            if inst.kind == "simple":
                padded = raw_by_ticker[tickers[0]]
            else:  # gram_try
                padded = _combine_gram_try(raw_by_ticker[tickers[0]], raw_by_ticker[tickers[1]])
        except (KeyError, MarketDataError):
            continue

        visible = padded.loc[(padded.index.date >= start) & (padded.index.date <= end)]
        if visible.empty:
            continue
        results[inst.code] = (padded, visible)
    return results
