import csv
import io
import sqlite3
from datetime import datetime

from app.database import repository
from app.database.backup import create_database_backup
from app.database.recovery_drill import (
    RecoveryDrillResult,
    list_recovery_drills,
    record_recovery_drill,
    run_recovery_drill,
)
from app.database.recovery_export import build_recovery_drill_csv
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


def test_recovery_drill_result_is_persisted_with_integrity(
    tmp_path, monkeypatch
):
    source_path = tmp_path / "source.db"
    history_path = tmp_path / "history.db"
    _create_database(source_path, monkeypatch)
    result = run_recovery_drill(
        create_database_backup(source_path),
        source_name="daily.db",
    )

    saved = record_recovery_drill(history_path, result)
    records = list_recovery_drills(history_path)

    assert saved.integrity_valid is True
    assert records == [saved]
    assert records[0].company_count == 1
    assert records[0].total_records == 1


def test_recovery_drill_history_detects_tampering(
    tmp_path, monkeypatch
):
    source_path = tmp_path / "source.db"
    history_path = tmp_path / "history.db"
    _create_database(source_path, monkeypatch)
    result = run_recovery_drill(
        create_database_backup(source_path),
        source_name="daily.db",
    )
    record_recovery_drill(history_path, result)
    with sqlite3.connect(history_path) as connection:
        connection.execute(
            "UPDATE recovery_drill_history SET company_count=99"
        )

    assert list_recovery_drills(history_path)[0].integrity_valid is False


def test_recovery_drill_history_can_filter_failed_results(tmp_path):
    history_path = tmp_path / "history.db"
    for success in (True, False):
        record_recovery_drill(
            history_path,
            RecoveryDrillResult(
                success=success,
                source_name=f"{success}.db",
                source_sha256="e" * 64,
                message="Sonuç",
                tested_at=f"2026-07-24T1{int(success)}:00:00",
            ),
        )

    failed = list_recovery_drills(history_path, success=False)

    assert len(failed) == 1
    assert failed[0].success is False


def test_recovery_drill_csv_is_excel_compatible(
    tmp_path, monkeypatch
):
    source_path = tmp_path / "source.db"
    history_path = tmp_path / "history.db"
    _create_database(source_path, monkeypatch)
    result = run_recovery_drill(
        create_database_backup(source_path),
        source_name="daily.db",
    )
    record_recovery_drill(history_path, result)

    csv_data = build_recovery_drill_csv(
        list_recovery_drills(history_path)
    )
    rows = list(
        csv.reader(io.StringIO(csv_data.decode("utf-8-sig")))
    )

    assert csv_data.startswith(b"\xef\xbb\xbf")
    assert rows[0][0:4] == [
        "Kayıt ID",
        "Tatbikat zamanı",
        "Sonuç",
        "Kaynak dosya",
    ]
    assert rows[1][2] == "Başarılı"
    assert rows[1][3] == "daily.db"
    assert rows[1][8] == "Doğrulandı"
