from datetime import date

import pandas as pd
import pytest

from pm.core.symbols import Instrument
from pm.data import market_data as md


def _df(dates, closes):
    idx = pd.to_datetime(dates)
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 0}, index=idx
    )


def test_tickers_for_instrument_simple():
    inst = Instrument(code="X", label="X", category="Hisse (BIST)", kind="simple", ticker="X.IS")
    assert md._tickers_for_instrument(inst) == ("X.IS",)


def test_tickers_for_instrument_gram_try():
    inst = Instrument(
        code="G",
        label="G",
        category="Kıymetli Maden",
        kind="gram_try",
        metal_ticker="GC=F",
        fx_ticker="USDTRY=X",
    )
    assert md._tickers_for_instrument(inst) == ("GC=F", "USDTRY=X")


def test_tickers_for_instrument_missing_ticker_raises():
    inst = Instrument(code="X", label="X", category="Hisse (BIST)", kind="simple", ticker=None)
    with pytest.raises(md.MarketDataError):
        md._tickers_for_instrument(inst)


def test_combine_gram_try_computes_gram_price():
    metal = _df(["2024-01-01", "2024-01-02"], [3100.0, 3200.0])  # USD/ons
    fx = _df(["2024-01-01", "2024-01-02"], [30.0, 31.0])  # USD/TRY
    result = md._combine_gram_try(metal, fx)
    expected_day1 = (3100.0 / md.GRAMS_PER_TROY_OUNCE) * 30.0
    assert result["Close"].iloc[0] == pytest.approx(expected_day1)
    assert (result["Open"] == result["Close"]).all()
    assert (result["Volume"] == 0).all()


def test_fetch_instruments_history_batches_in_a_single_call_and_dedupes(monkeypatch):
    calls = []

    def fake_fetch_many(tickers, start, end):
        calls.append(tuple(sorted(tickers)))
        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        return {
            "THYAO.IS": _df(dates, [100.0, 101.0, 102.0]),
            "GC=F": _df(dates, [3100.0, 3150.0, 3200.0]),
            "USDTRY=X": _df(dates, [30.0, 30.5, 31.0]),
        }

    monkeypatch.setattr(md, "fetch_many_tickers_history", fake_fetch_many)

    thyao = Instrument(code="THYAO", label="THYAO", category="Hisse (BIST)", kind="simple", ticker="THYAO.IS")
    gram_altin = Instrument(
        code="GRAMALTIN",
        label="Gram Altın",
        category="Kıymetli Maden",
        kind="gram_try",
        metal_ticker="GC=F",
        fx_ticker="USDTRY=X",
    )

    results = md.fetch_instruments_history_with_warmup(
        [thyao, gram_altin], start=date(2024, 1, 2), end=date(2024, 1, 3), warmup_days=0
    )

    assert set(results.keys()) == {"THYAO", "GRAMALTIN"}
    assert len(calls) == 1  # tek seferde toplu çağrı yapılmalı
    assert calls[0] == ("GC=F", "THYAO.IS", "USDTRY=X")  # GC=F sadece bir kez istenir

    _padded, visible = results["THYAO"]
    assert len(visible) == 2  # 2024-01-02 ve 2024-01-03


def test_fetch_instruments_history_skips_missing_data(monkeypatch):
    monkeypatch.setattr(md, "fetch_many_tickers_history", lambda tickers, start, end: {})

    inst = Instrument(code="X", label="X", category="Hisse (BIST)", kind="simple", ticker="X.IS")
    results = md.fetch_instruments_history_with_warmup([inst], date(2024, 1, 1), date(2024, 1, 2))
    assert results == {}


def test_fetch_many_tickers_history_retries_ticker_missing_from_batch(monkeypatch):
    start, end = date(2024, 1, 1), date(2024, 1, 3)
    batch_result = {"THYAO.IS": _df(["2024-01-01", "2024-01-02"], [100.0, 101.0])}
    monkeypatch.setattr(md, "_download_raw_many", lambda tickers, s, e: dict(batch_result))

    individual_calls = []

    def fake_single(ticker, s, e):
        individual_calls.append(ticker)
        return _df(["2024-01-01", "2024-01-02"], [50.0, 51.0])

    monkeypatch.setattr(md, "fetch_ticker_history", fake_single)

    result = md.fetch_many_tickers_history(["THYAO.IS", "KOZAL.IS"], start, end)

    assert individual_calls == ["KOZAL.IS"]  # yalnızca eksik olan tekil denenir
    assert set(result.keys()) == {"THYAO.IS", "KOZAL.IS"}
    assert result["KOZAL.IS"]["Close"].iloc[0] == 50.0


def test_fetch_many_tickers_history_drops_ticker_failing_both_attempts(monkeypatch):
    start, end = date(2024, 1, 1), date(2024, 1, 3)
    monkeypatch.setattr(md, "_download_raw_many", lambda tickers, s, e: {})

    def fake_single(ticker, s, e):
        raise md.MarketDataError("yok")

    monkeypatch.setattr(md, "fetch_ticker_history", fake_single)

    result = md.fetch_many_tickers_history(["KOZAL.IS"], start, end)
    assert result == {}


def test_instrument_scan_error_message_mentions_both_attempts(monkeypatch):
    # fetch_instruments_history_with_warmup -> fetch_many_tickers_history zincirinde
    # her iki deneme de başarısız olduğunda çağıranın ürettiği mesaj netleştirilmiş olmalı.
    assert "tekil" in md.NOT_FOUND_MESSAGE
    assert "toplu" in md.NOT_FOUND_MESSAGE
