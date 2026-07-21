from datetime import date

import pytest

from app.database import repository
from app.market_data.diagnostics import diagnose_market_data
from app.market_data.models import build_market_diagnostic_snapshot


def _quote(source: str, price: float) -> dict:
    return {
        "last": price,
        "previous": price - 1,
        "change_percent": 1.0,
        "as_of_date": "2026-07-21",
        "source": source,
        "data_mode": "delayed",
        "official": False,
    }


def _snapshot(symbol: str, price: float):
    diagnostic = diagnose_market_data(
        symbol,
        reference_date=date(2026, 7, 21),
        yahoo_loader=lambda _: _quote("Yahoo Finance", price),
        borsa_loader=lambda _: _quote("borsa-api", price),
    )
    return build_market_diagnostic_snapshot(diagnostic)


def test_market_batch_repository_is_transactional_and_deduplicated(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    snapshots = [_snapshot("THYAO", 100), _snapshot("AKSA", 50)]

    first = repository.add_market_diagnostic_snapshots(snapshots)
    second = repository.add_market_diagnostic_snapshots(snapshots)

    assert (first.inserted, first.skipped) == (2, 0)
    assert (second.inserted, second.skipped) == (0, 2)
    assert [
        item.symbol
        for item in repository.list_latest_market_diagnostic_snapshots()
    ] == ["AKSA", "THYAO"]


def test_market_batch_repository_returns_latest_for_requested_symbols(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.add_market_diagnostic_snapshots(
        [_snapshot("THYAO", 100), _snapshot("AKSA", 50)]
    )
    repository.add_market_diagnostic_snapshot(_snapshot("THYAO", 105))

    latest = repository.list_latest_market_diagnostic_snapshots(["thyao"])

    assert len(latest) == 1
    assert latest[0].symbol == "THYAO"
    assert latest[0].primary_price == 105


def test_market_batch_repository_rejects_entire_tampered_batch(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    valid = _snapshot("AKSA", 50)
    tampered = _snapshot("THYAO", 100).model_copy(
        update={"primary_price": 999}
    )

    with pytest.raises(ValueError, match="parmak izi geçersiz"):
        repository.add_market_diagnostic_snapshots([valid, tampered])

    assert repository.list_latest_market_diagnostic_snapshots() == []
