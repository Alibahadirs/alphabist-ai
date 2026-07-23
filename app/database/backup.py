import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.database import repository


REQUIRED_TABLES = {
    "companies",
    "watchlist",
    "score_history",
    "portfolio_positions",
    "company_data_audit",
}


@dataclass(frozen=True)
class BackupValidation:
    valid: bool
    message: str
    tables: tuple[str, ...] = ()


@dataclass(frozen=True)
class SafetyBackupInfo:
    path: Path
    file_name: str
    size_bytes: int
    modified_at: datetime
    valid: bool


@dataclass(frozen=True)
class BackupSummary:
    company_count: int
    watchlist_count: int
    portfolio_position_count: int
    score_history_count: int
    audit_count: int

    @property
    def total_business_records(self) -> int:
        return sum(
            (
                self.company_count,
                self.watchlist_count,
                self.portfolio_position_count,
                self.score_history_count,
                self.audit_count,
            )
        )


def _temporary_database_path() -> Path:
    file_descriptor, name = tempfile.mkstemp(suffix=".db")
    os.close(file_descriptor)
    return Path(name)


def _database_path(database_path: Path | None) -> Path:
    return database_path or repository.DB_PATH


def create_database_backup(database_path: Path | None = None) -> bytes:
    source_path = _database_path(database_path)
    if not source_path.exists():
        raise FileNotFoundError("Yedeklenecek veritabanı bulunamadı.")

    temporary_path = _temporary_database_path()
    try:
        with closing(sqlite3.connect(source_path)) as source:
            with closing(sqlite3.connect(temporary_path)) as destination:
                source.backup(destination)
        return temporary_path.read_bytes()
    finally:
        temporary_path.unlink(missing_ok=True)


def validate_database_backup(data: bytes) -> BackupValidation:
    if not data.startswith(b"SQLite format 3\x00"):
        return BackupValidation(
            valid=False,
            message="Dosya geçerli bir SQLite veritabanı değil.",
        )

    temporary_path = _temporary_database_path()
    try:
        temporary_path.write_bytes(data)
        try:
            with closing(
                sqlite3.connect(
                    f"file:{temporary_path.as_posix()}?mode=ro",
                    uri=True,
                )
            ) as connection:
                integrity = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]
                tables = {
                    row[0]
                    for row in connection.execute(
                        """SELECT name FROM sqlite_master
                        WHERE type='table'"""
                    ).fetchall()
                }
        except sqlite3.DatabaseError:
            return BackupValidation(
                valid=False,
                message="Veritabanı dosyası okunamıyor veya hasarlı.",
            )

        if integrity != "ok":
            return BackupValidation(
                valid=False,
                message=f"Veritabanı bütünlük kontrolü başarısız: {integrity}",
            )
        missing_tables = REQUIRED_TABLES - tables
        if missing_tables:
            return BackupValidation(
                valid=False,
                message=(
                    "AlphaBIST tabloları eksik: "
                    + ", ".join(sorted(missing_tables))
                ),
                tables=tuple(sorted(tables)),
            )
        return BackupValidation(
            valid=True,
            message="Yedek geçerli ve geri yüklemeye hazır.",
            tables=tuple(sorted(tables)),
        )
    finally:
        temporary_path.unlink(missing_ok=True)


def summarize_database_backup(data: bytes) -> BackupSummary:
    validation = validate_database_backup(data)
    if not validation.valid:
        raise ValueError(validation.message)

    temporary_path = _temporary_database_path()
    try:
        temporary_path.write_bytes(data)
        with closing(
            sqlite3.connect(
                f"file:{temporary_path.as_posix()}?mode=ro",
                uri=True,
            )
        ) as connection:
            counts = {
                table: connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in REQUIRED_TABLES
            }
        return BackupSummary(
            company_count=counts["companies"],
            watchlist_count=counts["watchlist"],
            portfolio_position_count=counts["portfolio_positions"],
            score_history_count=counts["score_history"],
            audit_count=counts["company_data_audit"],
        )
    finally:
        temporary_path.unlink(missing_ok=True)


def restore_database_backup(
    data: bytes,
    database_path: Path | None = None,
    backup_directory: Path | None = None,
) -> Path | None:
    validation = validate_database_backup(data)
    if not validation.valid:
        raise ValueError(validation.message)

    target_path = _database_path(database_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    safety_backup_path: Path | None = None
    if target_path.exists():
        safety_directory = (
            backup_directory or target_path.parent / "backups"
        )
        safety_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        safety_backup_path = (
            safety_directory
            / f"alphabist-before-restore-{timestamp}.db"
        )
        safety_backup_path.write_bytes(
            create_database_backup(target_path)
        )

    temporary_path = _temporary_database_path()
    try:
        temporary_path.write_bytes(data)
        with closing(sqlite3.connect(temporary_path)) as source:
            with closing(sqlite3.connect(target_path)) as destination:
                source.backup(destination)
    finally:
        temporary_path.unlink(missing_ok=True)

    restored_validation = validate_database_backup(
        target_path.read_bytes()
    )
    if not restored_validation.valid:
        raise RuntimeError(
            "Geri yüklenen veritabanı doğrulanamadı: "
            + restored_validation.message
        )
    return safety_backup_path


def list_safety_backups(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
) -> list[SafetyBackupInfo]:
    target_path = _database_path(database_path)
    safety_directory = backup_directory or target_path.parent / "backups"
    if not safety_directory.exists():
        return []

    backups: list[SafetyBackupInfo] = []
    for path in safety_directory.glob(
        "alphabist-before-restore-*.db"
    ):
        stat = path.stat()
        validation = validate_database_backup(path.read_bytes())
        backups.append(
            SafetyBackupInfo(
                path=path,
                file_name=path.name,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                valid=validation.valid,
            )
        )
    backups.sort(key=lambda item: item.modified_at, reverse=True)
    return backups
