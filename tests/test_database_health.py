from app.database import repository
from app.database.backup import (
    create_database_backup,
    restore_database_backup,
)
from app.database.health import inspect_database_health
from app.scoring.models import FinancialMetrics


def _company() -> FinancialMetrics:
    return FinancialMetrics(
        symbol="READY",
        company_name="Hazır Test Şirketi",
    )


def test_missing_database_is_reported_without_crashing(tmp_path):
    health = inspect_database_health(tmp_path / "missing.db")

    assert health.status == "Kurulmadı"
    assert health.ready is False
    assert health.size_bytes == 0


def test_initialized_database_and_backup_are_verified(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "alphabist.db"
    monkeypatch.setattr(repository, "DB_PATH", database_path)
    repository.init_db()
    repository.upsert_company(_company())

    health = inspect_database_health(database_path)

    assert health.ready is True
    assert health.status == "Hazır"
    assert health.integrity == "Doğrulandı"
    assert health.company_count == 1
    assert health.table_count >= 5
    assert health.size_bytes > 0
    assert health.backup_ready is True


def test_safety_backup_is_included_in_health_report(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "alphabist.db"
    backup_directory = tmp_path / "backups"
    monkeypatch.setattr(repository, "DB_PATH", database_path)
    repository.init_db()

    data = create_database_backup(database_path)
    restore_database_backup(
        data,
        database_path,
        backup_directory,
    )
    health = inspect_database_health(
        database_path,
        backup_directory,
    )

    assert health.ready is True
    assert health.safety_backup_count == 1
    assert health.latest_safety_backup_at is not None


def test_corrupted_database_is_reported_as_error(tmp_path):
    database_path = tmp_path / "broken.db"
    database_path.write_bytes(b"broken")

    health = inspect_database_health(database_path)

    assert health.status == "Hata"
    assert health.ready is False
    assert health.backup_ready is False
