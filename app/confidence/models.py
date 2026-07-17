from pydantic import BaseModel, Field


class AnalysisConfidence(BaseModel):
    total: float = Field(ge=0, le=100)
    status: str
    decision: str
    completeness_component: float = Field(ge=0, le=55)
    source_component: float = Field(ge=0, le=25)
    report_component: float = Field(ge=0, le=10)
    period_component: float = Field(ge=0, le=5)
    validation_component: float = Field(ge=0, le=5)
    calculation_check_status: str = "Kayıt yok"
    calculation_mismatch_fields: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
