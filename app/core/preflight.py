from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from app.core.settings import settings


REQUIRED_MODULES = (
    ("streamlit", "Streamlit"),
    ("pandas", "Pandas"),
    ("numpy", "NumPy"),
    ("pydantic", "Pydantic"),
    ("yfinance", "Yahoo Finance"),
    ("pypdf", "PDF okuyucu"),
    ("ta", "Teknik analiz"),
)


@dataclass(frozen=True)
class PreflightCheck:
    key: str
    label: str
    status: str
    detail: str
    blocking: bool = False


@dataclass(frozen=True)
class PreflightReport:
    checks: tuple[PreflightCheck, ...]

    @property
    def ready(self) -> bool:
        return not any(check.blocking for check in self.checks)

    @property
    def error_count(self) -> int:
        return sum(check.blocking for check in self.checks)

    @property
    def warning_count(self) -> int:
        return sum(
            check.status == "Uyarı" for check in self.checks
        )


def _python_check(version_info: Sequence[int]) -> PreflightCheck:
    major, minor = version_info[:2]
    supported = (major, minor) >= (3, 11)
    return PreflightCheck(
        key="python",
        label="Python",
        status="Hazır" if supported else "Hata",
        detail=f"{major}.{minor}",
        blocking=not supported,
    )


def _dependency_checks(
    module_finder: Callable[[str], object | None],
) -> list[PreflightCheck]:
    checks = []
    for module_name, label in REQUIRED_MODULES:
        available = module_finder(module_name) is not None
        checks.append(
            PreflightCheck(
                key=f"dependency:{module_name}",
                label=label,
                status="Hazır" if available else "Hata",
                detail=(
                    "Kurulu"
                    if available
                    else f"Eksik Python paketi: {module_name}"
                ),
                blocking=not available,
            )
        )
    return checks


def _data_directory_check(data_dir: Path) -> PreflightCheck:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=data_dir):
            pass
    except OSError as exc:
        return PreflightCheck(
            key="data_directory",
            label="Yerel veri klasörü",
            status="Hata",
            detail=f"Yazılamıyor: {exc}",
            blocking=True,
        )
    return PreflightCheck(
        key="data_directory",
        label="Yerel veri klasörü",
        status="Hazır",
        detail=str(data_dir),
    )


def _database_check(database_path: Path) -> PreflightCheck:
    if not database_path.exists():
        return PreflightCheck(
            key="database",
            label="SQLite veritabanı",
            status="Uyarı",
            detail="İlk açılışta otomatik oluşturulacak.",
        )
    try:
        with sqlite3.connect(database_path) as connection:
            result = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()[0]
    except sqlite3.DatabaseError as exc:
        return PreflightCheck(
            key="database",
            label="SQLite veritabanı",
            status="Hata",
            detail=f"Okunamıyor: {exc}",
            blocking=True,
        )
    healthy = result == "ok"
    return PreflightCheck(
        key="database",
        label="SQLite veritabanı",
        status="Hazır" if healthy else "Hata",
        detail="Bütünlük doğrulandı." if healthy else str(result),
        blocking=not healthy,
    )


def run_preflight(
    *,
    database_path: Path | None = None,
    data_dir: Path | None = None,
    version_info: Sequence[int] | None = None,
    module_finder: Callable[[str], object | None] | None = None,
) -> PreflightReport:
    selected_data_dir = data_dir or settings.data_dir
    selected_database_path = database_path or settings.database_path
    finder = module_finder or importlib.util.find_spec
    checks = [
        _python_check(version_info or sys.version_info),
        *_dependency_checks(finder),
        _data_directory_check(selected_data_dir),
        _database_check(selected_database_path),
    ]
    return PreflightReport(checks=tuple(checks))


def main() -> int:
    report = run_preflight()
    for check in report.checks:
        print(f"[{check.status}] {check.label}: {check.detail}")
    if report.ready:
        print("AlphaBIST AI başlatılmaya hazır.")
        return 0
    print("Başlangıç engellendi. Hata durumlarını düzeltin.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
