import sqlite3

from app.core.preflight import REQUIRED_MODULES, run_preflight


def _all_modules_available(_module_name: str) -> object:
    return object()


def test_preflight_accepts_supported_environment(tmp_path):
    database_path = tmp_path / "alphabist.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample(id INTEGER)")

    report = run_preflight(
        database_path=database_path,
        data_dir=tmp_path,
        version_info=(3, 14, 0),
        module_finder=_all_modules_available,
    )

    assert report.ready is True
    assert report.error_count == 0
    assert report.warning_count == 0
    assert {check.status for check in report.checks} == {"Hazır"}


def test_missing_database_is_a_non_blocking_first_run_warning(tmp_path):
    report = run_preflight(
        database_path=tmp_path / "missing.db",
        data_dir=tmp_path,
        version_info=(3, 11, 0),
        module_finder=_all_modules_available,
    )

    database_check = next(
        check for check in report.checks if check.key == "database"
    )
    assert report.ready is True
    assert report.warning_count == 1
    assert database_check.status == "Uyarı"


def test_missing_dependency_blocks_startup(tmp_path):
    missing_module = REQUIRED_MODULES[0][0]

    report = run_preflight(
        database_path=tmp_path / "missing.db",
        data_dir=tmp_path,
        version_info=(3, 11, 0),
        module_finder=lambda name: (
            None if name == missing_module else object()
        ),
    )

    assert report.ready is False
    assert report.error_count == 1
    assert any(
        check.key == f"dependency:{missing_module}"
        and check.blocking
        for check in report.checks
    )


def test_unsupported_python_blocks_startup(tmp_path):
    report = run_preflight(
        database_path=tmp_path / "missing.db",
        data_dir=tmp_path,
        version_info=(3, 10, 9),
        module_finder=_all_modules_available,
    )

    assert report.ready is False
    python_check = next(
        check for check in report.checks if check.key == "python"
    )
    assert python_check.status == "Hata"
    assert python_check.blocking is True


def test_corrupted_database_blocks_startup(tmp_path):
    database_path = tmp_path / "broken.db"
    database_path.write_bytes(b"not sqlite")

    report = run_preflight(
        database_path=database_path,
        data_dir=tmp_path,
        version_info=(3, 11, 0),
        module_finder=_all_modules_available,
    )

    assert report.ready is False
    database_check = next(
        check for check in report.checks if check.key == "database"
    )
    assert database_check.status == "Hata"
