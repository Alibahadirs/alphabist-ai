from math import isfinite
from pydantic import BaseModel, Field

from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


class ValidationReport(BaseModel):
    completeness: float = Field(ge=0, le=100)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


PROFILE_REQUIREMENTS = {
    CompanyProfile.STANDARD: (
        "revenue_growth", "net_profit_growth", "net_margin", "roe",
        "debt_to_equity", "current_ratio", "operating_cash_flow",
        "free_cash_flow", "asset_turnover",
    ),
    CompanyProfile.BANK: (
        "net_profit_growth", "roe", "capital_adequacy_ratio", "npl_ratio",
        "loan_to_deposit_ratio", "net_interest_margin", "cost_income_ratio",
    ),
    CompanyProfile.INSURANCE: (
        "net_profit_growth", "roe", "premium_growth", "combined_ratio",
        "solvency_ratio",
    ),
    CompanyProfile.REIT: (
        "revenue_growth", "net_profit_growth", "net_margin", "roe",
        "debt_to_equity", "operating_cash_flow", "nav_discount",
        "occupancy_rate",
    ),
    CompanyProfile.FINANCIAL_SERVICES: (
        "revenue_growth", "net_profit_growth", "net_margin", "roe",
        "capital_adequacy_ratio", "npl_ratio", "cost_income_ratio",
    ),
}


def validate_financial_metrics(metrics: FinancialMetrics) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    profile = CompanyProfile(metrics.company_profile)
    required = PROFILE_REQUIREMENTS[profile]
    missing = [name for name in required if getattr(metrics, name) is None]
    completeness = round((len(required) - len(missing)) / len(required) * 100, 1)

    for name, value in metrics.model_dump().items():
        if isinstance(value, (int, float)) and not isfinite(float(value)):
            errors.append(f"{name} sonlu bir sayı olmalıdır.")

    if not metrics.symbol.isalnum() or not 3 <= len(metrics.symbol) <= 6:
        errors.append("Hisse kodu 3-6 karakterli ve yalnızca harf/rakam olmalıdır.")
    if missing:
        warnings.append("Sektör puanı için eksik göstergeler: " + ", ".join(missing))
    if abs(metrics.roe or 0) > 150:
        warnings.append("ROE olağan aralığın dışında; dönem ve özkaynak değerlerini kontrol edin.")
    if abs(metrics.net_margin or 0) > 100:
        warnings.append("Net kâr marjı %100 sınırını aşıyor; tek seferlik gelirleri kontrol edin.")
    if abs(metrics.revenue_growth or 0) > 500:
        warnings.append("Gelir büyümesi olağan aralığın dışında; karşılaştırma dönemini kontrol edin.")
    if profile == CompanyProfile.BANK and metrics.capital_adequacy_ratio is not None:
        if not 5 <= metrics.capital_adequacy_ratio <= 50:
            warnings.append("Sermaye yeterliliği oranı olağan banka aralığının dışında.")
    if metrics.npl_ratio is not None and not 0 <= metrics.npl_ratio <= 100:
        errors.append("Takipteki kredi/alacak oranı %0-%100 arasında olmalıdır.")
    if metrics.combined_ratio is not None and not 0 <= metrics.combined_ratio <= 300:
        errors.append("Bileşik oran %0-%300 arasında olmalıdır.")

    return ValidationReport(
        completeness=completeness,
        errors=errors,
        warnings=warnings,
        missing_fields=missing,
    )
