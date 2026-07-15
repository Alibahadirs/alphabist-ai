from dataclasses import dataclass

from app.analysis.models import CompanyAnalysis, IndicatorAssessment
from app.core.constants import CATEGORY_MAX_POINTS
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.sector.profiles import CompanyProfile, PROFILE_LABELS


@dataclass(frozen=True)
class IndicatorRule:
    label: str
    unit: str = "%"
    good_min: float | None = None
    good_max: float | None = None
    bad_min: float | None = None
    bad_max: float | None = None


COMMON_RULES = {
    "revenue_growth": IndicatorRule("Gelir büyümesi", good_min=15, bad_max=0),
    "net_profit_growth": IndicatorRule("Net kâr büyümesi", good_min=15, bad_max=0),
    "net_margin": IndicatorRule("Net kâr marjı", good_min=10, bad_max=0),
    "roe": IndicatorRule("Özkaynak kârlılığı", good_min=20, bad_max=5),
    "debt_to_equity": IndicatorRule("Borç / özkaynak", unit="x", good_max=1, bad_min=2),
    "current_ratio": IndicatorRule("Cari oran", unit="x", good_min=1.5, bad_max=1),
    "asset_turnover": IndicatorRule("Aktif devir hızı", unit="x", good_min=0.8, bad_max=0.3),
}

PROFILE_RULES = {
    CompanyProfile.STANDARD: (
        "revenue_growth", "net_profit_growth", "net_margin", "roe",
        "debt_to_equity", "current_ratio", "asset_turnover",
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
        "debt_to_equity", "nav_discount", "occupancy_rate",
    ),
    CompanyProfile.FINANCIAL_SERVICES: (
        "revenue_growth", "net_profit_growth", "net_margin", "roe",
        "capital_adequacy_ratio", "npl_ratio", "cost_income_ratio",
    ),
}

SECTOR_RULES = {
    "capital_adequacy_ratio": IndicatorRule("Sermaye yeterliliği", good_min=16, bad_max=10),
    "npl_ratio": IndicatorRule("Takipteki kredi / alacak oranı", good_max=3, bad_min=7),
    "loan_to_deposit_ratio": IndicatorRule("Kredi / mevduat", good_min=80, good_max=110, bad_min=140),
    "net_interest_margin": IndicatorRule("Net faiz marjı", good_min=4, bad_max=1),
    "cost_income_ratio": IndicatorRule("Maliyet / gelir", good_max=45, bad_min=70),
    "premium_growth": IndicatorRule("Prim büyümesi", good_min=15, bad_max=0),
    "combined_ratio": IndicatorRule("Bileşik oran", good_max=100, bad_min=115),
    "solvency_ratio": IndicatorRule("Ödeme gücü / sermaye yeterliliği", good_min=130, bad_max=100),
    "nav_discount": IndicatorRule("Net aktif değer iskontosu", good_min=20, bad_max=-10),
    "occupancy_rate": IndicatorRule("Doluluk oranı", good_min=85, bad_max=60),
}

CATEGORY_NAMES = {
    "profitability": "Kârlılık",
    "growth": "Büyüme",
    "leverage": "Bilanço dayanıklılığı",
    "liquidity": "Likidite",
    "cash_flow": "Nakit / aktif kalitesi",
    "efficiency": "Verimlilik",
    "valuation": "Değerleme",
    "risk": "Risk dayanıklılığı",
    "management": "Yönetim",
}


def _assess(field: str, value: float | None) -> IndicatorAssessment:
    rule = COMMON_RULES.get(field) or SECTOR_RULES[field]
    if value is None:
        return IndicatorAssessment(
            field=field, label=rule.label, value=None, unit=rule.unit,
            status="Eksik", interpretation="Rapor veya kullanıcı doğrulaması gerekli.",
        )

    good = True
    if rule.good_min is not None and value < rule.good_min:
        good = False
    if rule.good_max is not None and value > rule.good_max:
        good = False
    bad = (
        (rule.bad_min is not None and value >= rule.bad_min)
        or (rule.bad_max is not None and value <= rule.bad_max)
    )
    status = "Güçlü" if good else "Zayıf" if bad else "Orta"
    interpretation = {
        "Güçlü": "Sektör profili için olumlu aralıkta.",
        "Orta": "İzlenmesi gereken ara bölgede.",
        "Zayıf": "Puanı ve risk görünümünü olumsuz etkiliyor.",
    }[status]
    return IndicatorAssessment(
        field=field, label=rule.label, value=value, unit=rule.unit,
        status=status, interpretation=interpretation,
    )


def build_company_analysis(
    metrics: FinancialMetrics,
    score: ScoreBreakdown,
) -> CompanyAnalysis:
    profile = CompanyProfile(metrics.company_profile)
    indicators = [_assess(field, getattr(metrics, field)) for field in PROFILE_RULES[profile]]
    strengths = [
        f"{item.label}: {item.interpretation}"
        for item in indicators if item.status == "Güçlü"
    ]
    risks = [
        f"{item.label}: {item.interpretation}"
        for item in indicators if item.status in ("Zayıf", "Eksik")
    ]
    for category, maximum in CATEGORY_MAX_POINTS.items():
        ratio = getattr(score, category) / maximum
        if ratio >= 0.8:
            strengths.append(f"{CATEGORY_NAMES[category]} puanı güçlü ({getattr(score, category):.1f}/{maximum}).")
        elif ratio <= 0.35:
            risks.append(f"{CATEGORY_NAMES[category]} puanı zayıf ({getattr(score, category):.1f}/{maximum}).")

    summary = (
        f"{metrics.symbol}, {PROFILE_LABELS[profile].lower()} metodolojisiyle "
        f"{score.total:.1f}/100 puan aldı. Veri yeterliliği %{score.data_completeness:.0f}."
    )
    if score.data_completeness < 70:
        summary += " Sonuç yatırım kararı için yeterli değil; eksik göstergeler tamamlanmalı."
    return CompanyAnalysis(
        company_profile=profile,
        data_completeness=score.data_completeness,
        summary=summary,
        strengths=list(dict.fromkeys(strengths))[:6],
        risks=list(dict.fromkeys(risks))[:6],
        indicators=indicators,
    )
