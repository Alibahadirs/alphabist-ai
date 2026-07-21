from app.market_data.history import build_market_diagnostic_trend
from app.market_data.models import (
    MarketDiagnosticSnapshot,
    market_snapshot_fingerprint,
)


def _snapshot(
    status: str,
    verified: bool,
    difference: float,
) -> MarketDiagnosticSnapshot:
    item = MarketDiagnosticSnapshot(
        symbol="THYAO",
        primary_available=True,
        secondary_available=verified,
        primary_eligible=True,
        secondary_eligible=verified,
        primary_price=100,
        secondary_price=100 - difference,
        price_difference_percent=difference,
        cross_verified=verified,
        status=status,
    )
    return item.model_copy(
        update={"fingerprint": market_snapshot_fingerprint(item)}
    )


def test_market_history_summarizes_verification_trend():
    history = [
        _snapshot("Doğrulandı", True, 0.10),
        _snapshot("Tek kaynak", False, 0.20),
        _snapshot("Uyumsuz", False, 0.35),
    ]

    trend = build_market_diagnostic_trend(history)

    assert trend.total_records == 3
    assert trend.valid_records == 3
    assert trend.verified_records == 1
    assert trend.verified_rate == 33.33
    assert trend.consecutive_unverified == 2
    assert trend.latest_status == "Uyumsuz"
    assert trend.status_changed is True
    assert trend.price_difference_delta == 0.15


def test_market_history_excludes_tampered_snapshot():
    valid = _snapshot("Doğrulandı", True, 0.10)
    tampered = valid.model_copy(update={"primary_price": 999})

    trend = build_market_diagnostic_trend([valid, tampered])

    assert trend.total_records == 2
    assert trend.valid_records == 1
    assert trend.invalid_records == 1
    assert trend.verified_rate == 100


def test_empty_market_history_is_safe():
    trend = build_market_diagnostic_trend([])

    assert trend.total_records == 0
    assert trend.latest_status == "Kayıt yok"
    assert trend.verified_rate == 0
