from enum import Enum

from pydantic import BaseModel, Field


class ReportFreshnessStatus(str, Enum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    FUTURE = "future"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class ReportPeriodAssessment(BaseModel):
    status: ReportFreshnessStatus
    age_days: int | None = None
    confidence_points: float = Field(ge=0, le=5)
    blocks_decision: bool = False
    message: str
