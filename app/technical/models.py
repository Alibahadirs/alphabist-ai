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


class TechnicalRefreshItem(BaseModel):
    symbol: str
    status: str
    detail: str
    price_date: date | None = None
    technical_score: float | None = Field(default=None, ge=0, le=100)


class TechnicalRefreshSummary(BaseModel):
    total: int = Field(ge=0)
    saved: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    rejected: int = Field(ge=0)
    failed: int = Field(ge=0)
    items: list[TechnicalRefreshItem]


class TechnicalQualityRow(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    technical_score: float | None = Field(default=None, ge=0, le=100)
    signal: str = ""
    price_date: date | None = None
    source: str = ""
    methodology_version: str = ""
    alignment_status: str = ""
    status: str
    age_days: int | None = Field(default=None, ge=0)
    current: bool = False
    methodology_current: bool = False
    alignment_verified: bool = False
    source_verified: bool = False
    score_integrity_verified: bool = False


class TechnicalQualitySummary(BaseModel):
    rows: list[TechnicalQualityRow]
    total: int = Field(ge=0)
    current_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    date_error_count: int = Field(ge=0)
    methodology_error_count: int = Field(default=0, ge=0)
    alignment_error_count: int = Field(default=0, ge=0)
    source_error_count: int = Field(default=0, ge=0)
    score_integrity_error_count: int = Field(default=0, ge=0)
