from app.database import repository
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics


def _company(margin: float) -> FinancialMetrics:
    return FinancialMetrics(
        symbol="TEST",
        company_name="Test Şirketi",
        revenue_growth=20,
        net_profit_growth=25,
        net_margin=margin,
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


def test_score_history_is_saved_in_chronological_order(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()

    first_company = _company(5)
    second_company = _company(25)
    repository.upsert_company(first_company)
    repository.add_score_history(
        first_company.symbol,
        calculate_alpha_score(first_company),
    )
    repository.upsert_company(second_company)
    repository.add_score_history(
        second_company.symbol,
        calculate_alpha_score(second_company),
    )

    history = repository.list_score_history("test")

    assert len(history) == 2
    assert history[0].id < history[1].id
    assert history[0].total_score < history[1].total_score
    assert all(entry.symbol == "TEST" for entry in history)
