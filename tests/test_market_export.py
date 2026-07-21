from app.market_data.export import build_market_diagnostic_csv
from app.market_data.models import (
    MarketDiagnosticSnapshot,
    market_snapshot_fingerprint,
)


def _snapshot():
    item = MarketDiagnosticSnapshot(
        symbol="THYAO",
        primary_available=True,
        secondary_available=True,
        primary_eligible=True,
        secondary_eligible=True,
        primary_price=317.5,
        secondary_price=317.5,
        price_difference_percent=0,
        cross_verified=True,
        status="İki sağlayıcı doğrulandı",
        created_at="2026-07-21 21:30:00",
    )
    return item.model_copy(
        update={"fingerprint": market_snapshot_fingerprint(item)}
    )


def test_market_diagnostic_csv_is_utf8_and_contains_integrity():
    content = build_market_diagnostic_csv([_snapshot()])
    text = content.decode("utf-8-sig")

    assert text.startswith("Hisse,Kontrol zamanı")
    assert "THYAO" in text
    assert "Çapraz doğrulandı" in text
    assert "Doğrulandı" in text
