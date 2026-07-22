import json
from datetime import datetime, timezone

from app.market_data.batch import MarketBatchItem, MarketBatchSummary
from app.market_data.batch_history import (
    audit_market_batch_run_payload,
    build_market_batch_run,
)
from app.market_data.export import build_market_batch_audit_csv


def _valid_audit():
    summary = MarketBatchSummary(
        total=1,
        cross_verified=0,
        partial=0,
        unavailable=0,
        failed=1,
        items=(
            MarketBatchItem(
                symbol="THYAO",
                diagnostic=None,
                status="Hata",
                error="Bağlantı kurulamadı",
            ),
        ),
    )
    run = build_market_batch_run(
        summary,
        observed_at=datetime(2026, 7, 22, 14, 0, tzinfo=timezone.utc),
    )
    return audit_market_batch_run_payload(
        record_id=1,
        run_payload=json.dumps(
            run.model_dump(mode="json", exclude={"id", "created_at"}),
            ensure_ascii=False,
        ),
        stored_fingerprint=run.fingerprint,
        created_at="2026-07-22 14:00:01",
    )


def test_batch_audit_csv_includes_valid_and_invalid_records():
    valid = _valid_audit()
    invalid = audit_market_batch_run_payload(
        record_id=2,
        run_payload="{bad-json",
        stored_fingerprint="changed",
        created_at="2026-07-22 14:01:00",
    )

    content = build_market_batch_audit_csv([invalid, valid])

    decoded = content.decode("utf-8-sig")
    assert "Denetim durumu" in decoded
    assert "THYAO,Hata,Bağlantı kurulamadı" in decoded
    assert "Yük bozuk" in decoded
    assert "changed" in decoded
