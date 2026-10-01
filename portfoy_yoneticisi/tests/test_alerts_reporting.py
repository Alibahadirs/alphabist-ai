import pandas as pd

from pm.alerts import reporting, service


def _df_from_close(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.DataFrame({"Close": values}, index=idx)


def _actionable_scan_result(monkeypatch):
    monkeypatch.setattr(service, "list_positions", lambda: [])
    up_values = [100 * (1.01**i) for i in range(80)]
    down_values = [100 * (0.99**i) for i in range(80)]
    history = {
        "UP": (_df_from_close(up_values), _df_from_close(up_values)),
        "DOWN": (_df_from_close(down_values), _df_from_close(down_values)),
    }
    monkeypatch.setattr(
        service, "fetch_instruments_history_with_warmup", lambda instruments, start, end: history
    )
    return service.run_daily_scan(extra_codes=["UP", "DOWN"])


def _empty_scan_result(monkeypatch):
    monkeypatch.setattr(service, "list_positions", lambda: [])
    flat_values = [100.0] * 80
    history = {"FLAT": (_df_from_close(flat_values), _df_from_close(flat_values))}
    monkeypatch.setattr(
        service, "fetch_instruments_history_with_warmup", lambda instruments, start, end: history
    )
    return service.run_daily_scan(extra_codes=["FLAT"])


def test_build_rows_contains_expected_columns(monkeypatch):
    result = _actionable_scan_result(monkeypatch)
    rows = reporting.build_rows(result)
    assert len(rows) == 2
    assert set(rows[0].keys()) == {"Enstrüman", "Kategori", "Fiyat", "Sinyal", "Skor", "Güven"}


def test_build_csv_nonempty_when_actionable(monkeypatch):
    result = _actionable_scan_result(monkeypatch)
    data = reporting.build_csv(result)
    assert data.startswith(b"\xef\xbb\xbf")
    assert b"UP" in data


def test_build_csv_empty_bytes_when_no_actionable(monkeypatch):
    result = _empty_scan_result(monkeypatch)
    assert reporting.build_csv(result) == b""


def test_build_html_lists_signals_and_disclaimer(monkeypatch):
    result = _actionable_scan_result(monkeypatch)
    html = reporting.build_html(result)
    assert "UP" in html
    assert "DOWN" in html
    assert "Al" in html
    assert "Sat" in html
    assert "yatırım tavsiyesi değildir" in html


def test_build_html_handles_no_signals(monkeypatch):
    result = _empty_scan_result(monkeypatch)
    html = reporting.build_html(result)
    assert "bulunmadı" in html
