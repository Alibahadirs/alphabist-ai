from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime

from app.core.exceptions import DataProviderError
from app.market_data.quote import normalize_quote_values


BORSA_API_SOURCE = "borsa-api / Yahoo Finance"
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_SYMBOL = re.compile(r"^[A-Z0-9]{1,12}$")
_DATE = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")
_TRY_VALUE = re.compile(r"(-?\d+(?:\.\d+)?)\s*₺")


def is_borsa_api_available() -> bool:
    return shutil.which("borsa") is not None


def get_borsa_api_quote(
    symbol: str,
    timeout_seconds: int = 20,
) -> dict[str, float | str | bool | None]:
    normalized_symbol = symbol.strip().upper()
    if not _SYMBOL.fullmatch(normalized_symbol):
        raise DataProviderError("borsa-api için hisse kodu geçersiz.")

    executable = shutil.which("borsa")
    if executable is None:
        raise DataProviderError(
            "borsa-api bulunamadı. 'npm install -g borsa-api' çalıştırın."
        )

    try:
        result = subprocess.run(
            [executable, "gecmis", normalized_symbol, "5d"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DataProviderError(f"borsa-api çalıştırılamadı: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise DataProviderError(
            f"borsa-api veri hatası: {detail or 'bilinmeyen hata'}"
        )
    return parse_borsa_api_history(result.stdout)


def parse_borsa_api_history(
    output: str,
) -> dict[str, float | str | bool | None]:
    rows: list[tuple[datetime, float]] = []
    for raw_line in _ANSI_ESCAPE.sub("", output).splitlines():
        date_match = _DATE.search(raw_line)
        values = _TRY_VALUE.findall(raw_line)
        if date_match is None or len(values) < 4:
            continue
        rows.append(
            (
                datetime.strptime(date_match.group(1), "%d.%m.%Y"),
                float(values[3]),
            )
        )

    rows.sort(key=lambda item: item[0])
    if len(rows) < 2:
        raise DataProviderError(
            "borsa-api çıktısında en az iki kapanış bulunamadı."
        )

    previous = rows[-2][1]
    last = rows[-1][1]
    normalized = normalize_quote_values(last=last, previous=previous)
    return {
        "last": normalized.last,
        "previous": normalized.previous,
        "change": normalized.change,
        "change_percent": normalized.change_percent,
        "as_of_date": rows[-1][0].date().isoformat(),
        "source": BORSA_API_SOURCE,
        "data_mode": "delayed",
        "official": False,
        "percent_corrected": normalized.percent_corrected,
    }
