from pydantic import BaseModel, Field


class FinancialMetrics(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    company_name: str = Field(min_length=1, max_length=120)

    revenue_growth: float = 0
    net_profit_growth: float = 0
    net_margin: float = 0
    roe: float = 0

    debt_to_equity: float = 0
    current_ratio: float = Field(default=0, ge=0)

    operating_cash_flow: float = 0
    free_cash_flow: float = 0
    asset_turnover: float = Field(default=0, ge=0)

    valuation_score_input: float = Field(default=50, ge=0, le=100)
    management_score_input: float = Field(default=70, ge=0, le=100)
    risk_score_input: float = Field(default=50, ge=0, le=100)


class ScoreBreakdown(BaseModel):
    profitability: float = Field(ge=0, le=15)
    growth: float = Field(ge=0, le=15)
    leverage: float = Field(ge=0, le=15)
    liquidity: float = Field(ge=0, le=10)
    cash_flow: float = Field(ge=0, le=15)
    efficiency: float = Field(ge=0, le=10)
    valuation: float = Field(ge=0, le=10)
    risk: float = Field(ge=0, le=5)
    management: float = Field(ge=0, le=5)

    total: float = Field(ge=0, le=100)
    grade: str
    decision: str