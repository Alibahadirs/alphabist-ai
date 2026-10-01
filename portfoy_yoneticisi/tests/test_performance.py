import pandas as pd
import pytest

from pm.analysis.performance import compute_range_performance


def _df_from_close(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.DataFrame({"Close": values}, index=idx)


def test_total_return_and_drawdown():
    df = _df_from_close([100, 110, 90, 105])
    perf = compute_range_performance(df)
    assert perf.total_return_pct == pytest.approx(5.0)
    assert perf.start_price == 100
    assert perf.end_price == 105
    assert perf.trading_days == 4
    assert perf.max_drawdown_pct == pytest.approx((90 - 110) / 110 * 100)


def test_best_and_worst_day():
    df = _df_from_close([100, 120, 100])
    perf = compute_range_performance(df)
    assert perf.best_day_pct == pytest.approx(20.0)
    assert perf.worst_day_pct == pytest.approx(-100 / 6, rel=1e-3)


def test_insufficient_data_raises():
    df = _df_from_close([100.0])
    with pytest.raises(ValueError):
        compute_range_performance(df)
