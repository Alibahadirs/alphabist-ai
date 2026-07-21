from datetime import date

from app.market_data.export import build_market_health_csv
from app.market_data.health import MarketHealthItem, MarketHealthSummary


def test_market_health_csv_is_utf8_bom_and_human_readable():
    item = MarketHealthItem(
        symbol="THYAO",
        status="Doğrulandı",
        priority=0,
        latest_date=date(2026, 7, 21),
        age_days=0,
        cross_verified=True,
        integrity_valid=True,
        detail="İki kaynak uyumlu",
    )
    summary = MarketHealthSummary(
        items=(item,),
        verified=1,
        partial=0,
        unavailable=0,
        stale=0,
        invalid=0,
    )

    content = build_market_health_csv(summary)

    assert content.startswith(b"\xef\xbb\xbf")
    decoded = content.decode("utf-8-sig")
    assert "Sağlık durumu" in decoded
    assert "THYAO,Doğrulandı,0,2026-07-21,0,Evet,Doğrulandı" in decoded
