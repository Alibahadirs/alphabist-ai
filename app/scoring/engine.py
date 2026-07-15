from app.core.constants import CATEGORY_MAX_POINTS, GRADE_RULES
from app.core.exceptions import ScoringError
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.sector.profiles import CompanyProfile


def clamp(value: float, minimum: float, maximum: float) -> float:
    if minimum > maximum:
        raise ScoringError("Minimum değer maksimum değerden büyük olamaz.")
    return max(minimum, min(value, maximum))


def scale(value: float | None, low: float, high: float, points: float) -> float:
    if low >= high:
        raise ScoringError("Ölçek üst sınırı alt sınırdan büyük olmalıdır.")
    if value is None:
        return 0
    return round(clamp((value - low) / (high - low), 0, 1) * points, 2)


def inverse_scale(value: float | None, good: float, bad: float, points: float) -> float:
    if value is None:
        return 0
    return round(clamp((bad - value) / (bad - good), 0, 1) * points, 2)


def band_score(value: float | None, low: float, high: float, tolerance: float, points: float) -> float:
    if value is None:
        return 0
    if low <= value <= high:
        return points
    distance = low - value if value < low else value - high
    return round(clamp(1 - distance / tolerance, 0, 1) * points, 2)


def get_grade_and_decision(total: float) -> tuple[str, str]:
    for minimum_score, grade, decision in GRADE_RULES:
        if total >= minimum_score:
            return grade, decision
    raise ScoringError("Puan için uygun not aralığı bulunamadı.")


def _manual_scores(m: FinancialMetrics) -> tuple[float, float, float]:
    return (
        round(m.valuation_score_input / 10, 2),
        round(m.risk_score_input / 20, 2),
        round(m.management_score_input / 20, 2),
    )


def _standard(m: FinancialMetrics) -> tuple[float, ...]:
    profitability = scale(m.net_margin, 0, 25, 7.5) + scale(m.roe, 0, 35, 7.5)
    growth = scale(m.revenue_growth, -10, 40, 7.5) + scale(m.net_profit_growth, -20, 60, 7.5)
    leverage = inverse_scale(m.debt_to_equity, 0, 2, 15)
    liquidity = scale(m.current_ratio, 0.5, 2.5, 10)
    cash_flow = (7.5 if (m.operating_cash_flow or 0) > 0 else 0) + (7.5 if (m.free_cash_flow or 0) > 0 else 0)
    efficiency = scale(m.asset_turnover, 0, 1.5, 10)
    return profitability, growth, leverage, liquidity, cash_flow, efficiency


def _bank(m: FinancialMetrics) -> tuple[float, ...]:
    profitability = scale(m.roe, 5, 35, 10) + scale(m.net_interest_margin, 0, 8, 5)
    growth = scale(m.net_profit_growth, -20, 60, 10) + scale(m.revenue_growth, -10, 40, 5)
    leverage = scale(m.capital_adequacy_ratio, 8, 20, 15)
    liquidity = band_score(m.loan_to_deposit_ratio, 80, 110, 40, 10)
    cash_flow = inverse_scale(m.npl_ratio, 2, 10, 15)
    efficiency = inverse_scale(m.cost_income_ratio, 30, 75, 10)
    return profitability, growth, leverage, liquidity, cash_flow, efficiency


def _insurance(m: FinancialMetrics) -> tuple[float, ...]:
    profitability = scale(m.roe, 5, 35, 10) + scale(m.net_margin, 0, 20, 5)
    growth = scale(m.premium_growth, -10, 40, 10) + scale(m.net_profit_growth, -20, 60, 5)
    leverage = scale(m.solvency_ratio, 100, 180, 15)
    liquidity = scale(m.current_ratio, 0.8, 2, 10)
    cash_flow = inverse_scale(m.combined_ratio, 90, 120, 15)
    efficiency = inverse_scale(m.combined_ratio, 85, 115, 10)
    return profitability, growth, leverage, liquidity, cash_flow, efficiency


def _reit(m: FinancialMetrics) -> tuple[float, ...]:
    profitability = scale(m.net_margin, 0, 35, 8) + scale(m.roe, 0, 20, 7)
    growth = scale(m.revenue_growth, -10, 40, 8) + scale(m.net_profit_growth, -20, 60, 7)
    leverage = inverse_scale(m.debt_to_equity, 0.2, 1.5, 15)
    liquidity = scale(m.current_ratio, 0.5, 2, 10)
    cash_flow = (10 if (m.operating_cash_flow or 0) > 0 else 0) + scale(m.occupancy_rate, 50, 95, 5)
    efficiency = scale(m.occupancy_rate, 50, 95, 10)
    return profitability, growth, leverage, liquidity, cash_flow, efficiency


def _financial_services(m: FinancialMetrics) -> tuple[float, ...]:
    profitability = scale(m.net_margin, 0, 25, 7.5) + scale(m.roe, 0, 35, 7.5)
    growth = scale(m.revenue_growth, -10, 40, 7.5) + scale(m.net_profit_growth, -20, 60, 7.5)
    leverage = scale(m.capital_adequacy_ratio, 8, 25, 15) if m.capital_adequacy_ratio is not None else inverse_scale(m.debt_to_equity, 1, 8, 15)
    liquidity = scale(m.current_ratio, 0.8, 2, 10)
    cash_flow = inverse_scale(m.npl_ratio, 2, 12, 15)
    efficiency = inverse_scale(m.cost_income_ratio, 30, 80, 10)
    return profitability, growth, leverage, liquidity, cash_flow, efficiency


def calculate_alpha_score(metrics: FinancialMetrics) -> ScoreBreakdown:
    from app.validation.service import validate_financial_metrics

    profile = CompanyProfile(metrics.company_profile)
    calculator = {
        CompanyProfile.STANDARD: _standard,
        CompanyProfile.BANK: _bank,
        CompanyProfile.INSURANCE: _insurance,
        CompanyProfile.REIT: _reit,
        CompanyProfile.FINANCIAL_SERVICES: _financial_services,
    }[profile]
    profitability, growth, leverage, liquidity, cash_flow, efficiency = calculator(metrics)
    valuation, risk, management = _manual_scores(metrics)
    if profile == CompanyProfile.REIT and metrics.nav_discount is not None:
        nav_value_score = scale(metrics.nav_discount, 0, 50, 10)
        valuation = round((valuation + nav_value_score) / 2, 2)
    raw_total = round(sum((profitability, growth, leverage, liquidity, cash_flow, efficiency, valuation, risk, management)), 2)
    validation = validate_financial_metrics(metrics)
    total = round(raw_total * (0.7 + 0.3 * validation.completeness / 100), 2)
    grade, decision = get_grade_and_decision(total)
    if validation.completeness < 70:
        decision = "Eksik veri / Doğrula"
    return ScoreBreakdown(
        profitability=profitability, growth=growth, leverage=leverage,
        liquidity=liquidity, cash_flow=cash_flow, efficiency=efficiency,
        valuation=valuation, risk=risk, management=management, total=total,
        grade=grade, decision=decision, company_profile=profile,
        data_completeness=validation.completeness,
        validation_warnings=validation.errors + validation.warnings,
    )
