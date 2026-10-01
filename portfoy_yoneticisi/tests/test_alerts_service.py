from datetime import date

import pandas as pd
import pytest

from pm.alerts import service
from pm.portfolio.models import Position


def _df_from_close(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.DataFrame({"Close": values}, index=idx)


def test_build_watch_list_dedupes_portfolio_and_extra_codes(monkeypatch):
    positions = [
        Position(
            instrument_code="THYAO",
            label="THYAO",
            category="Hisse (BIST)",
            quantity=1,
            unit_cost=1,
            purchase_date=date(2024, 1, 1),
        ),
    ]
    monkeypatch.setattr(service, "list_positions", lambda: positions)

    watch = service.build_watch_list(extra_codes=["THYAO", "GARAN"])
    codes = sorted(i.code for i in watch)
    assert codes == ["GARAN", "THYAO"]


def test_run_daily_scan_raises_when_watch_list_empty(monkeypatch):
    monkeypatch.setattr(service, "list_positions", lambda: [])
    with pytest.raises(RuntimeError):
        service.run_daily_scan(extra_codes=())


def test_run_daily_scan_filters_to_actionable_signals(monkeypatch):
    monkeypatch.setattr(service, "list_positions", lambda: [])

    up_values = [100 * (1.01**i) for i in range(80)]
    down_values = [100 * (0.99**i) for i in range(80)]
    flat_values = [100.0] * 80

    history = {
        "UP": (_df_from_close(up_values), _df_from_close(up_values)),
        "DOWN": (_df_from_close(down_values), _df_from_close(down_values)),
        "FLAT": (_df_from_close(flat_values), _df_from_close(flat_values)),
    }
    monkeypatch.setattr(
        service, "fetch_instruments_history_with_warmup", lambda instruments, start, end: history
    )

    result = service.run_daily_scan(extra_codes=["UP", "DOWN", "FLAT"])

    signals = {row.instrument.code: row.recommendation.signal.value for row in result.actionable}
    assert signals == {"UP": "Al", "DOWN": "Sat"}
    assert result.requested == 3
    assert result.evaluated == 3


def test_run_daily_scan_records_errors_for_missing_data(monkeypatch):
    monkeypatch.setattr(service, "list_positions", lambda: [])
    monkeypatch.setattr(
        service, "fetch_instruments_history_with_warmup", lambda instruments, start, end: {}
    )

    result = service.run_daily_scan(extra_codes=["X"])
    assert result.actionable == ()
    assert result.evaluated == 0
    assert len(result.errors) == 1
    assert "X" in result.errors[0]
