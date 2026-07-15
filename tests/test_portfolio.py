import pytest

from app.database import repository
from app.portfolio.models import PortfolioPosition
from app.portfolio.service import build_portfolio_summary
from app.scoring.models import FinancialMetrics


def _company() -> FinancialMetrics:
    return FinancialMetrics(
        symbol="TEST",
        company_name="Test Şirketi",
        revenue_growth=20,
        net_profit_growth=25,
        net_margin=15,
        roe=25,
        debt_to_equity=0.5,
        current_ratio=1.8,
        operating_cash_flow=100,
        free_cash_flow=50,
        asset_turnover=0.8,
        valuation_score_input=75,
        management_score_input=80,
        risk_score_input=70,
    )


def test_portfolio_repository_adds_updates_and_removes(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.upsert_company(_company())

    repository.upsert_portfolio_position(
        PortfolioPosition(symbol="test", quantity=10, average_cost=20)
    )
    repository.upsert_portfolio_position(
        PortfolioPosition(symbol="TEST", quantity=12, average_cost=22)
    )

    positions = repository.list_portfolio_positions()
    assert positions == [
        PortfolioPosition(symbol="TEST", quantity=12, average_cost=22)
    ]

    repository.remove_portfolio_position("test")
    assert repository.list_portfolio_positions() == []


def test_portfolio_summary_calculates_return_and_weighted_alpha():
    company = _company()
    summary = build_portfolio_summary(
        [PortfolioPosition(symbol="TEST", quantity=10, average_cost=20)],
        {"TEST": company},
        {"TEST": 25},
    )

    assert summary.total_cost == 200
    assert summary.total_market_value == 250
    assert summary.total_profit_loss == 50
    assert summary.total_return_percent == pytest.approx(25)
    assert summary.weighted_alpha_score == pytest.approx(
        summary.rows[0].alpha_score
    )
