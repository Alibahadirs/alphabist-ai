import pandas as pd
import pytest

from pm.analysis.backtest import run_signal_backtest


def _df_from_close(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.DataFrame({"Close": values}, index=idx)


def test_sustained_uptrend_gives_perfect_al_hit_rate():
    values = [100 * (1.01**i) for i in range(250)]
    result = run_signal_backtest(_df_from_close(values), holding_days=20)

    assert result.al.count > 0
    assert result.al.hit_rate_pct == pytest.approx(100.0)
    assert result.al.avg_forward_return_pct > 0
    assert result.sat.count == 0


def test_sustained_downtrend_gives_perfect_sat_hit_rate():
    values = [100 * (0.99**i) for i in range(250)]
    result = run_signal_backtest(_df_from_close(values), holding_days=20)

    assert result.sat.count > 0
    assert result.sat.hit_rate_pct == pytest.approx(100.0)
    assert result.sat.avg_forward_return_pct < 0
    assert result.al.count == 0


def test_flat_series_is_always_tut_with_no_hit_rate():
    values = [100.0] * 150
    result = run_signal_backtest(_df_from_close(values), holding_days=20)

    assert result.al.count == 0
    assert result.sat.count == 0
    assert result.tut.count > 0
    assert result.tut.hit_rate_pct is None
    assert result.tut.avg_forward_return_pct == pytest.approx(0.0)


def test_empty_signal_bucket_has_none_stats():
    values = [100 * (1.01**i) for i in range(250)]
    result = run_signal_backtest(_df_from_close(values), holding_days=20)
    assert result.sat.count == 0
    assert result.sat.hit_rate_pct is None
    assert result.sat.avg_forward_return_pct is None


def test_invalid_holding_days_raises():
    values = [100.0] * 100
    with pytest.raises(ValueError):
        run_signal_backtest(_df_from_close(values), holding_days=0)


def test_insufficient_history_raises():
    values = [100.0, 101.0, 99.0]
    with pytest.raises(ValueError):
        run_signal_backtest(_df_from_close(values), holding_days=20)


def test_holding_days_longer_than_history_raises():
    values = [100.0 + i for i in range(60)]
    with pytest.raises(ValueError):
        run_signal_backtest(_df_from_close(values), holding_days=120)
