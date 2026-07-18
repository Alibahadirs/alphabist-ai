from datetime import date

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
    confidence_score: float | None = Field(default=None, ge=0, le=100)
    confidence_status: str = ""
    calculation_check_status: str = "Kayıt yok"
    decision_ready: bool = True
    combined_decision_ready: bool = False
    technical_score: float | None = Field(default=None, ge=0, le=100)
    technical_delta: float | None = None
    technical_signal: str = ""
    technical_price_date: date | None = None
    technical_status: str = "Kayıt yok"
    technical_current: bool = False


class WatchlistSummary(BaseModel):
    rows: list[WatchlistRow]
    average_alpha_score: float = Field(ge=0, le=100)
    targets_reached: int = Field(ge=0)
    decision_ready_count: int = Field(default=0, ge=0)
    combined_decision_ready_count: int = Field(default=0, ge=0)
    current_technical_count: int = Field(default=0, ge=0)
    technical_strengthening_count: int = Field(default=0, ge=0)
