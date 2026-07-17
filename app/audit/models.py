from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.sector.profiles import CompanyProfile


class DataSourceType(str, Enum):
    PDF = "pdf"
    MANUAL = "manual"
    CORRECTION = "correction"
    LEGACY = "legacy"


class MetricSourceType(str, Enum):
    FINANCIAL_REPORT = "financial_report"
    ACTIVITY_REPORT = "activity_report"
    MANUAL = "manual"
    CORRECTION = "correction"


SOURCE_LABELS = {
    DataSourceType.PDF: "PDF raporları",
    DataSourceType.MANUAL: "Manuel giriş",
    DataSourceType.CORRECTION: "Veri kalite düzeltmesi",
    DataSourceType.LEGACY: "Kaynak belirtilmemiş",
}

METRIC_SOURCE_LABELS = {
    MetricSourceType.FINANCIAL_REPORT: "Finansal rapor",
    MetricSourceType.ACTIVITY_REPORT: "Faaliyet raporu",
    MetricSourceType.MANUAL: "Kullanıcı girişi",
    MetricSourceType.CORRECTION: "Kullanıcı düzeltmesi",
}


class CompanyDataAudit(BaseModel):
    id: int | None = Field(default=None, ge=1)
    symbol: str = Field(min_length=1, max_length=12)
    source_type: DataSourceType
    company_profile: CompanyProfile
    period_months: int | None = Field(default=None, ge=1, le=12)
    report_period_end: date | None = None
    financial_report_name: str = ""
    activity_report_name: str = ""
    financial_report_hash: str = Field(
        default="", pattern=r"^(?:[0-9a-f]{64})?$"
    )
    activity_report_hash: str = Field(
        default="", pattern=r"^(?:[0-9a-f]{64})?$"
    )
    financial_report_scale: float = Field(default=1, gt=0, le=1_000_000_000)
    completeness: float = Field(ge=0, le=100)
    alpha_score: float = Field(ge=0, le=100)
    grade: str = ""
    decision: str = ""
    confidence_score: float | None = Field(default=None, ge=0, le=100)
    confidence_status: str = ""
    methodology_version: str = "legacy"
    input_fingerprint: str = Field(default="", max_length=64)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    field_sources: dict[str, MetricSourceType] = Field(default_factory=dict)
    created_at: datetime | None = None


class AnalysisSnapshotComparison(BaseModel):
    previous_score: float = Field(ge=0, le=100)
    current_score: float = Field(ge=0, le=100)
    score_delta: float
    previous_confidence: float | None = Field(default=None, ge=0, le=100)
    current_confidence: float | None = Field(default=None, ge=0, le=100)
    confidence_delta: float | None = None
    previous_grade: str = ""
    current_grade: str = ""
    previous_decision: str = ""
    current_decision: str = ""
    previous_methodology: str = "legacy"
    current_methodology: str = "legacy"
    methodology_changed: bool = False
    category_deltas: dict[str, float] = Field(default_factory=dict)
