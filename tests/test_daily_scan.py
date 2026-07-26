from datetime import datetime

import numpy as np
import pandas as pd

from app.daily_scan.analysis import assess_symbol
from app.daily_scan.models import DailyScanResult
from app.daily_scan.reporting import build_csv, build_html
from app.daily_scan.runner import _config
from app.daily_scan import provider


def _history() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=100, freq="B")
    close = np.linspace(80, 110, len(index)) + np.sin(np.arange(len(index)))
    return pd.DataFrame({
        "Open": close - 0.2, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": np.linspace(1_000_000, 2_000_000, len(index)),
    }, index=index)


def test_assessment_has_sensible_levels_and_score():
    item = assess_symbol("TEST", _history())
    assert item.support < item.close < item.resistance
    assert 0 <= item.score <= 100
    assert item.price_date.isoformat() == "2026-05-20"


def test_reports_include_disclaimer_and_excel_friendly_csv():
    item = assess_symbol("TEST", _history())
    result = DailyScanResult(
        generated_at=datetime(2026, 5, 20, 19), market_date=item.price_date,
        requested_symbols=1, successful_symbols=1, failed_symbols=0,
        assessments=[item], failures={},
    )
    html = build_html(result)
    csv_data = build_csv(result)
    assert "yatırım tavsiyesi değildir" in html
    assert "TEST" in html
    assert csv_data.startswith(b"\xef\xbb\xbf")
    assert b"TEST" in csv_data


def test_cloud_config_uses_environment(monkeypatch):
    monkeypatch.setenv("ALPHABIST_GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("ALPHABIST_REPORT_RECIPIENT", "recipient@example.com")
    assert _config() == {
        "sender": "sender@example.com",
        "recipient": "recipient@example.com",
    }


def test_history_loader_ignores_json_notice_lines(monkeypatch):
    class Result:
        returncode = 0
        stdout = '"provider notice"\n{"symbol":"TEST","ok":false,"error":"yok"}\n'
        stderr = ""

    monkeypatch.setattr(provider, "_global_borsa_api_path", lambda: "module")
    monkeypatch.setattr(provider.shutil, "which", lambda name: name)
    monkeypatch.setattr(provider.subprocess, "run", lambda *args, **kwargs: Result())
    histories, failures = provider.load_histories(["TEST"])
    assert histories == {}
    assert failures == {"TEST": "yok"}
