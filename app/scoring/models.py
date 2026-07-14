from pydantic import BaseModel, Field

class FinancialMetrics(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    company_name: str
    revenue_growth: float = 0
    net_profit_growth: float = 0
    net_margin: float = 0
    roe: float = 0
    debt_to_equity: float = 0
    current_ratio: float = 0
    operating_cash_flow: float = 0
    free_cash_flow: float = 0
    asset_turnover: float = 0
    valuation_score_input: float = 50
    management_score_input: float = 70
    risk_score_input: float = 50

class ScoreBreakdown(BaseModel):
    profitability: float
    growth: float
    leverage: float
    liquidity: float
    cash_flow: float
    efficiency: float
    valuation: float
    risk: float
    management: float
    total: float
    grade: str
    decision: str
