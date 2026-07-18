import pandas as pd
from datetime import date

from app.market_data import provider
from app.market_data.freshness import assess_price_freshness
from app.market_data.validation import validate_quote_history_alignment


class _Ticker:
    def history(self, **kwargs):
        return pd.DataFrame(
            {"Close": [100.0, 110.0]},
            index=pd.to_datetime(["2026-07-16", "2026-07-17"]),
        )


def test_get_quote_includes_source_and_price_date(monkeypatch):
    monkeypatch.setattr(provider.yf, "Ticker", lambda symbol: _Ticker())

    quote = provider.get_quote("TEST")

    assert quote["last"] == 110
    assert quote["previous"] == 100
    assert quote["change"] == 10
    assert quote["change_percent"] == 10
    assert quote["as_of_date"] == "2026-07-17"
    assert quote["source"] == "Yahoo Finance"


def test_price_freshness_uses_shared_five_day_rule():
    current = assess_price_freshness(
        date(2026, 7, 13),
        reference_date=date(2026, 7, 18),
    )
    stale = assess_price_freshness(
        date(2026, 7, 12),
        reference_date=date(2026, 7, 18),
    )
    future = assess_price_freshness(
        date(2026, 7, 19),
        reference_date=date(2026, 7, 18),
    )

    assert current.current is True
    assert current.status == "Güncel günlük veri"
    assert current.age_days == 5
    assert stale.current is False
    assert stale.status == "Eski fiyat"
    assert stale.age_days == 6
    assert future.current is False
    assert future.status == "Tarih hatası"
    assert future.age_days == 0


def test_quote_and_history_alignment_accepts_matching_market_data():
    history = pd.DataFrame(
        {"Close": [109.8, 110.0]},
        index=pd.to_datetime(["2026-07-16", "2026-07-17"]),
    )
    result = validate_quote_history_alignment(
        {"last": 110.0, "as_of_date": "2026-07-17"},
        history,
    )

    assert result.valid is True
    assert result.status == "Fiyat ve grafik verisi uyumlu"
    assert result.quote_date == date(2026, 7, 17)
    assert result.history_date == date(2026, 7, 17)
    assert result.price_difference_percent == 0


def test_quote_and_history_alignment_rejects_date_or_price_mismatch():
    history = pd.DataFrame(
        {"Close": [100.0]},
        index=pd.to_datetime(["2026-07-14"]),
    )
    date_mismatch = validate_quote_history_alignment(
        {"last": 100.0, "as_of_date": "2026-07-17"},
        history,
    )
    price_mismatch = validate_quote_history_alignment(
        {"last": 110.0, "as_of_date": "2026-07-14"},
        history,
    )

    assert date_mismatch.valid is False
    assert "3 gün farklı" in date_mismatch.status
    assert price_mismatch.valid is False
    assert "%9.09 farklı" in price_mismatch.status
