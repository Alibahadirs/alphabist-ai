import numpy as np
import pandas as pd
import pytest

from pm.analysis import indicators as ind


def _price_series(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype=float)


def test_sma_basic():
    series = _price_series([1, 2, 3, 4, 5])
    result = ind.sma(series, window=2)
    assert np.isnan(result.iloc[0])
    assert result.iloc[1] == 1.5
    assert result.iloc[-1] == 4.5


def test_rsi_all_gains_is_100():
    series = _price_series([100 + i for i in range(30)])
    result = ind.rsi(series, period=14)
    assert result.iloc[-1] == 100.0


def test_rsi_all_losses_is_0():
    series = _price_series([200 - i for i in range(30)])
    result = ind.rsi(series, period=14)
    assert result.iloc[-1] == 0.0


def test_rsi_flat_series_is_neutral():
    series = _price_series([100.0] * 30)
    result = ind.rsi(series, period=14)
    assert result.iloc[-1] == 50.0


def test_rsi_within_bounds():
    rng = np.random.default_rng(42)
    values = 100 + np.cumsum(rng.normal(0, 1, size=60))
    series = _price_series(values)
    result = ind.rsi(series, period=14).dropna()
    assert (result >= 0).all()
    assert (result <= 100).all()


def test_momentum_positive_move():
    series = _price_series([100] * 5 + [110])
    result = ind.momentum(series, period=5)
    assert round(result.iloc[-1], 2) == 10.0


def test_annualized_volatility_zero_for_flat_series():
    series = _price_series([50.0] * 30)
    result = ind.annualized_volatility(series, window=10)
    assert result.iloc[-1] == 0.0


def test_max_drawdown_pct():
    series = _price_series([100, 120, 90, 95, 130])
    mdd = ind.max_drawdown_pct(series)
    assert round(mdd, 2) == round((90 - 120) / 120 * 100, 2)


def test_max_drawdown_empty_series_is_zero():
    assert ind.max_drawdown_pct(pd.Series(dtype=float)) == 0.0


def test_ema_converges_to_constant_for_flat_series():
    series = _price_series([50.0] * 30)
    result = ind.ema(series, span=10)
    assert result.iloc[-1] == pytest.approx(50.0)


def test_macd_histogram_near_zero_for_steady_log_trend():
    # Sabit yüzdeli bir trendde log-fiyat MACD histogramı sıfıra yakınsamalı
    # (trend ivmelenmiyor); bkz. recommendation.py'deki log-fiyat kullanım notu.
    values = np.log([100 * (1.01**i) for i in range(120)])
    series = _price_series(values)
    _macd_line, _signal_line, histogram = ind.macd(series, fast=12, slow=26, signal=9)
    assert abs(histogram.iloc[-1]) < 0.01


def test_macd_warms_up_with_nan_then_produces_values():
    series = _price_series([100 + i * 0.5 for i in range(60)])
    _macd_line, signal_line, histogram = ind.macd(series)
    assert signal_line.iloc[:30].isna().any()
    assert not pd.isna(histogram.iloc[-1])


def test_bollinger_bands_order_for_varying_series():
    rng = np.random.default_rng(1)
    values = 100 + np.cumsum(rng.normal(0, 1, size=60))
    series = _price_series(values)
    middle, upper, lower = ind.bollinger_bands(series, window=20, num_std=2.0)
    tail = slice(-10, None)
    assert (upper[tail] >= middle[tail]).all()
    assert (middle[tail] >= lower[tail]).all()


def test_bollinger_bands_collapse_for_flat_series():
    series = _price_series([100.0] * 40)
    middle, upper, lower = ind.bollinger_bands(series, window=20, num_std=2.0)
    assert upper.iloc[-1] == pytest.approx(100.0)
    assert lower.iloc[-1] == pytest.approx(100.0)
    assert middle.iloc[-1] == pytest.approx(100.0)
