from datetime import date

from app.market_data.diagnostics import diagnose_market_data
from app.market_data.models import (
    build_market_diagnostic_snapshot,
    market_snapshot_fingerprint,
)


def _quote(source: str, price: float):
    return {
        "last": price,
        "previous": 98,
        "change_percent": (price - 98) / 98 * 100,
        "as_of_date": "2026-07-21",
        "source": source,
        "data_mode": "delayed",
        "official": False,
    }


def test_snapshot_captures_verified_market_evidence():
    diagnostic = diagnose_market_data(
        "thyao",
        reference_date=date(2026, 7, 21),
        yahoo_loader=lambda symbol: _quote("Yahoo Finance", 100),
        borsa_loader=lambda symbol: _quote(
            "borsa-api / Yahoo Finance",
            100,
        ),
    )

    snapshot = build_market_diagnostic_snapshot(diagnostic)

    assert snapshot.symbol == "THYAO"
    assert snapshot.cross_verified is True
    assert snapshot.primary_price == 100
    assert snapshot.secondary_date == date(2026, 7, 21)
    assert len(snapshot.fingerprint) == 64


def test_snapshot_fingerprint_is_stable_and_content_sensitive():
    diagnostic = diagnose_market_data(
        "THYAO",
        reference_date=date(2026, 7, 21),
        yahoo_loader=lambda symbol: _quote("Yahoo Finance", 100),
        borsa_loader=lambda symbol: _quote(
            "borsa-api / Yahoo Finance",
            100,
        ),
    )
    first = build_market_diagnostic_snapshot(diagnostic)
    repeated = build_market_diagnostic_snapshot(diagnostic)
    changed = first.model_copy(update={"primary_price": 101})

    assert first.fingerprint == repeated.fingerprint
    assert market_snapshot_fingerprint(changed) != first.fingerprint
