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


class PortfolioSummary(BaseModel):
    rows: list[PortfolioRow]
    total_cost: float
    total_market_value: float
    total_profit_loss: float
    total_return_percent: float
    weighted_alpha_score: float = Field(ge=0, le=100)
