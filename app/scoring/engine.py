from app.core.constants import CATEGORY_MAX_POINTS, GRADE_RULES
from app.core.exceptions import ScoringError
from app.scoring.models import FinancialMetrics, ScoreBreakdown


def clamp(value: float, minimum: float, maximum: float) -> float:
    if minimum > maximum:
        raise ScoringError("Minimum değer maksimum değerden büyük olamaz.")

    return max(minimum, min(value, maximum))


def scale(
    value: float,
    low: float,
    high: float,
    points: float,
) -> float:
    if low >= high:
        raise ScoringError("Ölçek üst sınırı alt sınırdan büyük olmalıdır.")

    ratio = clamp((value - low) / (high - low), 0, 1)
    return round(ratio * points, 2)


def get_grade_and_decision(total: float) -> tuple[str, str]:
    for minimum_score, grade, decision in GRADE_RULES:
        if total >= minimum_score:
            return grade, decision

    raise ScoringError("Puan için uygun not aralığı bulunamadı.")


def calculate_alpha_score(metrics: FinancialMetrics) -> ScoreBreakdown:
    profitability = (
        scale(metrics.net_margin, 0, 25, 7.5)
        + scale(metrics.roe, 0, 35, 7.5)
    )

    growth = (
        scale(metrics.revenue_growth, -10, 40, 7.5)
        + scale(metrics.net_profit_growth, -20, 60, 7.5)
    )

    leverage = round(
        clamp((2 - metrics.debt_to_equity) / 2, 0, 1)
        * CATEGORY_MAX_POINTS["leverage"],
        2,
    )

    liquidity = scale(
        metrics.current_ratio,
        0.5,
        2.5,
        CATEGORY_MAX_POINTS["liquidity"],
    )

    cash_flow = (
        7.5 if metrics.operating_cash_flow > 0 else 0
    ) + (
        7.5 if metrics.free_cash_flow > 0 else 0
    )

    efficiency = scale(
        metrics.asset_turnover,
        0,
        1.5,
        CATEGORY_MAX_POINTS["efficiency"],
    )

    valuation = round(
        metrics.valuation_score_input
        / 100
        * CATEGORY_MAX_POINTS["valuation"],
        2,
    )

    risk = round(
        metrics.risk_score_input
        / 100
        * CATEGORY_MAX_POINTS["risk"],
        2,
    )

    management = round(
        metrics.management_score_input
        / 100
        * CATEGORY_MAX_POINTS["management"],
        2,
    )

    total = round(
        profitability
        + growth
        + leverage
        + liquidity
        + cash_flow
        + efficiency
        + valuation
        + risk
        + management,
        2,
    )

    grade, decision = get_grade_and_decision(total)

    return ScoreBreakdown(
        profitability=profitability,
        growth=growth,
        leverage=leverage,
        liquidity=liquidity,
        cash_flow=cash_flow,
        efficiency=efficiency,
        valuation=valuation,
        risk=risk,
        management=management,
        total=total,
        grade=grade,
        decision=decision,
    )