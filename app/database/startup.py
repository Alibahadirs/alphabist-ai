from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.database.backup import ensure_daily_backup


@dataclass(frozen=True)
class StartupBackupStatus:
    ready: bool
    created: bool
    message: str
    file_name: str = ""


def run_startup_backup(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
    *,
    keep_count: int = 14,
    now: datetime | None = None,
) -> StartupBackupStatus:
    try:
        result = ensure_daily_backup(
            database_path,
            backup_directory,
            keep_count=keep_count,
            now=now,
        )
    except (FileNotFoundError, RuntimeError, OSError, ValueError) as exc:
        return StartupBackupStatus(
            ready=False,
            created=False,
            message=f"Otomatik yedekleme başarısız: {exc}",
        )
    return StartupBackupStatus(
        ready=True,
        created=result.created,
        message=result.reason,
        file_name=result.backup.file_name,
    )
