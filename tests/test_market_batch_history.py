from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.market_data.batch import MarketBatchItem, MarketBatchSummary
from app.market_data.batch_history import (
    MarketBatchRun,
    build_market_batch_run,
    market_batch_run_fingerprint,
)


def _summary() -> MarketBatchSummary:
    return MarketBatchSummary(
        total=2,
        cross_verified=0,
        partial=0,
        unavailable=1,
        failed=1,
        items=(
            MarketBatchItem(
                symbol="AKSA",
                diagnostic=None,
                status="Veri yok",
            ),
            MarketBatchItem(
                symbol="THYAO",
                diagnostic=None,
                status="Hata",
                error="Bağlantı kurulamadı",
            ),
        ),
    )


def test_market_batch_run_builds_integrity_protected_record():
    observed_at = datetime(2026, 7, 22, 9, 30, tzinfo=timezone.utc)

    run = build_market_batch_run(_summary(), observed_at=observed_at)

    assert run.observed_at == observed_at
    assert run.items[1].detail == "Bağlantı kurulamadı"
    assert run.fingerprint == market_batch_run_fingerprint(run)


def test_market_batch_run_rejects_counter_mismatch():
    valid = build_market_batch_run(_summary())
    payload = valid.model_dump()
    payload["failed"] = 0

    with pytest.raises(ValidationError, match="sayaçları sonuçlarla uyuşmuyor"):
        MarketBatchRun(**payload)


def test_market_batch_run_fingerprint_changes_with_observation_time():
    first = build_market_batch_run(
        _summary(),
        observed_at=datetime(2026, 7, 22, 9, 30, tzinfo=timezone.utc),
    )
    second = build_market_batch_run(
        _summary(),
        observed_at=datetime(2026, 7, 22, 9, 31, tzinfo=timezone.utc),
    )

    assert first.fingerprint != second.fingerprint
