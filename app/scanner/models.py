from pydantic import BaseModel, Field


class ScannerFilters(BaseModel):
    minimum_alpha_score: float = Field(default=70, ge=0, le=100)
    minimum_revenue_growth: float = 0
    minimum_net_margin: float = 0
    maximum_debt_to_equity: float = Field(default=3, ge=0)
    positive_operating_cash_flow_only: bool = True
    decision_ready_only: bool = False


class ScannerRow(BaseModel):
    symbol: str
    company_name: str
    alpha_score: float = Field(ge=0, le=100)
    grade: str
    decision: str
    revenue_growth: float
    net_margin: float
    roe: float
    debt_to_equity: float
    current_ratio: float
    operating_cash_flow: float
    company_profile: str = "standard"
    data_completeness: float = Field(default=100, ge=0, le=100)
    confidence_score: float | None = Field(default=None, ge=0, le=100)
    confidence_status: str = ""
    calculation_check_status: str = "Kayıt yok"
    decision_ready: bool = True


class ScannerSummary(BaseModel):
    rows: list[ScannerRow]
    total_scanned: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    average_alpha_score: float = Field(ge=0, le=100)
