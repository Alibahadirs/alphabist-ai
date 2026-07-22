from datetime import date, datetime, timezone

import pytest

from app.database import repository
from app.market_data.batch import diagnose_market_batch
from app.market_data.batch_history import build_market_batch_run
from app.market_data.diagnostics import diagnose_market_data
from app.market_data.models import build_market_diagnostic_snapshot


def _quote(source: str, price: float) -> dict:
    return {
        "last": price,
        "previous": price - 1,
        "change_percent": 1.0,
        "as_of_date": "2026-07-22",
        "source": source,
        "data_mode": "delayed",
        "official": False,
    }


def _diagnostic(symbol: str):
    return diagnose_market_data(
        symbol,
        reference_date=date(2026, 7, 22),
        yahoo_loader=lambda _: _quote("Yahoo Finance", 100),
        borsa_loader=lambda _: _quote("borsa-api / Yahoo Finance", 100),
    )


def _result():
    summary = diagnose_market_batch(["AKSA", "THYAO"], _diagnostic)
    snapshots = [
        build_market_diagnostic_snapshot(item.diagnostic)
        for item in summary.items
        if item.diagnostic is not None
    ]
    run = build_market_batch_run(
        summary,
        observed_at=datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
    )
    return run, snapshots


def test_persist_market_batch_result_saves_run_and_snapshots_atomically(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    run, snapshots = _result()

    first = repository.persist_market_batch_result(run, snapshots)
    second = repository.persist_market_batch_result(run, snapshots)

    assert (first.snapshots_inserted, first.snapshots_skipped) == (2, 0)
    assert first.run_inserted is True
    assert (second.snapshots_inserted, second.snapshots_skipped) == (0, 2)
    assert second.run_inserted is False
    assert len(repository.list_market_batch_runs()) == 1


def test_persist_market_batch_result_rejects_mismatched_snapshots(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    run, snapshots = _result()

    with pytest.raises(ValueError, match="anlık görüntüleri eşleşmiyor"):
        repository.persist_market_batch_result(run, snapshots[:1])

    assert repository.list_market_batch_runs() == []
    assert repository.list_latest_market_diagnostic_snapshots() == []


def test_persist_market_batch_result_rejects_tampering_before_transaction(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    run, snapshots = _result()
    tampered = snapshots[0].model_copy(update={"primary_price": 999})

    with pytest.raises(ValueError, match="parmak izi geçersiz"):
        repository.persist_market_batch_result(
            run,
            [tampered, snapshots[1]],
        )

    assert repository.list_market_batch_runs() == []
    assert repository.list_latest_market_diagnostic_snapshots() == []
