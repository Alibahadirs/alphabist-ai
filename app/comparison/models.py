from pydantic import BaseModel, Field


class CompanyComparisonRow(BaseModel):
    symbol: str
    company_name: str
    alpha_score: float = Field(ge=0, le=100)
    grade: str
    decision: str
    technical_score: float | None = Field(default=None, ge=0, le=100)
    technical_signal: str | None = None
    combined_score: float | None = Field(default=None, ge=0, le=100)
    atr_percent: float | None = Field(default=None, ge=0)
    confidence_score: float | None = Field(default=None, ge=0, le=100)
    confidence_status: str = ""
    calculation_check_status: str = "Kayıt yok"
    decision_ready: bool = True


class ComparisonSummary(BaseModel):
    rows: list[CompanyComparisonRow]
    leader_symbol: str
    average_alpha_score: float = Field(ge=0, le=100)
    average_combined_score: float | None = Field(default=None, ge=0, le=100)
    decision_ready_count: int = Field(default=0, ge=0)
