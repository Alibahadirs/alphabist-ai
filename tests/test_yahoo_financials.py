import pandas as pd

from app.market_data import yahoo_financials


def _frame(rows):
    columns = pd.to_datetime(["2026-03-31", "2025-03-31"])
    return pd.DataFrame(rows, index=columns).T


class _Ticker:
    def __init__(self, symbol):
        assert symbol == "THYAO.IS"

    def get_income_stmt(self, freq):
        assert freq == "quarterly"
        return _frame({
            "TotalRevenue": [150, 100],
            "NetIncome": [30, 20],
        })

    def get_balance_sheet(self, freq):
        assert freq == "quarterly"
        return _frame({
            "StockholdersEquity": [300, 250], "TotalDebt": [120, 100],
            "CurrentAssets": [200, 180], "CurrentLiabilities": [100, 90],
            "TotalAssets": [600, 500], "CashAndCashEquivalents": [50, 40],
        })

    def get_cash_flow(self, freq):
        assert freq == "quarterly"
        return _frame({"OperatingCashFlow": [40, 30], "CapitalExpenditure": [-10, -8]})

    def get_info(self):
        return {"longName": "Türk Hava Yolları A.O."}


def test_fetch_yahoo_financials_builds_comparable_quarter(monkeypatch):
    monkeypatch.setattr(yahoo_financials.yf, "Ticker", _Ticker)
    result = yahoo_financials.fetch_yahoo_financials("thyao")
    assert result.yahoo_symbol == "THYAO.IS"
    assert result.current_period.isoformat() == "2026-03-31"
    assert result.comparison_period.isoformat() == "2025-03-31"
    assert result.draft.revenue == 150
    assert result.draft.previous_revenue == 100
    assert result.draft.operating_cash_flow == 40


def test_fetch_yahoo_financials_rejects_invalid_symbol():
    try:
        yahoo_financials.fetch_yahoo_financials("platform")
    except ValueError as exc:
        assert "Geçerli" in str(exc)
    else:
        raise AssertionError("Geçersiz sembol reddedilmeliydi")
