from collections.abc import Mapping, Sequence

from app.portfolio.models import PortfolioPosition, PortfolioRow, PortfolioSummary
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics


def build_portfolio_summary(
    positions: Sequence[PortfolioPosition],
    companies: Mapping[str, FinancialMetrics],
    prices: Mapping[str, float | None],
) -> PortfolioSummary:
    rows: list[PortfolioRow] = []
    for position in positions:
        company = companies.get(position.symbol)
        if company is None:
            continue

        price = prices.get(position.symbol)
        price_available = price is not None and price >= 0
        effective_price = float(price) if price_available else position.average_cost
        cost_value = position.quantity * position.average_cost
        market_value = position.quantity * effective_price
        profit_loss = market_value - cost_value
        return_percent = profit_loss / cost_value * 100 if cost_value else 0
        alpha_score = calculate_alpha_score(company).total

        rows.append(
            PortfolioRow(
                symbol=position.symbol,
                company_name=company.company_name,
                quantity=position.quantity,
                average_cost=position.average_cost,
                last_price=float(price) if price_available else None,
                cost_value=cost_value,
                market_value=market_value,
                profit_loss=profit_loss,
                return_percent=return_percent,
                alpha_score=alpha_score,
                price_available=price_available,
            )
        )

    total_cost = sum(row.cost_value for row in rows)
    total_market_value = sum(row.market_value for row in rows)
    total_profit_loss = total_market_value - total_cost
    total_return_percent = total_profit_loss / total_cost * 100 if total_cost else 0
    weight_base = total_market_value or total_cost
    weighted_alpha_score = (
        sum(row.alpha_score * row.market_value for row in rows) / weight_base
        if weight_base
        else 0
    )

    return PortfolioSummary(
        rows=rows,
        total_cost=round(total_cost, 2),
        total_market_value=round(total_market_value, 2),
        total_profit_loss=round(total_profit_loss, 2),
        total_return_percent=round(total_return_percent, 2),
        weighted_alpha_score=round(weighted_alpha_score, 2),
    )
