from datetime import date, datetime

from pydantic import BaseModel, Field


class TechnicalScoreBreakdown(BaseModel):
    trend: float = Field(ge=0, le=20)
    moving_averages: float = Field(ge=0, le=20)
    rsi: float = Field(ge=0, le=15)
    macd: float = Field(ge=0, le=15)
    volume: float = Field(ge=0, le=15)
    support_resistance: float = Field(ge=0, le=15)
    total: float = Field(ge=0, le=100)
    signal: str
    rsi_value: float
    atr_percent: float = Field(ge=0)


class TechnicalHistoryEntry(BaseModel):
    id: int = Field(ge=1)
    symbol: str = Field(min_length=1, max_length=12)
    price_date: date
    source: str
    total_score: float = Field(ge=0, le=100)
    signal: str
    rsi_value: float
    atr_percent: float = Field(ge=0)
    score_breakdown: dict[str, float]
    alignment_status: str
    methodology_version: str
    created_at: datetime
