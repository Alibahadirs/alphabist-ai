from enum import Enum

from pydantic import BaseModel, Field


class ReportFreshnessStatus(str, Enum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    FUTURE = "future"
    INVALID = "invalid"
    UNKNOWN = "unknown"


REPORT_FRESHNESS_LABELS = {
    ReportFreshnessStatus.CURRENT: "Güncel",
    ReportFreshnessStatus.AGING: "Eskimekte",
    ReportFreshnessStatus.STALE: "Güncel değil",
    ReportFreshnessStatus.FUTURE: "İleri tarihli",
    ReportFreshnessStatus.INVALID: "Dönem hatalı",
    ReportFreshnessStatus.UNKNOWN: "Tarih eksik",
}


class ReportPeriodAssessment(BaseModel):
    status: ReportFreshnessStatus
    age_days: int | None = None
    confidence_points: float = Field(ge=0, le=5)
    blocks_decision: bool = False
    message: str
