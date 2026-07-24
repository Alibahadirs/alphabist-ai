from datetime import datetime

from app.core.preflight import (
    PreflightCheck,
    PreflightReport,
)
from app.database.backup import BackupComparison, BackupSummary
from app.database.health import DatabaseHealth
from app.database.restore_history import RestoreAuditRecord
from app.database.recovery_drill import RecoveryDrillRecord
from app.ui.pages import (
    _backup_comparison_rows,
    _build_system_status_rows,
    _restore_audit_rows,
    _recovery_drill_rows,
)


def _database_health(*, backup_ready: bool = True) -> DatabaseHealth:
    return DatabaseHealth(
        status="Hazır",
        detail="SQLite bütünlüğü doğrulandı.",
        integrity="Doğrulandı",
        size_bytes=1024,
        table_count=8,
        company_count=3,
        safety_backup_count=1,
        latest_safety_backup_at=datetime(2026, 7, 23, 12, 0),
        backup_ready=backup_ready,
        backup_message=(
            "Yedek geçerli."
            if backup_ready
            else "Yedek üretilemedi."
        ),
        backup_age_days=0,
        backup_fresh=True,
        verified_backup_count=1,
        checksum_issue_count=0,
    )


def test_system_status_rows_include_runtime_and_backup_checks():
    preflight = PreflightReport(
        checks=(
            PreflightCheck(
                key="python",
                label="Python",
                status="Hazır",
                detail="3.14",
            ),
            PreflightCheck(
                key="database",
                label="SQLite veritabanı",
                status="Hazır",
                detail="Bütünlük doğrulandı.",
            ),
        )
    )

    rows = _build_system_status_rows(preflight, _database_health())

    assert [row["Kontrol"] for row in rows] == [
        "Python",
        "SQLite veritabanı",
        "Yedek üretimi",
        "Yedek tazeliği",
        "SHA-256 kanıtları",
    ]
    assert rows[-1]["Durum"] == "Hazır"


def test_system_status_rows_expose_backup_failure():
    preflight = PreflightReport(checks=())

    rows = _build_system_status_rows(
        preflight,
        _database_health(backup_ready=False),
    )

    assert rows[1] == {
        "Kontrol": "Yedek üretimi",
        "Durum": "Hata",
        "Ayrıntı": "Yedek üretilemedi.",
    }


def test_backup_comparison_rows_preserve_record_semantics():
    comparison = BackupComparison(
        current=BackupSummary(2, 1, 1, 4, 3),
        incoming=BackupSummary(3, 0, 2, 7, 5),
    )

    rows = _backup_comparison_rows(comparison)

    assert rows[0] == {
        "Kayıt türü": "Şirket",
        "Mevcut": 2,
        "Yüklenecek": 3,
        "Fark": 1,
    }
    assert rows[1]["Fark"] == -1
    assert rows[2]["Fark"] == 1


def test_restore_audit_rows_show_integrity_and_short_hash():
    record = RestoreAuditRecord(
        id=1,
        source_type="Taşınabilir ZIP paketi",
        source_file_name="backup.zip",
        source_sha256="a" * 64,
        status="Başarılı",
        message="Tamamlandı.",
        safety_backup_name="before.db",
        incoming_company_count=6,
        incoming_total_records=20,
        created_at="2026-07-24T14:00:00",
        fingerprint="invalid",
    )

    row = _restore_audit_rows([record])[0]

    assert row["Dosya"] == "backup.zip"
    assert row["Şirket"] == 6
    assert row["Bütünlük"] == "Geçersiz"
    assert row["SHA-256"] == "aaaaaaaaaaaa..."


def test_recovery_drill_rows_show_result_and_short_hash():
    record = RecoveryDrillRecord(
        id=1,
        source_name="daily.db",
        source_sha256="b" * 64,
        success=True,
        message="Doğrulandı.",
        company_count=6,
        total_records=24,
        tested_at="2026-07-24T16:00:00",
        fingerprint="invalid",
    )

    row = _recovery_drill_rows([record])[0]

    assert row["Sonuç"] == "Başarılı"
    assert row["Kaynak"] == "daily.db"
    assert row["Bütünlük"] == "Geçersiz"
    assert row["SHA-256"] == "bbbbbbbbbbbb..."
