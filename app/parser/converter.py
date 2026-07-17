from app.core.exceptions import ValidationError
from app.parser.models import FinancialReportDraft
from app.scoring.models import FinancialMetrics


def _growth_rate(
    current: float | None,
    previous: float | None,
) -> float | None:
    if current is None or previous is None or previous <= 0:
        return None
    return (current - previous) / abs(previous) * 100


def _ratio(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _average_balance(
    current: float | None,
    previous: float | None,
) -> float | None:
    if current is None or current <= 0:
        return None
    if previous is None or previous <= 0:
        return current
    return (current + previous) / 2


def to_financial_metrics(draft: FinancialReportDraft) -> FinancialMetrics:
    symbol = draft.symbol.upper().strip()
    company_name = draft.company_name.strip()
    if not symbol or not company_name:
        raise ValidationError("Hisse kodu ve şirket adı zorunludur.")

    annualization_factor = 12 / draft.period_months
    free_cash_flow = (
        draft.operating_cash_flow - abs(draft.capital_expenditures)
        if draft.operating_cash_flow is not None
        and draft.capital_expenditures is not None
        else None
    )
    average_equity = _average_balance(draft.equity, draft.previous_equity)
    average_assets = _average_balance(
        draft.total_assets,
        draft.previous_total_assets,
    )
    premium_growth = draft.premium_growth
    if (
        premium_growth is None
        and draft.previous_premium_revenue is not None
        and draft.previous_premium_revenue > 0
    ):
        premium_growth = _growth_rate(
            draft.premium_revenue,
            draft.previous_premium_revenue,
        )

    net_margin_ratio = _ratio(draft.net_profit, draft.revenue)
    roe_ratio = _ratio(draft.net_profit, average_equity)
    debt_to_equity = _ratio(draft.total_debt, draft.equity)
    current_ratio = _ratio(draft.current_assets, draft.current_liabilities)
    asset_turnover_ratio = _ratio(draft.revenue, average_assets)

    return FinancialMetrics(
        symbol=symbol,
        company_name=company_name,
        company_profile=draft.company_profile,
        revenue_growth=_growth_rate(draft.revenue, draft.previous_revenue),
        net_profit_growth=_growth_rate(
            draft.net_profit,
            draft.previous_net_profit,
        ),
        net_margin=(
            net_margin_ratio * 100 if net_margin_ratio is not None else None
        ),
        roe=(
            roe_ratio * 100 * annualization_factor
            if roe_ratio is not None
            else None
        ),
        debt_to_equity=debt_to_equity,
        current_ratio=(
            max(current_ratio, 0) if current_ratio is not None else None
        ),
        operating_cash_flow=draft.operating_cash_flow,
        free_cash_flow=free_cash_flow,
        asset_turnover=(
            max(asset_turnover_ratio * annualization_factor, 0)
            if asset_turnover_ratio is not None
            else None
        ),
        valuation_score_input=draft.valuation_score_input,
        management_score_input=draft.management_score_input,
        risk_score_input=draft.risk_score_input,
        capital_adequacy_ratio=draft.capital_adequacy_ratio,
        npl_ratio=draft.npl_ratio,
        loan_to_deposit_ratio=draft.loan_to_deposit_ratio,
        net_interest_margin=draft.net_interest_margin,
        cost_income_ratio=draft.cost_income_ratio,
        premium_growth=premium_growth,
        combined_ratio=draft.combined_ratio,
        solvency_ratio=draft.solvency_ratio,
        nav_discount=draft.nav_discount,
        occupancy_rate=draft.occupancy_rate,
    )
