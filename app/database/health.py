from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.database import repository
from app.database.backup import (
    REQUIRED_TABLES,
    create_database_backup,
    list_safety_backups,
    validate_database_backup,
)


@dataclass(frozen=True)
class DatabaseHealth:
    status: str
    detail: str
    integrity: str
    size_bytes: int
    table_count: int
    company_count: int
    safety_backup_count: int
    latest_safety_backup_at: datetime | None
    backup_ready: bool
    backup_message: str

    @property
    def ready(self) -> bool:
        return self.status == "Hazır" and self.backup_ready


def inspect_database_health(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
) -> DatabaseHealth:
    path = database_path or repository.DB_PATH
    if not path.exists():
        return DatabaseHealth(
            status="Kurulmadı",
            detail="Veritabanı ilk açılışta otomatik oluşturulacak.",
            integrity="Kontrol edilmedi",
            size_bytes=0,
            table_count=0,
            company_count=0,
            safety_backup_count=0,
            latest_safety_backup_at=None,
            backup_ready=False,
            backup_message="Veritabanı henüz yok.",
        )

    try:
        with closing(sqlite3.connect(path)) as connection:
            integrity = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()[0]
            tables = {
                row[0]
                for row in connection.execute(
                    """SELECT name FROM sqlite_master
                    WHERE type='table'"""
                ).fetchall()
            }
            company_count = (
                connection.execute(
                    "SELECT COUNT(*) FROM companies"
                ).fetchone()[0]
                if "companies" in tables
                else 0
            )
    except sqlite3.DatabaseError as exc:
        return DatabaseHealth(
            status="Hata",
            detail=f"Veritabanı okunamıyor: {exc}",
            integrity="Başarısız",
            size_bytes=path.stat().st_size,
            table_count=0,
            company_count=0,
            safety_backup_count=0,
            latest_safety_backup_at=None,
            backup_ready=False,
            backup_message="Bütünlük sorunu nedeniyle yedek sınanmadı.",
        )

    missing_tables = REQUIRED_TABLES - tables
    healthy = integrity == "ok" and not missing_tables
    if missing_tables:
        detail = "Eksik tablolar: " + ", ".join(sorted(missing_tables))
    elif integrity != "ok":
        detail = f"SQLite bütünlük sonucu: {integrity}"
    else:
        detail = "SQLite bütünlüğü ve zorunlu tablolar doğrulandı."

    backup_ready = False
    backup_message = "Veritabanı sağlıklı olmadığı için yedek sınanmadı."
    if healthy:
        try:
            backup_validation = validate_database_backup(
                create_database_backup(path)
            )
            backup_ready = backup_validation.valid
            backup_message = backup_validation.message
        except (OSError, sqlite3.DatabaseError) as exc:
            backup_message = f"Yedek üretilemedi: {exc}"

    safety_backups = list_safety_backups(path, backup_directory)
    latest_backup_at = (
        safety_backups[0].modified_at if safety_backups else None
    )
    return DatabaseHealth(
        status="Hazır" if healthy else "Hata",
        detail=detail,
        integrity="Doğrulandı" if integrity == "ok" else str(integrity),
        size_bytes=path.stat().st_size,
        table_count=len(tables),
        company_count=company_count,
        safety_backup_count=len(safety_backups),
        latest_safety_backup_at=latest_backup_at,
        backup_ready=backup_ready,
        backup_message=backup_message,
    )
