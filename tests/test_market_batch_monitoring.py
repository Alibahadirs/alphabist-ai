import json
from datetime import datetime, timezone

from app.market_data.batch import MarketBatchItem, MarketBatchSummary
from app.market_data.batch_history import (
    audit_market_batch_run_payload,
    build_market_batch_run,
)
from app.market_data.batch_monitoring import build_market_batch_history_summary


def _audit(record_id: int, verified: int, total: int = 2):
    items = tuple(
        MarketBatchItem(
            symbol=f"S{index}",
            diagnostic=None,
            status=("Çapraz doğrulandı" if index < verified else "Veri yok"),
        )
        for index in range(total)
    )
    summary = MarketBatchSummary(
        total=total,
        cross_verified=verified,
        partial=0,
        unavailable=total - verified,
        failed=0,
        items=items,
    )
    run = build_market_batch_run(
        summary,
        observed_at=datetime(2026, 7, 22, 10, record_id, tzinfo=timezone.utc),
    )
    payload = json.dumps(
        run.model_dump(mode="json", exclude={"id", "created_at"}),
        ensure_ascii=False,
    )
    return audit_market_batch_run_payload(
        record_id=record_id,
        run_payload=payload,
        stored_fingerprint=run.fingerprint,
        created_at="2026-07-22 10:00:00",
    )


def test_batch_monitoring_summarizes_weighted_verification_rates():
    audits = [_audit(3, 1), _audit(2, 0), _audit(1, 2)]

    result = build_market_batch_history_summary(audits)

    assert result.status == "İnceleme gerekli"
    assert result.last_verified_rate == 50.0
    assert result.average_verified_rate == 50.0
    assert result.consecutive_problem_runs == 2
    assert result.valid_records == 3


def test_batch_monitoring_prioritizes_integrity_errors():
    valid = _audit(1, 2)
    invalid = valid.__class__(
        id=2,
        run=valid.run,
        integrity_valid=False,
        status="Parmak izi hatası",
        error="eşleşmiyor",
        stored_fingerprint="changed",
        created_at="2026-07-22 10:01:00",
    )

    result = build_market_batch_history_summary([invalid, valid])

    assert result.status == "Bütünlük sorunu"
    assert result.invalid_records == 1
    assert result.consecutive_problem_runs == 1


def test_batch_monitoring_handles_empty_history():
    result = build_market_batch_history_summary([])

    assert result.status == "Veri yok"
    assert result.total_records == 0
    assert result.last_observed_at is None
