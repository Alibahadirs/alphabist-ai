from pydantic import BaseModel, Field

from app.sector.profiles import CompanyProfile


class DataQualityRow(BaseModel):
    symbol: str
    company_name: str
    company_profile: CompanyProfile
    completeness: float = Field(ge=0, le=100)
    status: str
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
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
