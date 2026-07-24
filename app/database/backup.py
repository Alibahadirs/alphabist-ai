import hashlib
import io
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.core.settings import settings
from app.database import repository


REQUIRED_TABLES = {
    "companies",
    "watchlist",
    "score_history",
    "portfolio_positions",
    "company_data_audit",
}
BACKUP_BUNDLE_SCHEMA_VERSION = 1
BACKUP_BUNDLE_DATABASE_NAME = "alphabist.db"
BACKUP_BUNDLE_CHECKSUM_NAME = "alphabist.db.sha256"
BACKUP_BUNDLE_MANIFEST_NAME = "manifest.json"


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
    backup_type: str = "Geri yükleme öncesi"
    checksum_sha256: str = ""
    checksum_valid: bool | None = None

    @property
    def checksum_status(self) -> str:
        if self.checksum_valid is True:
            return "Doğrulandı"
        if self.checksum_valid is False:
            return "Uyuşmazlık"
        return "Kanıt yok"


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


@dataclass(frozen=True)
class BackupBundleManifest:
    schema_version: int
    app_version: str
    created_at: str
    database_file: str
    database_sha256: str
    database_size: int
    company_count: int
    watchlist_count: int
    portfolio_position_count: int
    score_history_count: int
    audit_count: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "schema_version": self.schema_version,
            "app_version": self.app_version,
            "created_at": self.created_at,
            "database_file": self.database_file,
            "database_sha256": self.database_sha256,
            "database_size": self.database_size,
            "company_count": self.company_count,
            "watchlist_count": self.watchlist_count,
            "portfolio_position_count": self.portfolio_position_count,
            "score_history_count": self.score_history_count,
            "audit_count": self.audit_count,
        }


@dataclass(frozen=True)
class BackupComparison:
    current: BackupSummary
    incoming: BackupSummary

    @property
    def company_delta(self) -> int:
        return self.incoming.company_count - self.current.company_count

    @property
    def watchlist_delta(self) -> int:
        return self.incoming.watchlist_count - self.current.watchlist_count

    @property
    def portfolio_position_delta(self) -> int:
        return (
            self.incoming.portfolio_position_count
            - self.current.portfolio_position_count
        )

    @property
    def score_history_delta(self) -> int:
        return (
            self.incoming.score_history_count
            - self.current.score_history_count
        )

    @property
    def audit_delta(self) -> int:
        return self.incoming.audit_count - self.current.audit_count


@dataclass(frozen=True)
class AutomaticBackupResult:
    created: bool
    backup: SafetyBackupInfo
    reason: str


def _temporary_database_path() -> Path:
    file_descriptor, name = tempfile.mkstemp(suffix=".db")
    os.close(file_descriptor)
    return Path(name)


def _database_path(database_path: Path | None) -> Path:
    return database_path or repository.DB_PATH


def _backup_directory(
    database_path: Path,
    backup_directory: Path | None,
) -> Path:
    return backup_directory or database_path.parent / "backups"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _checksum_path(database_backup_path: Path) -> Path:
    return database_backup_path.with_suffix(
        database_backup_path.suffix + ".sha256"
    )


def _write_checksum_manifest(path: Path, data: bytes) -> None:
    checksum_path = _checksum_path(path)
    temporary_path = checksum_path.with_suffix(
        checksum_path.suffix + ".tmp"
    )
    try:
        temporary_path.write_text(
            _sha256(data) + "\n",
            encoding="ascii",
        )
        temporary_path.replace(checksum_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _backup_info(
    path: Path,
    *,
    backup_type: str,
) -> SafetyBackupInfo:
    stat = path.stat()
    data = path.read_bytes()
    validation = validate_database_backup(data)
    actual_checksum = _sha256(data)
    checksum_path = _checksum_path(path)
    checksum_valid = None
    if checksum_path.exists():
        try:
            expected_checksum = checksum_path.read_text(
                encoding="ascii"
            ).strip().lower()
        except (OSError, UnicodeError):
            checksum_valid = False
        else:
            checksum_valid = (
                len(expected_checksum) == 64
                and expected_checksum == actual_checksum
            )
    return SafetyBackupInfo(
        path=path,
        file_name=path.name,
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime),
        valid=validation.valid and checksum_valid is not False,
        backup_type=backup_type,
        checksum_sha256=actual_checksum,
        checksum_valid=checksum_valid,
    )


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


def create_backup_bundle(
    database_path: Path | None = None,
    *,
    created_at: datetime | None = None,
) -> bytes:
    database_data = create_database_backup(database_path)
    validation = validate_database_backup(database_data)
    if not validation.valid:
        raise RuntimeError(validation.message)

    summary = summarize_database_backup(database_data)
    checksum = _sha256(database_data)
    manifest = BackupBundleManifest(
        schema_version=BACKUP_BUNDLE_SCHEMA_VERSION,
        app_version=settings.app_version,
        created_at=(created_at or datetime.now().astimezone()).isoformat(),
        database_file=BACKUP_BUNDLE_DATABASE_NAME,
        database_sha256=checksum,
        database_size=len(database_data),
        company_count=summary.company_count,
        watchlist_count=summary.watchlist_count,
        portfolio_position_count=summary.portfolio_position_count,
        score_history_count=summary.score_history_count,
        audit_count=summary.audit_count,
    )

    bundle = io.BytesIO()
    with zipfile.ZipFile(
        bundle,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(BACKUP_BUNDLE_DATABASE_NAME, database_data)
        archive.writestr(
            BACKUP_BUNDLE_CHECKSUM_NAME,
            checksum + "\n",
        )
        archive.writestr(
            BACKUP_BUNDLE_MANIFEST_NAME,
            json.dumps(
                manifest.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    return bundle.getvalue()


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


def compare_backup_to_database(
    data: bytes,
    database_path: Path | None = None,
) -> BackupComparison:
    target_path = _database_path(database_path)
    incoming = summarize_database_backup(data)
    if target_path.exists():
        current = summarize_database_backup(
            create_database_backup(target_path)
        )
    else:
        current = BackupSummary(
            company_count=0,
            watchlist_count=0,
            portfolio_position_count=0,
            score_history_count=0,
            audit_count=0,
        )
    return BackupComparison(current=current, incoming=incoming)


def _restore_database_from_bytes(data: bytes, target_path: Path) -> None:
    temporary_path = _temporary_database_path()
    try:
        temporary_path.write_bytes(data)
        validation = validate_database_backup(
            temporary_path.read_bytes()
        )
        if not validation.valid:
            raise RuntimeError(validation.message)
        with closing(sqlite3.connect(temporary_path)) as source:
            with closing(sqlite3.connect(target_path)) as destination:
                source.backup(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def list_local_backups(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
) -> list[SafetyBackupInfo]:
    target_path = _database_path(database_path)
    directory = _backup_directory(target_path, backup_directory)
    if not directory.exists():
        return []

    backups = [
        *(
            _backup_info(path, backup_type="Manuel")
            for path in directory.glob("alphabist-manual-*.db")
        ),
        *(
            _backup_info(path, backup_type="Otomatik günlük")
            for path in directory.glob("alphabist-auto-*.db")
        ),
        *(
            _backup_info(path, backup_type="Geri yükleme öncesi")
            for path in directory.glob("alphabist-before-restore-*.db")
        ),
    ]
    backups.sort(key=lambda item: item.modified_at, reverse=True)
    return backups


def prune_manual_backups(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
    *,
    keep_count: int = 10,
) -> tuple[Path, ...]:
    if keep_count < 1:
        raise ValueError("En az bir manuel yedek saklanmalıdır.")

    target_path = _database_path(database_path)
    directory = _backup_directory(target_path, backup_directory)
    if not directory.exists():
        return ()

    manual_paths = sorted(
        directory.glob("alphabist-manual-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    deleted = []
    for path in manual_paths[keep_count:]:
        path.unlink()
        _checksum_path(path).unlink(missing_ok=True)
        deleted.append(path)
    return tuple(deleted)


def prune_automatic_backups(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
    *,
    keep_count: int = 14,
) -> tuple[Path, ...]:
    if keep_count < 1:
        raise ValueError("En az bir otomatik yedek saklanmalıdır.")

    target_path = _database_path(database_path)
    directory = _backup_directory(target_path, backup_directory)
    if not directory.exists():
        return ()

    automatic_paths = sorted(
        directory.glob("alphabist-auto-*.db"),
        key=lambda path: path.name,
        reverse=True,
    )
    deleted = []
    for path in automatic_paths[keep_count:]:
        path.unlink()
        _checksum_path(path).unlink(missing_ok=True)
        deleted.append(path)
    return tuple(deleted)


def create_local_backup(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
    *,
    keep_count: int = 10,
    created_at: datetime | None = None,
) -> SafetyBackupInfo:
    target_path = _database_path(database_path)
    directory = _backup_directory(target_path, backup_directory)
    directory.mkdir(parents=True, exist_ok=True)

    data = create_database_backup(target_path)
    validation = validate_database_backup(data)
    if not validation.valid:
        raise RuntimeError(validation.message)

    timestamp = (created_at or datetime.now()).strftime(
        "%Y%m%d-%H%M%S-%f"
    )
    final_path = directory / f"alphabist-manual-{timestamp}.db"
    temporary_path = directory / f".{final_path.name}.tmp"
    try:
        temporary_path.write_bytes(data)
        temporary_path.replace(final_path)
        _write_checksum_manifest(final_path, data)
    except Exception:
        final_path.unlink(missing_ok=True)
        _checksum_path(final_path).unlink(missing_ok=True)
        raise
    finally:
        temporary_path.unlink(missing_ok=True)

    prune_manual_backups(
        target_path,
        directory,
        keep_count=keep_count,
    )
    return _backup_info(final_path, backup_type="Manuel")


def create_automatic_backup(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
    *,
    keep_count: int = 14,
    created_at: datetime | None = None,
) -> SafetyBackupInfo:
    target_path = _database_path(database_path)
    directory = _backup_directory(target_path, backup_directory)
    directory.mkdir(parents=True, exist_ok=True)

    data = create_database_backup(target_path)
    validation = validate_database_backup(data)
    if not validation.valid:
        raise RuntimeError(validation.message)

    timestamp = (created_at or datetime.now()).strftime(
        "%Y%m%d-%H%M%S-%f"
    )
    final_path = directory / f"alphabist-auto-{timestamp}.db"
    temporary_path = directory / f".{final_path.name}.tmp"
    try:
        temporary_path.write_bytes(data)
        temporary_path.replace(final_path)
        _write_checksum_manifest(final_path, data)
    except Exception:
        final_path.unlink(missing_ok=True)
        _checksum_path(final_path).unlink(missing_ok=True)
        raise
    finally:
        temporary_path.unlink(missing_ok=True)

    prune_automatic_backups(
        target_path,
        directory,
        keep_count=keep_count,
    )
    return _backup_info(
        final_path,
        backup_type="Otomatik günlük",
    )


def ensure_daily_backup(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
    *,
    keep_count: int = 14,
    now: datetime | None = None,
) -> AutomaticBackupResult:
    target_path = _database_path(database_path)
    directory = _backup_directory(target_path, backup_directory)
    current_time = now or datetime.now()
    daily_prefix = f"alphabist-auto-{current_time:%Y%m%d}-"

    if directory.exists():
        candidates = sorted(
            directory.glob(f"{daily_prefix}*.db"),
            key=lambda path: path.name,
            reverse=True,
        )
        for path in candidates:
            backup = _backup_info(
                path,
                backup_type="Otomatik günlük",
            )
            if backup.valid and backup.checksum_valid is True:
                return AutomaticBackupResult(
                    created=False,
                    backup=backup,
                    reason="Bugünün doğrulanmış otomatik yedeği mevcut.",
                )

    backup = create_automatic_backup(
        target_path,
        directory,
        keep_count=keep_count,
        created_at=current_time,
    )
    return AutomaticBackupResult(
        created=True,
        backup=backup,
        reason="Günün doğrulanmış otomatik yedeği oluşturuldu.",
    )


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
    target_existed = target_path.exists()
    safety_backup_path: Path | None = None
    if target_existed:
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
        _write_checksum_manifest(
            safety_backup_path,
            safety_backup_path.read_bytes(),
        )

    try:
        _restore_database_from_bytes(data, target_path)
        restored_validation = validate_database_backup(
            target_path.read_bytes()
        )
        if not restored_validation.valid:
            raise RuntimeError(
                "Geri yüklenen veritabanı doğrulanamadı: "
                + restored_validation.message
            )
    except Exception:
        if safety_backup_path is not None:
            try:
                _restore_database_from_bytes(
                    safety_backup_path.read_bytes(),
                    target_path,
                )
            except Exception:
                pass
        elif not target_existed:
            try:
                target_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return safety_backup_path


def list_safety_backups(
    database_path: Path | None = None,
    backup_directory: Path | None = None,
) -> list[SafetyBackupInfo]:
    target_path = _database_path(database_path)
    safety_directory = _backup_directory(target_path, backup_directory)
    if not safety_directory.exists():
        return []

    backups: list[SafetyBackupInfo] = []
    for path in safety_directory.glob(
        "alphabist-before-restore-*.db"
    ):
        backups.append(
            _backup_info(
                path,
                backup_type="Geri yükleme öncesi",
            )
        )
    backups.sort(key=lambda item: item.modified_at, reverse=True)
    return backups
