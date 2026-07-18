from datetime import date

from pydantic import BaseModel, Field, field_validator


class PortfolioPosition(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    quantity: float = Field(gt=0)
    average_cost: float = Field(ge=0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


class PortfolioMarketPrice(BaseModel):
    value: float | None
    as_of_date: date | None = None
    source: str = ""


class PortfolioRow(BaseModel):
    symbol: str
    company_name: str
    quantity: float
    average_cost: float
    last_price: float | None
    cost_value: float
    market_value: float
    profit_loss: float
    return_percent: float
    alpha_score: float = Field(ge=0, le=100)
    price_available: bool
    price_as_of_date: date | None = None
    price_age_days: int | None = Field(default=None, ge=0)
    price_source: str = ""
    price_status: str = "Fiyat yok"
    price_current: bool = False
    technical_score: float | None = Field(default=None, ge=0, le=100)
    technical_signal: str = ""
    technical_price_date: date | None = None
    technical_status: str = "Kayıt yok"
    technical_current: bool = False
    confidence_score: float | None = Field(default=None, ge=0, le=100)
    confidence_status: str = ""
    decision: str = ""
    decision_ready: bool = True
    calculation_check_status: str = "Kayıt yok"
    company_profile: str = "standard"
    weight_percent: float = Field(default=0, ge=0, le=100)


class PortfolioStressScenario(BaseModel):
    label: str
    affected_scope: str
    shock_percent: float
    projected_market_value: float
    value_change: float
    projected_profit_loss: float
    projected_return_percent: float


class PortfolioSummary(BaseModel):
    rows: list[PortfolioRow]
    total_cost: float
    total_market_value: float
    total_profit_loss: float
    total_return_percent: float
    weighted_alpha_score: float = Field(ge=0, le=100)
    weighted_technical_score: float | None = Field(
        default=None, ge=0, le=100
    )
    weighted_combined_score: float | None = Field(
        default=None, ge=0, le=100
    )
    weighted_confidence_score: float | None = Field(
        default=None, ge=0, le=100
    )
    decision_ready_count: int = Field(default=0, ge=0)
    verification_required_count: int = Field(default=0, ge=0)
    decision_ready_value_percent: float = Field(default=0, ge=0, le=100)
    largest_position_symbol: str = ""
    largest_position_percent: float = Field(default=0, ge=0, le=100)
    profile_exposure: dict[str, float] = Field(default_factory=dict)
    concentration_warnings: list[str] = Field(default_factory=list)
    concentration_index: float = Field(default=0, ge=0, le=100)
    effective_position_count: float = Field(default=0, ge=0)
    diversification_status: str = "Veri yok"
    current_price_count: int = Field(default=0, ge=0)
    price_warning_count: int = Field(default=0, ge=0)
    current_price_value_percent: float = Field(
        default=0, ge=0, le=100
    )
    stress_test_ready: bool = False
    current_technical_value_percent: float = Field(
        default=0, ge=0, le=100
    )
    portfolio_score_ready: bool = False
    stress_scenarios: list[PortfolioStressScenario] = Field(
        default_factory=list
    )
