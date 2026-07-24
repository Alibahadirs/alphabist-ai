import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


RESTORE_STATUS_SUCCESS = "Başarılı"
RESTORE_STATUS_FAILURE = "Başarısız"
RESTORE_STATUSES = {
    RESTORE_STATUS_SUCCESS,
    RESTORE_STATUS_FAILURE,
}


@dataclass(frozen=True)
class RestoreAuditRecord:
    id: int
    source_type: str
    source_file_name: str
    source_sha256: str
    status: str
    message: str
    safety_backup_name: str
    incoming_company_count: int
    incoming_total_records: int
    created_at: str
    fingerprint: str

    @property
    def integrity_valid(self) -> bool:
        return self.fingerprint == restore_audit_fingerprint(
            source_type=self.source_type,
            source_file_name=self.source_file_name,
            source_sha256=self.source_sha256,
            status=self.status,
            message=self.message,
            safety_backup_name=self.safety_backup_name,
            incoming_company_count=self.incoming_company_count,
            incoming_total_records=self.incoming_total_records,
            created_at=self.created_at,
        )


def restore_audit_fingerprint(
    *,
    source_type: str,
    source_file_name: str,
    source_sha256: str,
    status: str,
    message: str,
    safety_backup_name: str,
    incoming_company_count: int,
    incoming_total_records: int,
    created_at: str,
) -> str:
    payload = {
        "source_type": source_type,
        "source_file_name": source_file_name,
        "source_sha256": source_sha256,
        "status": status,
        "message": message,
        "safety_backup_name": safety_backup_name,
        "incoming_company_count": incoming_company_count,
        "incoming_total_records": incoming_total_records,
        "created_at": created_at,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def ensure_restore_audit_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS restore_audit_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL,
        source_file_name TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT NOT NULL DEFAULT '',
        safety_backup_name TEXT NOT NULL DEFAULT '',
        incoming_company_count INTEGER NOT NULL DEFAULT 0,
        incoming_total_records INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        fingerprint TEXT NOT NULL)"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_restore_audit_history_id
        ON restore_audit_history(id)"""
    )


def record_restore_audit(
    database_path: Path,
    *,
    source_type: str,
    source_file_name: str,
    source_sha256: str,
    status: str,
    message: str = "",
    safety_backup_name: str = "",
    incoming_company_count: int = 0,
    incoming_total_records: int = 0,
    created_at: datetime | None = None,
) -> RestoreAuditRecord:
    if status not in RESTORE_STATUSES:
        raise ValueError("Geçersiz geri yükleme denetim durumu.")
    timestamp = (created_at or datetime.now().astimezone()).isoformat()
    fingerprint = restore_audit_fingerprint(
        source_type=source_type,
        source_file_name=source_file_name,
        source_sha256=source_sha256,
        status=status,
        message=message,
        safety_backup_name=safety_backup_name,
        incoming_company_count=incoming_company_count,
        incoming_total_records=incoming_total_records,
        created_at=timestamp,
    )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_restore_audit_table(connection)
        cursor = connection.execute(
            """INSERT INTO restore_audit_history(
            source_type, source_file_name, source_sha256, status,
            message, safety_backup_name, incoming_company_count,
            incoming_total_records, created_at, fingerprint)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source_type,
                source_file_name,
                source_sha256,
                status,
                message,
                safety_backup_name,
                incoming_company_count,
                incoming_total_records,
                timestamp,
                fingerprint,
            ),
        )
        record_id = cursor.lastrowid
    return RestoreAuditRecord(
        id=int(record_id),
        source_type=source_type,
        source_file_name=source_file_name,
        source_sha256=source_sha256,
        status=status,
        message=message,
        safety_backup_name=safety_backup_name,
        incoming_company_count=incoming_company_count,
        incoming_total_records=incoming_total_records,
        created_at=timestamp,
        fingerprint=fingerprint,
    )


def list_restore_audits(
    database_path: Path,
    *,
    limit: int = 100,
    status: str | None = None,
) -> list[RestoreAuditRecord]:
    if limit < 1:
        raise ValueError("Geri yükleme geçmişi limiti pozitif olmalıdır.")
    if status is not None and status not in RESTORE_STATUSES:
        raise ValueError("Geçersiz geri yükleme geçmişi filtresi.")
    if not database_path.exists():
        return []
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_restore_audit_table(connection)
        query = """SELECT id, source_type, source_file_name, source_sha256,
        status, message, safety_backup_name, incoming_company_count,
        incoming_total_records, created_at, fingerprint
        FROM restore_audit_history"""
        parameters: tuple[object, ...]
        if status is None:
            parameters = (limit,)
        else:
            query += " WHERE status=?"
            parameters = (status, limit)
        query += " ORDER BY id DESC LIMIT ?"
        rows = connection.execute(query, parameters).fetchall()
    return [RestoreAuditRecord(**dict(row)) for row in rows]
