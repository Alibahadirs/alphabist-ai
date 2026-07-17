from app.database import repository
from app.database.backup import (
    create_database_backup,
    restore_database_backup,
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
