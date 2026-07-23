from datetime import datetime

from app.core.preflight import (
    PreflightCheck,
    PreflightReport,
)
from app.database.health import DatabaseHealth
from app.ui.pages import _build_system_status_rows


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
    ]
    assert rows[-1]["Durum"] == "Hazır"


def test_system_status_rows_expose_backup_failure():
    preflight = PreflightReport(checks=())

    rows = _build_system_status_rows(
        preflight,
        _database_health(backup_ready=False),
    )

    assert rows[-1] == {
        "Kontrol": "Yedek üretimi",
        "Durum": "Hata",
        "Ayrıntı": "Yedek üretilemedi.",
    }
