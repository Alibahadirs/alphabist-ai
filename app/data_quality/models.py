from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.sector.profiles import CompanyProfile
from app.validation.service import WarningConfirmationStatus


class DataQualityRow(BaseModel):
    symbol: str
    company_name: str
    company_profile: CompanyProfile
    completeness: float = Field(ge=0, le=100)
    status: str
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    warnings_confirmed: bool = False
    warning_confirmation_status: WarningConfirmationStatus = (
        WarningConfirmationStatus.NOT_APPLICABLE
    )
    warning_recommended_action: str = "İşlem gerekmiyor"
    errors: list[str] = Field(default_factory=list)
    calculation_check_status: str = "Kayıt yok"
    calculation_mismatch_fields: list[str] = Field(default_factory=list)


class DataQualitySummary(BaseModel):
    rows: list[DataQualityRow] = Field(default_factory=list)
    total_companies: int = Field(ge=0)
    verified_count: int = Field(ge=0)
    review_count: int = Field(ge=0)
    critical_count: int = Field(ge=0)
    average_completeness: float = Field(ge=0, le=100)
    warning_status_counts: dict[str, int] = Field(default_factory=dict)
    warning_issue_count: int = Field(default=0, ge=0)


class DecisionReadinessRow(BaseModel):
    symbol: str
    company_name: str
    financial_ready: bool
    technical_ready: bool
    status: str
    recommended_action: str
    blockers: list[str] = Field(default_factory=list)
    priority_score: int = Field(default=0, ge=0, le=100)
    priority_level: str = "Hazır"


class DecisionReadinessSummary(BaseModel):
    rows: list[DecisionReadinessRow] = Field(default_factory=list)
    total: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    financial_only_count: int = Field(ge=0)
    technical_only_count: int = Field(ge=0)
    combined_issue_count: int = Field(ge=0)


class RemediationTaskStatus(str, Enum):
    OPEN = "Açık"
    IN_PROGRESS = "Devam ediyor"
    COMPLETED = "Tamamlandı"
    DISMISSED = "Geçersiz"


class RemediationQueueRow(BaseModel):
    task_id: str
    symbol: str
    company_name: str
    company_profile: CompanyProfile
    priority_score: int = Field(ge=0, le=100)
    priority_level: str
    task_category: str
    recommended_action: str
    blockers: list[str] = Field(default_factory=list)
    workflow_status: RemediationTaskStatus = RemediationTaskStatus.OPEN
    workflow_note: str = ""
    workflow_updated_at: datetime | None = None


class RemediationTaskState(BaseModel):
    task_id: str
    symbol: str
    task_category: str
    status: RemediationTaskStatus = RemediationTaskStatus.OPEN
    note: str = Field(default="", max_length=1000)
    updated_at: datetime | None = None


class RemediationQueueSummary(BaseModel):
    rows: list[RemediationQueueRow] = Field(default_factory=list)
    total_tasks: int = Field(ge=0)
    urgent_count: int = Field(ge=0)
    high_count: int = Field(ge=0)
    financial_task_count: int = Field(ge=0)
    technical_task_count: int = Field(ge=0)
    profile_counts: dict[str, int] = Field(default_factory=dict)
