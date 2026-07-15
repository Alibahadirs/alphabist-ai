from pydantic import BaseModel, Field, field_validator


class WatchlistEntry(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    note: str = Field(default="", max_length=200)
    target_alpha_score: float = Field(default=80, ge=0, le=100)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


class WatchlistRow(BaseModel):
    symbol: str
    company_name: str
    alpha_score: float = Field(ge=0, le=100)
    target_alpha_score: float = Field(ge=0, le=100)
    grade: str
    decision: str
    note: str
    target_reached: bool


class WatchlistSummary(BaseModel):
    rows: list[WatchlistRow]
    average_alpha_score: float = Field(ge=0, le=100)
    targets_reached: int = Field(ge=0)
