from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class DailyTechnicalAssessment:
    symbol: str
    price_date: date
    close: float
    daily_change_percent: float | None
    support: float
    resistance: float
    support_distance_percent: float
    resistance_distance_percent: float
    stop_level: float
    risk_reward_ratio: float | None
    rsi: float
    ema_20: float
    ema_50: float
    volume_ratio: float | None
    status: str
    score: int
    explanation: str


@dataclass(frozen=True)
class DailyScanResult:
    generated_at: datetime
    market_date: date | None
    requested_symbols: int
    successful_symbols: int
    failed_symbols: int
    assessments: list[DailyTechnicalAssessment]
    failures: dict[str, str]
