from datetime import date

from app.market_data.health import build_market_health_summary
from app.market_data.models import (
    MarketDiagnosticSnapshot,
    market_snapshot_fingerprint,
)


def _snapshot(
    symbol: str,
    *,
    quote_date: date | None,
    available: bool = True,
    cross_verified: bool = True,
) -> MarketDiagnosticSnapshot:
    snapshot = MarketDiagnosticSnapshot(
        symbol=symbol,
        primary_available=available,
        secondary_available=available,
        primary_eligible=available,
        secondary_eligible=available,
        primary_price=100 if available else None,
        secondary_price=100 if available else None,
        primary_date=quote_date,
        secondary_date=quote_date,
        price_difference_percent=0 if available else None,
        change_difference_points=0 if available else None,
        date_gap_days=0 if available else None,
        cross_verified=cross_verified,
        status="Test durumu",
    )
    return snapshot.model_copy(
        update={"fingerprint": market_snapshot_fingerprint(snapshot)}
    )


def test_market_health_summary_classifies_and_prioritizes_items():
    verified = _snapshot("AKSA", quote_date=date(2026, 7, 21))
    partial = _snapshot(
        "THYAO",
        quote_date=date(2026, 7, 21),
        cross_verified=False,
    )
    stale = _snapshot("GARAN", quote_date=date(2026, 7, 10))
    tampered = _snapshot("ASELS", quote_date=date(2026, 7, 21)).model_copy(
        update={"primary_price": 999}
    )

    summary = build_market_health_summary(
        ["AKSA", "THYAO", "GARAN", "ASELS", "BIMAS"],
        [verified, partial, stale, tampered],
        reference_date=date(2026, 7, 21),
    )

    assert [item.symbol for item in summary.items] == [
        "ASELS",
        "GARAN",
        "BIMAS",
        "THYAO",
        "AKSA",
    ]
    assert summary.verified == 1
    assert summary.partial == 1
    assert summary.unavailable == 1
    assert summary.stale == 1
    assert summary.invalid == 1


def test_market_health_marks_snapshot_without_quotes_as_unavailable():
    empty = _snapshot(
        "AKSA",
        quote_date=None,
        available=False,
        cross_verified=False,
    )

    summary = build_market_health_summary(
        ["AKSA"],
        [empty],
        reference_date=date(2026, 7, 21),
    )

    assert summary.items[0].status == "Veri yok"
    assert summary.items[0].detail == "Test durumu"
