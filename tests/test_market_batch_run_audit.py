import json
from datetime import datetime, timezone

from app.market_data.batch import MarketBatchItem, MarketBatchSummary
from app.market_data.batch_history import (
    audit_market_batch_run_payload,
    build_market_batch_run,
)


def _run():
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
    return build_market_batch_run(
        summary,
        observed_at=datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc),
    )


def _payload(run) -> str:
    return json.dumps(
        run.model_dump(mode="json", exclude={"id", "created_at"}),
        ensure_ascii=False,
    )


def test_market_batch_run_audit_accepts_valid_record():
    run = _run()

    audit = audit_market_batch_run_payload(
        record_id=7,
        run_payload=_payload(run),
        stored_fingerprint=run.fingerprint,
        created_at="2026-07-22 12:00:01",
    )

    assert audit.integrity_valid is True
    assert audit.status == "Doğrulandı"
    assert audit.run is not None
    assert audit.run.id == 7


def test_market_batch_run_audit_reports_malformed_json():
    audit = audit_market_batch_run_payload(
        record_id=8,
        run_payload="{not-json",
        stored_fingerprint="abc",
        created_at="2026-07-22 12:00:01",
    )

    assert audit.integrity_valid is False
    assert audit.status == "Yük bozuk"
    assert audit.run is None


def test_market_batch_run_audit_reports_schema_and_counter_error():
    run = _run()
    payload = run.model_dump(mode="json", exclude={"id", "created_at"})
    payload["failed"] = 0

    audit = audit_market_batch_run_payload(
        record_id=9,
        run_payload=json.dumps(payload, ensure_ascii=False),
        stored_fingerprint=run.fingerprint,
        created_at="2026-07-22 12:00:01",
    )

    assert audit.integrity_valid is False
    assert audit.status == "Şema hatası"
    assert audit.run is None


def test_market_batch_run_audit_reports_fingerprint_mismatch():
    run = _run()

    audit = audit_market_batch_run_payload(
        record_id=10,
        run_payload=_payload(run),
        stored_fingerprint="changed",
        created_at="2026-07-22 12:00:01",
    )

    assert audit.integrity_valid is False
    assert audit.status == "Parmak izi hatası"
    assert audit.run is not None
