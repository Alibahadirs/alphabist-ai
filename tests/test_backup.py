from app.database import repository
from app.database.backup import (
    create_database_backup,
    list_safety_backups,
    restore_database_backup,
    summarize_database_backup,
    validate_database_backup,
)
from app.scoring.models import FinancialMetrics


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
