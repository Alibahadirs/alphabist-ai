from pydantic import BaseModel, Field, field_validator

from app.sector.profiles import CompanyProfile


class FinancialMetrics(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    company_name: str = Field(min_length=1, max_length=160)
    company_profile: CompanyProfile = CompanyProfile.STANDARD

    revenue_growth: float | None = None
    net_profit_growth: float | None = None
    net_margin: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = Field(default=None, ge=0)
    current_ratio: float | None = Field(default=None, ge=0)
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    asset_turnover: float | None = Field(default=None, ge=0)

    capital_adequacy_ratio: float | None = Field(default=None, ge=0)
    npl_ratio: float | None = Field(default=None, ge=0)
    loan_to_deposit_ratio: float | None = Field(default=None, ge=0)
    net_interest_margin: float | None = None
    cost_income_ratio: float | None = Field(default=None, ge=0)
    premium_growth: float | None = None
    combined_ratio: float | None = Field(default=None, ge=0)
    solvency_ratio: float | None = Field(default=None, ge=0)
    nav_discount: float | None = None
    occupancy_rate: float | None = Field(default=None, ge=0, le=100)

    valuation_score_input: float = Field(default=50, ge=0, le=100)
    management_score_input: float = Field(default=70, ge=0, le=100)
    risk_score_input: float = Field(default=50, ge=0, le=100)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


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
    company_profile: CompanyProfile = CompanyProfile.STANDARD
    data_completeness: float = Field(default=100, ge=0, le=100)
    validation_warnings: list[str] = Field(default_factory=list)
