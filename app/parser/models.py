from pydantic import BaseModel, Field


class FinancialReportDraft(BaseModel):
    symbol: str = ""
    company_name: str = ""
    period_months: int = Field(default=3, ge=1, le=12)

    revenue: float = 0
    previous_revenue: float = 0
    net_profit: float = 0
    previous_net_profit: float = 0
    equity: float = 0
    total_debt: float = 0
    cash: float = 0
    current_assets: float = 0
    current_liabilities: float = 0
    operating_cash_flow: float = 0
    capital_expenditures: float = 0
    total_assets: float = 0

    valuation_score_input: float = Field(default=50, ge=0, le=100)
    management_score_input: float = Field(default=70, ge=0, le=100)
    risk_score_input: float = Field(default=50, ge=0, le=100)


class PdfExtractionResult(BaseModel):
    draft: FinancialReportDraft
    page_count: int
    extracted_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CompanyMetadata(BaseModel):
    symbol: str = ""
    company_name: str = ""
    period_months: int | None = Field(default=None, ge=1, le=12)


class ActivityReportExtractionResult(BaseModel):
    metadata: CompanyMetadata
    page_count: int
    warnings: list[str] = Field(default_factory=list)
