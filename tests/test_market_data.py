import pandas as pd
from datetime import date

from app.market_data import provider
from app.market_data.freshness import assess_price_freshness


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
