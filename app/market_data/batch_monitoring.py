from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.market_data.batch_history import MarketBatchRunAudit


@dataclass(frozen=True)
class MarketBatchHistorySummary:
    total_records: int
    valid_records: int
    invalid_records: int
    last_observed_at: datetime | None
    last_verified_rate: float
    average_verified_rate: float
    consecutive_problem_runs: int
    status: str


def build_market_batch_history_summary(
    audits: list[MarketBatchRunAudit],
) -> MarketBatchHistorySummary:
    valid_runs = [
        audit.run
        for audit in audits
        if audit.integrity_valid and audit.run is not None
    ]
    invalid_records = len(audits) - len(valid_runs)
    last_run = valid_runs[0] if valid_runs else None
    total_symbols = sum(run.total for run in valid_runs)
    verified_symbols = sum(run.cross_verified for run in valid_runs)
    average_verified_rate = (
        verified_symbols / total_symbols * 100 if total_symbols else 0.0
    )
    last_verified_rate = (
        last_run.cross_verified / last_run.total * 100
        if last_run and last_run.total
        else 0.0
    )
    consecutive_problem_runs = _consecutive_problem_runs(audits)
    if not audits:
        status = "Veri yok"
    elif invalid_records:
        status = "Bütünlük sorunu"
    elif not valid_runs:
        status = "Doğrulanmış kayıt yok"
    elif last_run and last_run.cross_verified == last_run.total:
        status = "Sağlıklı"
    else:
        status = "İnceleme gerekli"
    return MarketBatchHistorySummary(
        total_records=len(audits),
        valid_records=len(valid_runs),
        invalid_records=invalid_records,
        last_observed_at=last_run.observed_at if last_run else None,
        last_verified_rate=round(last_verified_rate, 2),
        average_verified_rate=round(average_verified_rate, 2),
        consecutive_problem_runs=consecutive_problem_runs,
        status=status,
    )


def _consecutive_problem_runs(
    audits: list[MarketBatchRunAudit],
) -> int:
    count = 0
    for audit in audits:
        run = audit.run
        fully_verified = bool(
            audit.integrity_valid
            and run is not None
            and run.total > 0
            and run.cross_verified == run.total
        )
        if fully_verified:
            break
        count += 1
    return count
