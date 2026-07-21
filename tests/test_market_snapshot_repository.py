from datetime import date

import pytest

from app.database import repository
from app.market_data.diagnostics import diagnose_market_data
from app.market_data.models import build_market_diagnostic_snapshot


def _quote(source: str):
    return {
        "last": 100,
        "previous": 98,
        "change_percent": 2.040816,
        "as_of_date": "2026-07-21",
        "source": source,
        "data_mode": "delayed",
        "official": False,
    }


def _snapshot():
    diagnostic = diagnose_market_data(
        "THYAO",
        reference_date=date(2026, 7, 21),
        yahoo_loader=lambda symbol: _quote("Yahoo Finance"),
        borsa_loader=lambda symbol: _quote("borsa-api / Yahoo Finance"),
    )
    return build_market_diagnostic_snapshot(diagnostic)


def test_market_snapshot_repository_deduplicates_fingerprint(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    snapshot = _snapshot()

    assert repository.add_market_diagnostic_snapshot(snapshot) is True
    assert repository.add_market_diagnostic_snapshot(snapshot) is False

    history = repository.list_market_diagnostic_snapshots("thyao")
    assert len(history) == 1
    assert history[0].symbol == "THYAO"
    assert history[0].cross_verified is True
    assert history[0].primary_date == date(2026, 7, 21)


def test_market_snapshot_repository_rejects_tampering(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    tampered = _snapshot().model_copy(update={"primary_price": 999})

    with pytest.raises(ValueError, match="parmak izi geçersiz"):
        repository.add_market_diagnostic_snapshot(tampered)
