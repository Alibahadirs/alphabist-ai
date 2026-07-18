from datetime import date

import numpy as np
import pandas as pd

from app.technical.refresh import refresh_technical_scores
import pytest


def _price_frame(end_date: str) -> pd.DataFrame:
    index = pd.date_range(end=end_date, periods=260, freq="D")
    close = np.linspace(50, 100, len(index))
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": np.linspace(1_000_000, 1_500_000, len(index)),
        },
        index=index,
    )


def test_refresh_saves_only_current_aligned_technical_scores():
    frames = {
        "NEW": _price_frame("2026-07-17"),
        "SAME": _price_frame("2026-07-17"),
        "STALE": _price_frame("2026-07-01"),
    }

    def loader(symbol):
        if symbol == "BROKEN":
            raise RuntimeError("Veri sağlayıcı hatası")
        frame = frames[symbol]
        return (
            {
                "last": float(frame["Close"].iloc[-1]),
                "as_of_date": frame.index[-1].date().isoformat(),
                "source": "Yahoo Finance",
            },
            frame,
        )

    saved_symbols = []

    def saver(symbol, price_date, source, score, alignment, methodology):
        saved_symbols.append(symbol)
        return symbol == "NEW"

    summary = refresh_technical_scores(
        ["NEW", "SAME", "STALE", "BROKEN"],
        loader,
        saver,
        "technical-2026.1",
        reference_date=date(2026, 7, 18),
    )

    statuses = {item.symbol: item.status for item in summary.items}
    assert statuses == {
        "NEW": "Kaydedildi",
        "SAME": "Değişmedi",
        "STALE": "Reddedildi",
        "BROKEN": "Hata",
    }
    assert saved_symbols == ["NEW", "SAME"]
    assert summary.total == 4
    assert summary.saved == 1
    assert summary.unchanged == 1
    assert summary.rejected == 1
    assert summary.failed == 1


def test_refresh_normalizes_duplicates_and_limits_batch_size():
    frame = _price_frame("2026-07-17")
    loaded_symbols = []

    def loader(symbol):
        loaded_symbols.append(symbol)
        return (
            {
                "last": float(frame["Close"].iloc[-1]),
                "as_of_date": "2026-07-17",
                "source": "Yahoo Finance",
            },
            frame,
        )

    def saver(*args):
        return True

    summary = refresh_technical_scores(
        [" test ", "TEST"],
        loader,
        saver,
        "technical-2026.1",
        reference_date=date(2026, 7, 18),
    )

    assert summary.total == 1
    assert loaded_symbols == ["TEST"]

    with pytest.raises(ValueError, match="en fazla 20"):
        refresh_technical_scores(
            [f"S{index}" for index in range(21)],
            loader,
            saver,
            "technical-2026.1",
            reference_date=date(2026, 7, 18),
        )
