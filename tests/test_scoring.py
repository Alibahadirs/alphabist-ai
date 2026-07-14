from app.scoring.models import FinancialMetrics
from app.scoring.engine import calculate_alpha_score

def test_score_range():
    metrics = FinancialMetrics(symbol='TEST', company_name='Test', revenue_growth=20, net_profit_growth=25, net_margin=12, roe=22, debt_to_equity=.6, current_ratio=1.8, operating_cash_flow=100, free_cash_flow=50, asset_turnover=.8, valuation_score_input=75, management_score_input=80, risk_score_input=70)
    score = calculate_alpha_score(metrics)
    assert 0 <= score.total <= 100
