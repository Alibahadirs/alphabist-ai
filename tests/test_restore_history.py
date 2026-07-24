import csv
import io
import sqlite3
from datetime import datetime

from app.database import repository
from app.database.restore_history import (
    RESTORE_STATUS_FAILURE,
    RESTORE_STATUS_SUCCESS,
    list_restore_audits,
    record_restore_audit,
)
from app.database.restore_export import build_restore_audit_csv


def test_init_db_creates_restore_audit_table(tmp_path, monkeypatch):
    database_path = tmp_path / "alphabist.db"
    monkeypatch.setattr(repository, "DB_PATH", database_path)

    repository.init_db()

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "restore_audit_history" in tables


def test_restore_audit_is_persisted_and_integrity_checked(tmp_path):
    database_path = tmp_path / "alphabist.db"

    saved = record_restore_audit(
        database_path,
        source_type="Taşınabilir ZIP paketi",
        source_file_name="backup.zip",
        source_sha256="a" * 64,
        status=RESTORE_STATUS_SUCCESS,
        message="Geri yükleme tamamlandı.",
        safety_backup_name="before.db",
        incoming_company_count=4,
        incoming_total_records=18,
        created_at=datetime(2026, 7, 24, 13, 0),
    )
    records = list_restore_audits(database_path)

    assert saved.integrity_valid is True
    assert len(records) == 1
    assert records[0] == saved
    assert records[0].incoming_company_count == 4


def test_restore_audit_detects_database_tampering(tmp_path):
    database_path = tmp_path / "alphabist.db"
    record_restore_audit(
        database_path,
        source_type="SQLite veritabanı",
        source_file_name="backup.db",
        source_sha256="b" * 64,
        status=RESTORE_STATUS_SUCCESS,
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """UPDATE restore_audit_history
            SET incoming_company_count=99"""
        )

    record = list_restore_audits(database_path)[0]

    assert record.integrity_valid is False


def test_restore_audit_limit_must_be_positive(tmp_path):
    try:
        list_restore_audits(tmp_path / "alphabist.db", limit=0)
    except ValueError as exc:
        assert "pozitif" in str(exc)
    else:
        raise AssertionError("Sıfır kayıt limiti kabul edilmemeliydi.")


def test_restore_audit_history_can_be_filtered_by_status(tmp_path):
    database_path = tmp_path / "alphabist.db"
    for status in (RESTORE_STATUS_SUCCESS, RESTORE_STATUS_FAILURE):
        record_restore_audit(
            database_path,
            source_type="SQLite veritabanı",
            source_file_name=f"{status}.db",
            source_sha256="c" * 64,
            status=status,
        )

    failed = list_restore_audits(
        database_path,
        status=RESTORE_STATUS_FAILURE,
    )

    assert len(failed) == 1
    assert failed[0].status == RESTORE_STATUS_FAILURE


def test_restore_audit_csv_is_excel_compatible(tmp_path):
    database_path = tmp_path / "alphabist.db"
    record_restore_audit(
        database_path,
        source_type="Taşınabilir ZIP paketi",
        source_file_name="backup.zip",
        source_sha256="d" * 64,
        status=RESTORE_STATUS_SUCCESS,
        message="Tamamlandı.",
        incoming_company_count=6,
        incoming_total_records=24,
    )

    csv_data = build_restore_audit_csv(
        list_restore_audits(database_path)
    )
    rows = list(
        csv.reader(io.StringIO(csv_data.decode("utf-8-sig")))
    )

    assert csv_data.startswith(b"\xef\xbb\xbf")
    assert rows[0][0:5] == [
        "Kayıt ID",
        "Tarih",
        "Durum",
        "Kaynak türü",
        "Dosya",
    ]
    assert rows[1][2] == RESTORE_STATUS_SUCCESS
    assert rows[1][4] == "backup.zip"
    assert rows[1][10] == "Doğrulandı"
