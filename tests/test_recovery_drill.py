from datetime import datetime

from app.database import repository
from app.database.backup import create_database_backup
from app.database.recovery_drill import run_recovery_drill
from app.scoring.models import FinancialMetrics


def _create_database(path, monkeypatch) -> None:
    monkeypatch.setattr(repository, "DB_PATH", path)
    repository.init_db()
    repository.upsert_company(
        FinancialMetrics(
            symbol="DRILL",
            company_name="Tatbikat Şirketi",
        )
    )


def test_recovery_drill_restores_backup_in_isolation(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch)
    original_data = create_database_backup(database_path)

    result = run_recovery_drill(
        original_data,
        source_name="daily.db",
        tested_at=datetime(2026, 7, 24, 15, 0),
    )

    assert result.success is True
    assert result.source_name == "daily.db"
    assert result.summary is not None
    assert result.summary.company_count == 1
    assert result.tested_at == "2026-07-24T15:00:00"
    assert database_path.read_bytes().startswith(b"SQLite format 3\x00")


def test_recovery_drill_rejects_invalid_database():
    result = run_recovery_drill(
        b"invalid",
        source_name="broken.db",
    )

    assert result.success is False
    assert "SQLite" in result.message
    assert result.summary is None


def test_recovery_drill_checksum_is_repeatable(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch)
    database_data = create_database_backup(database_path)

    first = run_recovery_drill(
        database_data,
        source_name="first.db",
    )
    second = run_recovery_drill(
        database_data,
        source_name="second.db",
    )

    assert first.source_sha256 == second.source_sha256
