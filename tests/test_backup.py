import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta

from app.database import repository
from app.database.backup import (
    BACKUP_BUNDLE_CHECKSUM_NAME,
    BACKUP_BUNDLE_DATABASE_NAME,
    BACKUP_BUNDLE_MANIFEST_NAME,
    compare_backup_to_database,
    create_backup_bundle,
    create_database_backup,
    ensure_daily_backup,
    create_local_backup,
    load_backup_payload,
    list_local_backups,
    list_safety_backups,
    prune_manual_backups,
    restore_database_backup,
    summarize_database_backup,
    validate_backup_bundle,
    validate_database_backup,
)
from app.scoring.models import FinancialMetrics
from app.database.restore_history import list_restore_audits


def _company(symbol: str) -> FinancialMetrics:
    return FinancialMetrics(
        symbol=symbol,
        company_name=f"{symbol} Test Şirketi",
        revenue_growth=10,
        net_profit_growth=15,
        net_margin=8,
        roe=12,
        debt_to_equity=0.5,
        current_ratio=1.5,
        operating_cash_flow=100,
        free_cash_flow=50,
        asset_turnover=0.8,
    )


def _create_database(path, monkeypatch, symbol: str) -> None:
    monkeypatch.setattr(repository, "DB_PATH", path)
    repository.init_db()
    repository.upsert_company(_company(symbol))


def test_database_backup_is_valid_and_contains_required_tables(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch, "SAFE")

    backup_data = create_database_backup(database_path)
    validation = validate_database_backup(backup_data)

    assert validation.valid is True
    assert "companies" in validation.tables
    assert backup_data.startswith(b"SQLite format 3\x00")


def test_portable_backup_bundle_contains_manifest_and_checksum(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch, "BUNDLE")

    bundle_data = create_backup_bundle(
        database_path,
        created_at=datetime(2026, 7, 24, 12, 30),
    )

    with zipfile.ZipFile(io.BytesIO(bundle_data)) as archive:
        assert set(archive.namelist()) == {
            BACKUP_BUNDLE_DATABASE_NAME,
            BACKUP_BUNDLE_CHECKSUM_NAME,
            BACKUP_BUNDLE_MANIFEST_NAME,
        }
        database_data = archive.read(BACKUP_BUNDLE_DATABASE_NAME)
        checksum = archive.read(
            BACKUP_BUNDLE_CHECKSUM_NAME
        ).decode("ascii").strip()
        manifest = json.loads(
            archive.read(BACKUP_BUNDLE_MANIFEST_NAME)
        )

    assert checksum == hashlib.sha256(database_data).hexdigest()
    assert manifest["schema_version"] == 1
    assert manifest["database_file"] == BACKUP_BUNDLE_DATABASE_NAME
    assert manifest["database_sha256"] == checksum
    assert manifest["database_size"] == len(database_data)
    assert manifest["company_count"] == 1
    assert manifest["created_at"] == "2026-07-24T12:30:00"


def _rewrite_bundle(
    bundle_data: bytes,
    replacements: dict[str, bytes],
    *,
    extra_files: dict[str, bytes] | None = None,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(bundle_data)) as source:
        original_files = {
            name: source.read(name)
            for name in source.namelist()
        }
    original_files.update(replacements)
    original_files.update(extra_files or {})
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as target:
        for name, content in original_files.items():
            target.writestr(name, content)
    return output.getvalue()


def test_portable_backup_bundle_is_fully_validated(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch, "VALID")

    validation = validate_backup_bundle(
        create_backup_bundle(database_path)
    )

    assert validation.valid is True
    assert validation.manifest is not None
    assert validation.manifest.company_count == 1
    assert validation.database_data.startswith(b"SQLite format 3\x00")


def test_invalid_zip_is_rejected():
    validation = validate_backup_bundle(b"not a zip")

    assert validation.valid is False
    assert "paketi" in validation.message.lower()


def test_tampered_bundle_checksum_is_rejected(tmp_path, monkeypatch):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch, "TAMPER")
    bundle_data = create_backup_bundle(database_path)
    tampered = _rewrite_bundle(
        bundle_data,
        {BACKUP_BUNDLE_CHECKSUM_NAME: b"0" * 64},
    )

    validation = validate_backup_bundle(tampered)

    assert validation.valid is False
    assert "sha-256" in validation.message.lower()


def test_manifest_count_mismatch_is_rejected(tmp_path, monkeypatch):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch, "COUNT")
    bundle_data = create_backup_bundle(database_path)
    with zipfile.ZipFile(io.BytesIO(bundle_data)) as archive:
        manifest = json.loads(
            archive.read(BACKUP_BUNDLE_MANIFEST_NAME)
        )
    manifest["company_count"] = 99
    tampered = _rewrite_bundle(
        bundle_data,
        {
            BACKUP_BUNDLE_MANIFEST_NAME: json.dumps(
                manifest
            ).encode("utf-8")
        },
    )

    validation = validate_backup_bundle(tampered)

    assert validation.valid is False
    assert "kayıt sayıları" in validation.message.lower()


def test_bundle_with_unexpected_file_is_rejected(tmp_path, monkeypatch):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch, "EXTRA")
    tampered = _rewrite_bundle(
        create_backup_bundle(database_path),
        {},
        extra_files={"../unexpected.txt": b"unsafe"},
    )

    validation = validate_backup_bundle(tampered)

    assert validation.valid is False
    assert "beklenmeyen" in validation.message.lower()


def test_database_file_is_loaded_as_validated_payload(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch, "DATABASE")
    database_data = create_database_backup(database_path)

    payload = load_backup_payload(database_data, "backup.DB")

    assert payload.source_type == "SQLite veritabanı"
    assert payload.database_data == database_data
    assert payload.summary.company_count == 1
    assert payload.manifest is None


def test_zip_file_is_loaded_as_validated_payload(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch, "PORTABLE")

    payload = load_backup_payload(
        create_backup_bundle(database_path),
        "alphabist-backup.ZIP",
    )

    assert payload.source_type == "Taşınabilir ZIP paketi"
    assert payload.summary.company_count == 1
    assert payload.manifest is not None
    assert payload.manifest.database_file == BACKUP_BUNDLE_DATABASE_NAME


def test_unsupported_backup_payload_is_rejected():
    try:
        load_backup_payload(b"content", "backup.txt")
    except ValueError as exc:
        assert ".db veya .zip" in str(exc)
    else:
        raise AssertionError("Desteklenmeyen dosya kabul edilmemeliydi.")


def test_invalid_zip_payload_is_rejected():
    try:
        load_backup_payload(b"not a zip", "backup.zip")
    except ValueError as exc:
        assert "paketi" in str(exc).lower()
    else:
        raise AssertionError("Bozuk ZIP paketi kabul edilmemeliydi.")


def test_invalid_backup_is_rejected():
    validation = validate_database_backup(b"not a database")

    assert validation.valid is False
    assert "SQLite" in validation.message


def test_backup_summary_counts_business_records(tmp_path, monkeypatch):
    database_path = tmp_path / "source.db"
    _create_database(database_path, monkeypatch, "SUMMARY")

    summary = summarize_database_backup(
        create_database_backup(database_path)
    )

    assert summary.company_count == 1
    assert summary.watchlist_count == 0
    assert summary.portfolio_position_count == 0
    assert summary.score_history_count == 0
    assert summary.audit_count == 0
    assert summary.total_business_records == 1


def test_invalid_backup_cannot_be_summarized():
    try:
        summarize_database_backup(b"not a database")
    except ValueError as exc:
        assert "SQLite" in str(exc)
    else:
        raise AssertionError("Geçersiz yedek özetlenmemeliydi.")


def test_local_backup_is_written_and_validated(tmp_path, monkeypatch):
    database_path = tmp_path / "source.db"
    backup_directory = tmp_path / "backups"
    _create_database(database_path, monkeypatch, "LOCAL")

    backup = create_local_backup(
        database_path,
        backup_directory,
        created_at=datetime(2026, 7, 23, 10, 30),
    )

    assert backup.path.exists()
    assert backup.valid is True
    assert backup.backup_type == "Manuel"
    assert backup.checksum_valid is True
    assert backup.checksum_status == "Doğrulandı"
    assert len(backup.checksum_sha256) == 64
    assert backup.path.with_suffix(".db.sha256").exists()
    assert backup.file_name.startswith("alphabist-manual-20260723")
    assert summarize_database_backup(
        backup.path.read_bytes()
    ).company_count == 1


def test_manual_backup_retention_keeps_newest_files(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    backup_directory = tmp_path / "backups"
    _create_database(database_path, monkeypatch, "RETENTION")
    start = datetime(2026, 7, 23, 10, 0)

    for offset in range(4):
        create_local_backup(
            database_path,
            backup_directory,
            keep_count=2,
            created_at=start + timedelta(minutes=offset),
        )

    backups = list_local_backups(database_path, backup_directory)

    assert len(backups) == 2
    assert all(item.backup_type == "Manuel" for item in backups)
    assert "100300" in backups[0].file_name
    assert "100200" in backups[1].file_name
    assert len(list(backup_directory.glob("*.sha256"))) == 2


def test_manual_backup_retention_requires_at_least_one_copy(tmp_path):
    try:
        prune_manual_backups(
            tmp_path / "source.db",
            tmp_path / "backups",
            keep_count=0,
        )
    except ValueError as exc:
        assert "en az bir" in str(exc).lower()
    else:
        raise AssertionError("Sıfır yedek saklama kabul edilmemeliydi.")


def test_checksum_mismatch_marks_local_backup_invalid(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    backup_directory = tmp_path / "backups"
    _create_database(database_path, monkeypatch, "CHECKSUM")
    backup = create_local_backup(database_path, backup_directory)
    backup.path.with_suffix(".db.sha256").write_text(
        "0" * 64,
        encoding="ascii",
    )

    listed = list_local_backups(database_path, backup_directory)

    assert len(listed) == 1
    assert listed[0].valid is False
    assert listed[0].checksum_valid is False
    assert listed[0].checksum_status == "Uyuşmazlık"


def test_daily_backup_is_created_only_once_per_day(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    backup_directory = tmp_path / "backups"
    _create_database(database_path, monkeypatch, "DAILY")
    morning = datetime(2026, 7, 24, 9, 0)

    first = ensure_daily_backup(
        database_path,
        backup_directory,
        now=morning,
    )
    second = ensure_daily_backup(
        database_path,
        backup_directory,
        now=morning + timedelta(hours=5),
    )

    assert first.created is True
    assert second.created is False
    assert first.backup.path == second.backup.path
    assert second.backup.checksum_valid is True
    assert len(list(backup_directory.glob("alphabist-auto-*.db"))) == 1


def test_invalid_daily_backup_is_replaced(tmp_path, monkeypatch):
    database_path = tmp_path / "source.db"
    backup_directory = tmp_path / "backups"
    _create_database(database_path, monkeypatch, "REPLACE")
    morning = datetime(2026, 7, 24, 9, 0)
    first = ensure_daily_backup(
        database_path,
        backup_directory,
        now=morning,
    )
    first.backup.path.with_suffix(".db.sha256").write_text(
        "0" * 64,
        encoding="ascii",
    )

    replacement = ensure_daily_backup(
        database_path,
        backup_directory,
        now=morning + timedelta(hours=1),
    )

    assert replacement.created is True
    assert replacement.backup.path != first.backup.path
    assert replacement.backup.valid is True


def test_automatic_backup_retention_keeps_newest_days(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    backup_directory = tmp_path / "backups"
    _create_database(database_path, monkeypatch, "AUTO")
    start = datetime(2026, 7, 20, 8, 0)

    for offset in range(4):
        ensure_daily_backup(
            database_path,
            backup_directory,
            keep_count=2,
            now=start + timedelta(days=offset),
        )

    backups = [
        item
        for item in list_local_backups(
            database_path,
            backup_directory,
        )
        if item.backup_type == "Otomatik günlük"
    ]

    assert len(backups) == 2
    assert "20260723" in backups[0].file_name
    assert "20260722" in backups[1].file_name


def test_backup_comparison_reports_incoming_record_deltas(
    tmp_path, monkeypatch
):
    current_path = tmp_path / "current.db"
    incoming_path = tmp_path / "incoming.db"
    _create_database(current_path, monkeypatch, "CURRENT")
    _create_database(incoming_path, monkeypatch, "INCOMING")
    monkeypatch.setattr(repository, "DB_PATH", incoming_path)
    repository.upsert_company(_company("SECOND"))

    comparison = compare_backup_to_database(
        create_database_backup(incoming_path),
        current_path,
    )

    assert comparison.current.company_count == 1
    assert comparison.incoming.company_count == 2
    assert comparison.company_delta == 1
    assert comparison.watchlist_delta == 0
    assert comparison.portfolio_position_delta == 0


def test_restore_replaces_data_and_keeps_safety_backup(
    tmp_path, monkeypatch
):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    safety_directory = tmp_path / "safety"

    _create_database(source_path, monkeypatch, "NEW")
    backup_data = create_database_backup(source_path)
    _create_database(target_path, monkeypatch, "OLD")

    safety_path = restore_database_backup(
        backup_data,
        target_path,
        safety_directory,
    )

    monkeypatch.setattr(repository, "DB_PATH", target_path)
    assert [company.symbol for company in repository.list_companies()] == [
        "NEW"
    ]
    assert safety_path is not None
    assert safety_path.exists()
    safety_validation = validate_database_backup(
        safety_path.read_bytes()
    )
    assert safety_validation.valid is True

    backups = list_safety_backups(
        target_path,
        safety_directory,
    )
    assert len(backups) == 1
    assert backups[0].path == safety_path
    assert backups[0].valid is True
    assert backups[0].size_bytes > 0
    assert backups[0].checksum_valid is True
    assert safety_path.with_suffix(".db.sha256").exists()
    restore_audits = list_restore_audits(target_path)
    assert len(restore_audits) == 1
    assert restore_audits[0].status == "Başarılı"
    assert restore_audits[0].source_file_name == "alphabist-yedek.db"
    assert restore_audits[0].incoming_company_count == 1
    assert restore_audits[0].integrity_valid is True


def test_restore_failure_keeps_original_database(
    tmp_path, monkeypatch
):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    safety_directory = tmp_path / "safety"
    _create_database(source_path, monkeypatch, "NEW")
    incoming = create_database_backup(source_path)
    _create_database(target_path, monkeypatch, "OLD")

    def fail_before_replace(_data, _target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(
        "app.database.backup._restore_database_from_bytes",
        fail_before_replace,
    )

    try:
        restore_database_backup(
            incoming,
            target_path,
            safety_directory,
        )
    except OSError as exc:
        assert "simulated" in str(exc)
    else:
        raise AssertionError("Geri yükleme hatası bekleniyordu.")

    monkeypatch.setattr(repository, "DB_PATH", target_path)
    assert [company.symbol for company in repository.list_companies()] == [
        "OLD"
    ]
    assert len(list_safety_backups(target_path, safety_directory)) == 1
    restore_audits = list_restore_audits(target_path)
    assert len(restore_audits) == 1
    assert restore_audits[0].status == "Başarısız"
    assert "simulated" in restore_audits[0].message


def test_invalid_restore_attempt_is_audited(tmp_path, monkeypatch):
    target_path = tmp_path / "target.db"
    _create_database(target_path, monkeypatch, "CURRENT")

    try:
        restore_database_backup(
            b"invalid",
            target_path,
            source_type="Taşınabilir ZIP paketi",
            source_file_name="broken.zip",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Geçersiz geri yükleme reddedilmeliydi.")

    restore_audits = list_restore_audits(target_path)
    assert len(restore_audits) == 1
    assert restore_audits[0].status == "Başarısız"
    assert restore_audits[0].source_file_name == "broken.zip"


def test_safety_backups_are_listed_newest_first(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "source.db"
    safety_directory = tmp_path / "safety"
    _create_database(database_path, monkeypatch, "SAFE")
    backup_data = create_database_backup(database_path)

    first = restore_database_backup(
        backup_data,
        database_path,
        safety_directory,
    )
    second = restore_database_backup(
        backup_data,
        database_path,
        safety_directory,
    )

    backups = list_safety_backups(
        database_path,
        safety_directory,
    )
    assert len(backups) == 2
    assert first is not None
    assert second is not None
    assert backups[0].modified_at >= backups[1].modified_at
    assert {item.path for item in backups} == {first, second}
