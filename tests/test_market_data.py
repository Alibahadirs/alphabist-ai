import pandas as pd

from app.market_data import provider


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
