from datetime import datetime

from app.database import repository
from app.database.startup import run_startup_backup


def test_startup_backup_creates_then_reuses_daily_copy(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "alphabist.db"
    backup_directory = tmp_path / "backups"
    monkeypatch.setattr(repository, "DB_PATH", database_path)
    repository.init_db()
    now = datetime(2026, 7, 24, 8, 30)

    first = run_startup_backup(
        database_path,
        backup_directory,
        now=now,
    )
    second = run_startup_backup(
        database_path,
        backup_directory,
        now=now,
    )

    assert first.ready is True
    assert first.created is True
    assert first.file_name
    assert second.ready is True
    assert second.created is False
    assert second.file_name == first.file_name


def test_startup_backup_failure_is_non_blocking_status(tmp_path):
    status = run_startup_backup(
        tmp_path / "missing.db",
        tmp_path / "backups",
    )

    assert status.ready is False
    assert status.created is False
    assert "başarısız" in status.message
