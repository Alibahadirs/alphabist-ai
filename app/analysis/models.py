from pydantic import BaseModel, Field

from app.sector.profiles import CompanyProfile


class IndicatorAssessment(BaseModel):
    field: str
    label: str
    value: float | None = None
    unit: str = "%"
    status: str
    interpretation: str


class CompanyAnalysis(BaseModel):
    company_profile: CompanyProfile
    data_completeness: float = Field(ge=0, le=100)
    summary: str
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    indicators: list[IndicatorAssessment] = Field(default_factory=list)
