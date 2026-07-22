from datetime import datetime, timezone

from app.database import repository
from app.market_data.batch import MarketBatchItem, MarketBatchSummary
from app.market_data.batch_history import build_market_batch_run


def _run():
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
        observed_at=datetime(2026, 7, 22, 13, 0, tzinfo=timezone.utc),
    )


def test_batch_audit_repository_keeps_invalid_rows_visible(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.add_market_batch_run(_run())
    with repository.connect() as conn:
        conn.execute(
            "UPDATE market_batch_run SET fingerprint='changed' WHERE id=1"
        )

    audits = repository.list_market_batch_run_audits()

    assert len(audits) == 1
    assert audits[0].status == "Parmak izi hatası"
    assert audits[0].integrity_valid is False
    assert repository.list_market_batch_runs() == []


def test_batch_audit_repository_survives_malformed_payload(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.add_market_batch_run(_run())
    with repository.connect() as conn:
        conn.execute(
            "UPDATE market_batch_run SET run_payload='{bad-json' WHERE id=1"
        )

    audits = repository.list_market_batch_run_audits()

    assert audits[0].status == "Yük bozuk"
    assert audits[0].run is None
    assert repository.list_market_batch_runs() == []


def test_batch_audit_repository_returns_valid_runs_normally(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.add_market_batch_run(_run())

    audits = repository.list_market_batch_run_audits()
    runs = repository.list_market_batch_runs()

    assert audits[0].integrity_valid is True
    assert len(runs) == 1
    assert runs[0].items[0].symbol == "THYAO"
