import hashlib
import json
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


@dataclass(frozen=True)
class RecoveryDrillRecord:
    id: int
    source_name: str
    source_sha256: str
    success: bool
    message: str
    company_count: int
    total_records: int
    tested_at: str
    fingerprint: str

    @property
    def integrity_valid(self) -> bool:
        return self.fingerprint == recovery_drill_fingerprint(
            source_name=self.source_name,
            source_sha256=self.source_sha256,
            success=self.success,
            message=self.message,
            company_count=self.company_count,
            total_records=self.total_records,
            tested_at=self.tested_at,
        )


def recovery_drill_fingerprint(
    *,
    source_name: str,
    source_sha256: str,
    success: bool,
    message: str,
    company_count: int,
    total_records: int,
    tested_at: str,
) -> str:
    payload = {
        "source_name": source_name,
        "source_sha256": source_sha256,
        "success": success,
        "message": message,
        "company_count": company_count,
        "total_records": total_records,
        "tested_at": tested_at,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def ensure_recovery_drill_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS recovery_drill_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        success INTEGER NOT NULL,
        message TEXT NOT NULL,
        company_count INTEGER NOT NULL DEFAULT 0,
        total_records INTEGER NOT NULL DEFAULT 0,
        tested_at TEXT NOT NULL,
        fingerprint TEXT NOT NULL)"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_recovery_drill_history_id
        ON recovery_drill_history(id)"""
    )


def record_recovery_drill(
    database_path: Path,
    result: RecoveryDrillResult,
) -> RecoveryDrillRecord:
    company_count = (
        result.summary.company_count
        if result.summary is not None
        else 0
    )
    total_records = (
        result.summary.total_business_records
        if result.summary is not None
        else 0
    )
    fingerprint = recovery_drill_fingerprint(
        source_name=result.source_name,
        source_sha256=result.source_sha256,
        success=result.success,
        message=result.message,
        company_count=company_count,
        total_records=total_records,
        tested_at=result.tested_at,
    )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        ensure_recovery_drill_table(connection)
        cursor = connection.execute(
            """INSERT INTO recovery_drill_history(
            source_name, source_sha256, success, message,
            company_count, total_records, tested_at, fingerprint)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.source_name,
                result.source_sha256,
                int(result.success),
                result.message,
                company_count,
                total_records,
                result.tested_at,
                fingerprint,
            ),
        )
        record_id = cursor.lastrowid
    return RecoveryDrillRecord(
        id=int(record_id),
        source_name=result.source_name,
        source_sha256=result.source_sha256,
        success=result.success,
        message=result.message,
        company_count=company_count,
        total_records=total_records,
        tested_at=result.tested_at,
        fingerprint=fingerprint,
    )


def list_recovery_drills(
    database_path: Path,
    *,
    limit: int = 100,
    success: bool | None = None,
) -> list[RecoveryDrillRecord]:
    if limit < 1:
        raise ValueError("Kurtarma tatbikatı geçmişi limiti pozitif olmalıdır.")
    if not database_path.exists():
        return []
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_recovery_drill_table(connection)
        query = """SELECT id, source_name, source_sha256, success, message,
        company_count, total_records, tested_at, fingerprint
        FROM recovery_drill_history"""
        parameters: tuple[object, ...]
        if success is None:
            parameters = (limit,)
        else:
            query += " WHERE success=?"
            parameters = (int(success), limit)
        query += " ORDER BY id DESC LIMIT ?"
        rows = connection.execute(query, parameters).fetchall()
    return [
        RecoveryDrillRecord(
            **{
                **dict(row),
                "success": bool(row["success"]),
            }
        )
        for row in rows
    ]


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
