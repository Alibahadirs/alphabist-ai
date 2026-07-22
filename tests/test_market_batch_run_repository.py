from datetime import datetime, timezone

import pytest

from app.database import repository
from app.market_data.batch import MarketBatchItem, MarketBatchSummary
from app.market_data.batch_history import build_market_batch_run


def _run(minute: int = 30):
    summary = MarketBatchSummary(
        total=1,
        cross_verified=0,
        partial=0,
        unavailable=0,
        failed=1,
        items=(
            MarketBatchItem(
                symbol="THYAO",
                diagnostic=None,
                status="Hata",
                error="Bağlantı kurulamadı",
            ),
        ),
    )
    return build_market_batch_run(
        summary,
        observed_at=datetime(2026, 7, 22, 9, minute, tzinfo=timezone.utc),
    )


def test_market_batch_run_repository_persists_and_deduplicates(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    run = _run()

    assert repository.add_market_batch_run(run) is True
    assert repository.add_market_batch_run(run) is False

    history = repository.list_market_batch_runs()
    assert len(history) == 1
    assert history[0].id is not None
    assert history[0].items[0].detail == "Bağlantı kurulamadı"


def test_market_batch_run_repository_returns_newest_first(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.add_market_batch_run(_run(30))
    repository.add_market_batch_run(_run(31))

    history = repository.list_market_batch_runs(limit=1)

    assert len(history) == 1
    assert history[0].observed_at.minute == 31


def test_market_batch_run_repository_rejects_tampering(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    tampered = _run().model_copy(update={"failed": 0})

    with pytest.raises(ValueError, match="parmak izi geçersiz"):
        repository.add_market_batch_run(tampered)

    assert repository.list_market_batch_runs() == []
