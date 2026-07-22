from datetime import datetime, timezone

from app.market_data.batch import MarketBatchItem, MarketBatchSummary
from app.market_data.batch_history import build_market_batch_run
from app.market_data.export import build_market_batch_run_csv


def test_market_batch_run_csv_contains_run_and_item_evidence():
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
        observed_at=datetime(2026, 7, 22, 10, 30, tzinfo=timezone.utc),
    )

    content = build_market_batch_run_csv([run])

    assert content.startswith(b"\xef\xbb\xbf")
    decoded = content.decode("utf-8-sig")
    assert "Çalışma bütünlüğü" in decoded
    assert "THYAO,Hata,Bağlantı kurulamadı" in decoded
    assert run.fingerprint in decoded
