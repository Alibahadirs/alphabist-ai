import numpy as np
import pandas as pd
import pytest

from pm.analysis.recommendation import (
    Signal,
    build_recommendation,
    indicator_warmup_start,
    signal_from_score_series,
    total_score_series,
)


def _df_from_close(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.DataFrame({"Close": values}, index=idx)


def test_strong_uptrend_yields_al():
    values = [100 * (1.01 ** i) for i in range(80)]
    rec = build_recommendation(_df_from_close(values))
    assert rec.signal == Signal.AL
    assert rec.score > 0.25


def test_strong_downtrend_yields_sat():
    values = [100 * (0.99 ** i) for i in range(80)]
    rec = build_recommendation(_df_from_close(values))
    assert rec.signal == Signal.SAT
    assert rec.score < -0.25


def test_flat_series_yields_tut():
    values = [100.0] * 80
    rec = build_recommendation(_df_from_close(values))
    assert rec.signal == Signal.TUT
    assert rec.score == pytest.approx(0.0, abs=1e-6)


def test_insufficient_history_gives_low_confidence():
    values = [100.0, 101.0, 99.0, 100.5, 100.2]
    rec = build_recommendation(_df_from_close(values))
    assert rec.confidence == "Düşük"


def test_empty_close_raises():
    df = pd.DataFrame({"Close": pd.Series(dtype=float)})
    with pytest.raises(ValueError):
        build_recommendation(df)


def test_score_is_bounded():
    rng = np.random.default_rng(7)
    values = 100 + np.cumsum(rng.normal(0, 5, size=120))
    values = np.clip(values, 1, None)
    rec = build_recommendation(_df_from_close(values))
    assert -1.0 <= rec.score <= 1.0


@pytest.mark.parametrize(
    "values",
    [
        [100 * (1.01**i) for i in range(80)],
        [100 * (0.99**i) for i in range(80)],
        [100.0] * 80,
    ],
)
def test_total_score_series_matches_scalar_recommendation(values):
    df = _df_from_close(values)
    rec = build_recommendation(df)
    series_score = total_score_series(df["Close"]).iloc[-1]
    assert series_score == pytest.approx(rec.score, abs=1e-9)


def test_signal_from_score_series_matches_scalar_signal():
    rng = np.random.default_rng(3)
    values = 100 + np.cumsum(rng.normal(0, 2, size=150))
    values = np.clip(values, 1, None)
    close = _df_from_close(values)["Close"]
    scores = total_score_series(close)
    signals = signal_from_score_series(scores)
    # Son günün vektörize sinyali, tek nokta hesaplamasıyla aynı olmalı.
    rec = build_recommendation(_df_from_close(values))
    assert signals.iloc[-1] == rec.signal.value


def test_indicator_warmup_start_is_none_for_short_series():
    close = pd.Series([100.0, 101.0, 102.0])
    assert indicator_warmup_start(close) is None


def test_indicator_warmup_start_found_for_long_series():
    values = [100.0 + i for i in range(80)]
    close = _df_from_close(values)["Close"]
    warm_start = indicator_warmup_start(close)
    assert warm_start is not None
    assert warm_start in close.index


def test_bollinger_zero_width_is_neutral_not_insufficient():
    values = [100.0] * 80
    rec = build_recommendation(_df_from_close(values))
    bollinger = next(f for f in rec.factors if f.name.startswith("Bollinger"))
    assert bollinger.score == pytest.approx(0.0)
    assert bollinger.detail != "Yetersiz geçmiş veri"
    assert rec.bollinger_pctb is not None


def test_macd_factor_sign_is_symmetric_between_up_and_down_trend():
    up_values = [100 * (1.01**i) for i in range(100)]
    down_values = [100 * (0.99**i) for i in range(100)]
    up_rec = build_recommendation(_df_from_close(up_values))
    down_rec = build_recommendation(_df_from_close(down_values))
    assert up_rec.macd_histogram is not None
    assert down_rec.macd_histogram is not None
    # Simetrik bileşik trendlerde log-fiyat histogramı zıt işaretli olmalı.
    assert (up_rec.macd_histogram > 0) != (down_rec.macd_histogram > 0) or (
        abs(up_rec.macd_histogram) < 1e-6 and abs(down_rec.macd_histogram) < 1e-6
    )


def test_all_five_scoring_factors_present():
    values = [100.0 + i * 0.3 for i in range(90)]
    rec = build_recommendation(_df_from_close(values))
    names = {f.name.split(" (")[0] for f in rec.factors}
    assert names == {"Trend", "MACD", "RSI", "Momentum", "Bollinger Bantları", "Volatilite"}
