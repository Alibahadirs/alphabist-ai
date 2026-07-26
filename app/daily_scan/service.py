from __future__ import annotations

from datetime import datetime

from app.daily_scan.analysis import assess_symbol
from app.daily_scan.models import DailyScanResult
from app.daily_scan.provider import fetch_bist_symbols, load_histories


def run_scan(symbols: list[str] | None = None, limit: int | None = None) -> DailyScanResult:
    requested = symbols or fetch_bist_symbols()
    if limit:
        requested = requested[:limit]
    histories, failures = load_histories(requested)
    assessments = []
    for symbol, history in histories.items():
        try:
            assessments.append(assess_symbol(symbol, history))
        except Exception as exc:
            failures[symbol] = str(exc)
    dates = [item.price_date for item in assessments]
    return DailyScanResult(
        generated_at=datetime.now(),
        market_date=max(dates) if dates else None,
        requested_symbols=len(requested),
        successful_symbols=len(assessments),
        failed_symbols=len(failures),
        assessments=assessments,
        failures=failures,
    )
