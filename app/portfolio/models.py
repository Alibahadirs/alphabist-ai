from pydantic import BaseModel, Field, field_validator


class PortfolioPosition(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    quantity: float = Field(gt=0)
    average_cost: float = Field(ge=0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


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
    confidence_score: float | None = Field(default=None, ge=0, le=100)
    confidence_status: str = ""
    decision: str = ""
    decision_ready: bool = True
    calculation_check_status: str = "Kayıt yok"
    company_profile: str = "standard"
    weight_percent: float = Field(default=0, ge=0, le=100)


class PortfolioSummary(BaseModel):
    rows: list[PortfolioRow]
    total_cost: float
    total_market_value: float
    total_profit_loss: float
    total_return_percent: float
    weighted_alpha_score: float = Field(ge=0, le=100)
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
