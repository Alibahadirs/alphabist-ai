import hashlib
import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.database.backup import (
    BackupSummary,
    summarize_database_backup,
    validate_database_backup,
)


@dataclass(frozen=True)
class RecoveryDrillResult:
    success: bool
    source_name: str
    source_sha256: str
    message: str
    tested_at: str
    summary: BackupSummary | None = None


def _temporary_path() -> Path:
    descriptor, name = tempfile.mkstemp(suffix=".db")
    os.close(descriptor)
    return Path(name)


def run_recovery_drill(
    database_data: bytes,
    *,
    source_name: str,
    tested_at: datetime | None = None,
) -> RecoveryDrillResult:
    timestamp = (tested_at or datetime.now().astimezone()).isoformat()
    checksum = hashlib.sha256(database_data).hexdigest()
    validation = validate_database_backup(database_data)
    if not validation.valid:
        return RecoveryDrillResult(
            success=False,
            source_name=source_name,
            source_sha256=checksum,
            message=validation.message,
            tested_at=timestamp,
        )

    source_path = _temporary_path()
    restored_path = _temporary_path()
    try:
        source_path.write_bytes(database_data)
        with closing(sqlite3.connect(source_path)) as source:
            with closing(sqlite3.connect(restored_path)) as destination:
                source.backup(destination)

        restored_data = restored_path.read_bytes()
        restored_validation = validate_database_backup(restored_data)
        if not restored_validation.valid:
            return RecoveryDrillResult(
                success=False,
                source_name=source_name,
                source_sha256=checksum,
                message=(
                    "İzole geri yükleme doğrulanamadı: "
                    + restored_validation.message
                ),
                tested_at=timestamp,
            )

        expected_summary = summarize_database_backup(database_data)
        restored_summary = summarize_database_backup(restored_data)
        if restored_summary != expected_summary:
            return RecoveryDrillResult(
                success=False,
                source_name=source_name,
                source_sha256=checksum,
                message=(
                    "İzole geri yükleme kayıt sayıları kaynakla "
                    "uyuşmuyor."
                ),
                tested_at=timestamp,
                summary=restored_summary,
            )
        return RecoveryDrillResult(
            success=True,
            source_name=source_name,
            source_sha256=checksum,
            message=(
                "Yedek izole veritabanına geri yüklendi ve "
                "kayıt sayıları doğrulandı."
            ),
            tested_at=timestamp,
            summary=restored_summary,
        )
    except (OSError, sqlite3.DatabaseError, ValueError) as exc:
        return RecoveryDrillResult(
            success=False,
            source_name=source_name,
            source_sha256=checksum,
            message=f"Kurtarma tatbikatı başarısız: {exc}",
            tested_at=timestamp,
        )
    finally:
        source_path.unlink(missing_ok=True)
        restored_path.unlink(missing_ok=True)
