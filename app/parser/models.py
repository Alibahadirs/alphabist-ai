from datetime import date

from pydantic import BaseModel, Field

from app.sector.profiles import CompanyProfile


class FinancialReportDraft(BaseModel):
    symbol: str = ""
    company_name: str = ""
    period_months: int = Field(default=3, ge=1, le=12)
    report_period_end: date | None = None
    company_profile: CompanyProfile = CompanyProfile.STANDARD

    revenue: float | None = None
    previous_revenue: float | None = None
    net_profit: float | None = None
    previous_net_profit: float | None = None
    equity: float | None = None
    previous_equity: float | None = None
    total_debt: float | None = None
    cash: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    operating_cash_flow: float | None = None
    capital_expenditures: float | None = None
    total_assets: float | None = None
    previous_total_assets: float | None = None
    premium_revenue: float | None = None
    previous_premium_revenue: float | None = None

    capital_adequacy_ratio: float | None = None
    npl_ratio: float | None = None
    loan_to_deposit_ratio: float | None = None
    net_interest_margin: float | None = None
    cost_income_ratio: float | None = None
    premium_growth: float | None = None
    combined_ratio: float | None = None
    solvency_ratio: float | None = None
    nav_discount: float | None = None
    occupancy_rate: float | None = None

    valuation_score_input: float = Field(default=50, ge=0, le=100)
    management_score_input: float = Field(default=70, ge=0, le=100)
    risk_score_input: float = Field(default=50, ge=0, le=100)


class PdfExtractionResult(BaseModel):
    draft: FinancialReportDraft
    page_count: int
    monetary_scale: float = Field(default=1, gt=0)
    monetary_unit_label: str = "TL"
    comparison_period_end: date | None = None
    comparison_period_validated: bool = False
    comparison_order_current_first: bool | None = None
    extracted_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CompanyMetadata(BaseModel):
    symbol: str = ""
    company_name: str = ""
    period_months: int | None = Field(default=None, ge=1, le=12)
    report_period_end: date | None = None
    company_profile: CompanyProfile = CompanyProfile.STANDARD


class ActivityReportExtractionResult(BaseModel):
    metadata: CompanyMetadata
    page_count: int
    warnings: list[str] = Field(default_factory=list)
    sector_metrics: dict[str, float] = Field(default_factory=dict)
