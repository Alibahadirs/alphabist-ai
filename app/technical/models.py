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
