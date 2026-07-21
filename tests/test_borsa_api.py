import subprocess

import pytest

from app.core.exceptions import DataProviderError
from app.market_data import borsa_api


HISTORY_OUTPUT = """
│ 20.07.2026 │ 328.75 ₺ │ 330.00 ₺ │ 323.75 ₺ │ 328.00 ₺ │ 46.622.936 │
│ 21.07.2026 │ 330.00 ₺ │ 330.25 ₺ │ 317.50 ₺ │ 317.50 ₺ │ 49.836.435 │
"""


def test_parse_borsa_history_recalculates_daily_change():
    quote = borsa_api.parse_borsa_api_history(HISTORY_OUTPUT)

    assert quote["last"] == 317.50
    assert quote["previous"] == 328.00
    assert quote["change"] == -10.50
    assert quote["change_percent"] == pytest.approx(-3.2012195)
    assert quote["as_of_date"] == "2026-07-21"
    assert quote["data_mode"] == "delayed"
    assert quote["official"] is False


def test_borsa_api_rejects_unsafe_symbol():
    with pytest.raises(DataProviderError, match="hisse kodu geçersiz"):
        borsa_api.get_borsa_api_quote("THYAO;echo")


def test_borsa_api_reports_missing_command(monkeypatch):
    monkeypatch.setattr(borsa_api.shutil, "which", lambda command: None)

    with pytest.raises(DataProviderError, match="npm install"):
        borsa_api.get_borsa_api_quote("THYAO")


def test_borsa_api_runs_without_shell(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, HISTORY_OUTPUT, "")

    monkeypatch.setattr(
        borsa_api.shutil,
        "which",
        lambda command: "C:/npm/borsa.cmd",
    )
    monkeypatch.setattr(borsa_api.subprocess, "run", fake_run)

    quote = borsa_api.get_borsa_api_quote("thyao")

    assert captured["command"] == [
        "C:/npm/borsa.cmd",
        "gecmis",
        "THYAO",
        "5d",
    ]
    assert captured["kwargs"]["shell"] is False
    assert quote["last"] == 317.50


def test_borsa_api_requires_two_closes():
    with pytest.raises(DataProviderError, match="en az iki kapanış"):
        borsa_api.parse_borsa_api_history(
            "│ 21.07.2026 │ 330.00 ₺ │ 330.25 ₺ │ 317.50 ₺ │ 317.50 ₺ │"
        )
