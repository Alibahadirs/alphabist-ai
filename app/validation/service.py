from math import isfinite
from pydantic import BaseModel, Field

from app.parser.models import FinancialReportDraft
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


class SourceValidationReport(BaseModel):
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

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
        "revenue_growth", "net_profit_growth", "roe",
        "capital_adequacy_ratio", "npl_ratio", "loan_to_deposit_ratio",
        "net_interest_margin", "cost_income_ratio",
    ),
    CompanyProfile.INSURANCE: (
        "net_profit_growth", "net_margin", "roe", "current_ratio",
        "premium_growth", "combined_ratio", "solvency_ratio",
    ),
    CompanyProfile.REIT: (
        "revenue_growth", "net_profit_growth", "net_margin", "roe",
        "debt_to_equity", "current_ratio", "operating_cash_flow", "nav_discount",
        "occupancy_rate",
    ),
    CompanyProfile.FINANCIAL_SERVICES: (
        "revenue_growth", "net_profit_growth", "net_margin", "roe",
        "current_ratio", "npl_ratio", "cost_income_ratio",
    ),
}

PROFILE_ALTERNATIVE_REQUIREMENTS = {
    CompanyProfile.FINANCIAL_SERVICES: (
        ("capital_adequacy_ratio", "debt_to_equity"),
    ),
}


def get_profile_requirements(
    metrics: FinancialMetrics,
) -> tuple[str, ...]:
    profile = CompanyProfile(metrics.company_profile)
    required = list(PROFILE_REQUIREMENTS[profile])
    for alternatives in PROFILE_ALTERNATIVE_REQUIREMENTS.get(profile, ()):
        selected = next(
            (
                field
                for field in alternatives
                if getattr(metrics, field) is not None
            ),
            alternatives[0],
        )
        required.append(selected)
    return tuple(required)


def _is_materially_greater(
    value: float | None,
    reference: float | None,
    tolerance: float = 0.02,
) -> bool:
    if value is None or reference is None or reference < 0:
        return False
    return value > reference * (1 + tolerance)


def _has_scale_gap(
    current: float | None,
    previous: float | None,
    threshold: float = 1_000,
) -> bool:
    if current is None or previous is None or current == 0 or previous == 0:
        return False
    smaller = min(abs(current), abs(previous))
    larger = max(abs(current), abs(previous))
    return smaller > 0 and larger / smaller >= threshold


def validate_financial_draft(
    draft: FinancialReportDraft,
) -> SourceValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    profile = CompanyProfile(draft.company_profile)

    nonnegative_fields = {
        "Hasılat": draft.revenue,
        "Önceki dönem hasılat": draft.previous_revenue,
        "Finansal borç": draft.total_debt,
        "Nakit": draft.cash,
        "Dönen varlık": draft.current_assets,
        "Kısa vadeli yükümlülük": draft.current_liabilities,
        "Cari dönem yazılan primler": draft.premium_revenue,
        "Önceki dönem yazılan primler": draft.previous_premium_revenue,
    }
    for label, value in nonnegative_fields.items():
        if value is not None and value < 0:
            errors.append(f"{label} negatif olamaz.")

    for label, value in (
        ("Toplam varlık", draft.total_assets),
        ("Önceki dönem toplam varlık", draft.previous_total_assets),
    ):
        if value is not None and value <= 0:
            errors.append(f"{label} sıfırdan büyük olmalıdır.")

    for label, value in draft.model_dump().items():
        if isinstance(value, (int, float)) and not isfinite(float(value)):
            errors.append(f"{label} sonlu bir sayı olmalıdır.")

    if _is_materially_greater(draft.equity, draft.total_assets):
        errors.append(
            "Özkaynak toplam varlıktan büyük görünüyor; tutar birimini ve "
            "çıkarılan bilanço satırlarını kontrol edin."
        )
    if _is_materially_greater(
        draft.previous_equity,
        draft.previous_total_assets,
    ):
        errors.append(
            "Önceki dönem özkaynağı önceki dönem toplam varlığından büyük "
            "görünüyor."
        )
    if _is_materially_greater(draft.cash, draft.total_assets):
        errors.append("Nakit toplam varlıktan büyük olamaz.")

    if profile in (CompanyProfile.STANDARD, CompanyProfile.REIT):
        if _is_materially_greater(draft.current_assets, draft.total_assets):
            errors.append("Dönen varlık toplam varlıktan büyük olamaz.")
        if _is_materially_greater(draft.cash, draft.current_assets):
            errors.append("Nakit dönen varlıktan büyük olamaz.")
        if (
            draft.total_debt is not None
            and draft.total_assets is not None
            and draft.total_assets > 0
            and draft.total_debt > draft.total_assets * 2
        ):
            warnings.append(
                "Finansal borç toplam varlığın iki katını aşıyor; borç satırının "
                "ve rapor biriminin doğru alındığını kontrol edin."
            )

    scale_pairs = (
        ("hasılat", draft.revenue, draft.previous_revenue),
        ("net dönem kârı", draft.net_profit, draft.previous_net_profit),
        ("özkaynak", draft.equity, draft.previous_equity),
        ("toplam varlık", draft.total_assets, draft.previous_total_assets),
        (
            "yazılan primler",
            draft.premium_revenue,
            draft.previous_premium_revenue,
        ),
    )
    for label, current, previous in scale_pairs:
        if _has_scale_gap(current, previous):
            warnings.append(
                f"Cari ve önceki dönem {label} değerleri arasında en az 1.000 kat "
                "fark var; dönem sırasını ve para birimini kontrol edin."
            )

    margin_reference = draft.revenue
    margin_limit = 20 if profile == CompanyProfile.REIT else 5
    if (
        draft.net_profit is not None
        and margin_reference is not None
        and margin_reference > 0
        and abs(draft.net_profit) > margin_reference * margin_limit
    ):
        warnings.append(
            "Net dönem kârı gelire göre olağan dışı yüksek; tek seferlik gelir, "
            "gerçeğe uygun değer farkı veya yanlış satır eşleşmesini kontrol edin."
        )

    if (
        draft.operating_cash_flow is not None
        and draft.total_assets is not None
        and draft.total_assets > 0
        and abs(draft.operating_cash_flow) > draft.total_assets * 5
    ):
        warnings.append(
            "Operasyonel nakit akışı toplam varlığa göre olağan dışı yüksek; "
            "rapor birimini kontrol edin."
        )

    return SourceValidationReport(errors=errors, warnings=warnings)


def validate_financial_metrics(metrics: FinancialMetrics) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    profile = CompanyProfile(metrics.company_profile)
    required = get_profile_requirements(metrics)
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
    if metrics.revenue_growth is not None and metrics.revenue_growth <= -99.9:
        warnings.append("Gelir büyümesi -%100; cari dönem gelirinin sıfır veya eksik olmadığını kontrol edin.")
    if abs(metrics.net_profit_growth or 0) > 1_000:
        warnings.append("Net kâr büyümesi olağan aralığın dışında; baz dönem değerini kontrol edin.")
    if profile in (CompanyProfile.STANDARD, CompanyProfile.REIT):
        if (metrics.current_ratio or 0) > 20:
            warnings.append("Cari oran olağan aralığın dışında; dönen varlık ve kısa vadeli yükümlülükleri kontrol edin.")
        if (metrics.debt_to_equity or 0) > 20:
            warnings.append("Borç / özkaynak oranı olağan aralığın dışında; tutar ve oran alanlarını kontrol edin.")
        if (metrics.asset_turnover or 0) > 10:
            warnings.append("Aktif devir hızı olağan aralığın dışında; gelir ve toplam aktif değerlerini kontrol edin.")
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
