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


class CompanyReportChange(BaseModel):
    field: str
    label: str
    previous_value: Any = None
    current_value: Any = None
    numeric_delta: float | None = None


class CompanyReportComparison(BaseModel):
    symbol: str
    previous_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_generated_at: datetime
    current_generated_at: datetime
    changes: list[CompanyReportChange] = Field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.changes)


class CompanyReportExchangePackage(BaseModel):
    schema_version: str = "company-report-package-1"
    exported_at: datetime
    symbol: str
    report_count: int = Field(ge=1)
    reports: list[CompanyInvestmentReport] = Field(min_length=1)
    content_fingerprint: str = Field(
        default="",
        pattern=r"^(?:[0-9a-f]{64})?$",
    )


class CompanyReportPackageValidation(BaseModel):
    valid: bool
    package: CompanyReportExchangePackage | None = None
    errors: list[str] = Field(default_factory=list)


class CompanyReportImportResult(BaseModel):
    valid: bool
    imported_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)


class CompanyReportComparability(BaseModel):
    financial_comparable: bool
    technical_comparable: bool
    combined_comparable: bool
    notes: list[str] = Field(default_factory=list)


class ReportTrendAlertSeverity(str, Enum):
    INFO = "Bilgi"
    WARNING = "Uyarı"
    CRITICAL = "Kritik"


class CompanyReportTrendAlert(BaseModel):
    code: str
    severity: ReportTrendAlertSeverity
    message: str


class CompanyReportTrendSummary(BaseModel):
    symbol: str
    report_count: int = Field(ge=1)
    latest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    trend_label: str
    comparability: CompanyReportComparability | None = None
    alpha_delta: float | None = None
    confidence_delta: float | None = None
    technical_delta: float | None = None
    combined_delta: float | None = None
    category_deltas: dict[str, float] = Field(default_factory=dict)
    alerts: list[CompanyReportTrendAlert] = Field(default_factory=list)


class CompanyReportTrendMonitorRow(BaseModel):
    symbol: str
    company_name: str
    company_profile: CompanyProfile
    report_count: int = Field(ge=1)
    latest_generated_at: datetime
    latest_report_period_end: date | None = None
    latest_alpha_score: float = Field(ge=0, le=100)
    trend_label: str
    alpha_delta: float | None = None
    combined_delta: float | None = None
    decision_ready: bool
    alert_severity: ReportTrendAlertSeverity
    alert_count: int = Field(ge=0)
    primary_alert: str
    priority_score: float = Field(ge=0, le=100)


class CompanyReportTrendMonitor(BaseModel):
    rows: list[CompanyReportTrendMonitorRow] = Field(default_factory=list)
    company_count: int = Field(ge=0)
    critical_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    weakening_count: int = Field(ge=0)


class CompanyReportTrendMonitorFilters(BaseModel):
    search: str = ""
    severities: list[ReportTrendAlertSeverity] = Field(default_factory=list)
    trend_labels: list[str] = Field(default_factory=list)
    company_profiles: list[CompanyProfile] = Field(default_factory=list)
    minimum_priority: float = Field(default=0, ge=0, le=100)
    decision_blocked_only: bool = False
