from app.core.exceptions import ValidationError
from app.parser.models import FinancialReportDraft
from app.scoring.models import FinancialMetrics


def _growth_rate(current: float, previous: float) -> float:
    if previous <= 0:
        return 0
    return (current - previous) / abs(previous) * 100


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0
    return numerator / denominator


def to_financial_metrics(draft: FinancialReportDraft) -> FinancialMetrics:
    symbol = draft.symbol.upper().strip()
    company_name = draft.company_name.strip()
    if not symbol or not company_name:
        raise ValidationError("Hisse kodu ve şirket adı zorunludur.")

    annualization_factor = 12 / draft.period_months
    free_cash_flow = draft.operating_cash_flow - abs(draft.capital_expenditures)
    premium_growth = draft.premium_growth
    if premium_growth is None and draft.previous_premium_revenue > 0:
        premium_growth = _growth_rate(
            draft.premium_revenue,
            draft.previous_premium_revenue,
        )

    return FinancialMetrics(
        symbol=symbol,
        company_name=company_name,
        company_profile=draft.company_profile,
        revenue_growth=_growth_rate(draft.revenue, draft.previous_revenue),
        net_profit_growth=_growth_rate(
            draft.net_profit,
            draft.previous_net_profit,
        ),
        net_margin=_ratio(draft.net_profit, draft.revenue) * 100,
        roe=_ratio(draft.net_profit, draft.equity)
        * 100
        * annualization_factor,
        debt_to_equity=_ratio(draft.total_debt, draft.equity),
        current_ratio=max(
            _ratio(draft.current_assets, draft.current_liabilities),
            0,
        ),
        operating_cash_flow=draft.operating_cash_flow,
        free_cash_flow=free_cash_flow,
        asset_turnover=max(
            _ratio(draft.revenue, draft.total_assets) * annualization_factor,
            0,
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
