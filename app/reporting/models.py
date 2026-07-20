from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.sector.profiles import CompanyProfile


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


class CompanyInvestmentReport(BaseModel):
    symbol: str
    company_name: str
    company_profile: CompanyProfile
    generated_at: datetime
    report_period_end: date | None = None
    alpha_score: float = Field(ge=0, le=100)
    alpha_grade: str
    alpha_decision: str
    confidence_score: float = Field(ge=0, le=100)
    confidence_status: str
    decision_ready: bool
    technical_score: float | None = Field(default=None, ge=0, le=100)
    technical_signal: str | None = None
    technical_price_date: date | None = None
    combined_score: float | None = Field(default=None, ge=0, le=100)
    combined_decision: str
    summary: str
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)
    category_scores: dict[str, float] = Field(default_factory=dict)
    indicators: list[dict[str, Any]] = Field(default_factory=list)
    scoring_methodology_version: str
    technical_methodology_version: str
    report_fingerprint: str = Field(
        default="",
        pattern=r"^(?:[0-9a-f]{64})?$",
    )


class CompanyReportSnapshot(BaseModel):
    id: int | None = None
    symbol: str
    report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_payload: dict[str, Any]
    created_at: datetime | None = None
