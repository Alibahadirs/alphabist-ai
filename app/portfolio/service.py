from collections.abc import Mapping, Sequence

from app.audit.models import CompanyDataAudit
from app.confidence.service import calculate_analysis_confidence
from app.portfolio.models import PortfolioPosition, PortfolioRow, PortfolioSummary
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics


def build_portfolio_summary(
    positions: Sequence[PortfolioPosition],
    companies: Mapping[str, FinancialMetrics],
    prices: Mapping[str, float | None],
    latest_audits: Mapping[str, CompanyDataAudit] | None = None,
) -> PortfolioSummary:
    audits = {
        symbol.upper(): audit for symbol, audit in (latest_audits or {}).items()
    }
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
        score = calculate_alpha_score(company)
        confidence = (
            calculate_analysis_confidence(
                company, score, audits.get(company.symbol.upper())
            )
            if latest_audits is not None
            else None
        )

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
                alpha_score=score.total,
                price_available=price_available,
                confidence_score=confidence.total if confidence else None,
                confidence_status=confidence.status if confidence else "",
                decision=confidence.decision if confidence else score.decision,
                decision_ready=(
                    confidence.decision_ready if confidence else True
                ),
                calculation_check_status=(
                    confidence.calculation_check_status
                    if confidence
                    else "Kayıt yok"
                ),
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
    confidence_rows = [
        row for row in rows if row.confidence_score is not None
    ]
    weighted_confidence_score = (
        sum(
            float(row.confidence_score) * row.market_value
            for row in confidence_rows
        )
        / weight_base
        if weight_base and len(confidence_rows) == len(rows)
        else None
    )
    decision_ready_value = sum(
        row.market_value for row in rows if row.decision_ready
    )
    decision_ready_value_percent = (
        decision_ready_value / weight_base * 100 if weight_base else 0
    )

    return PortfolioSummary(
        rows=rows,
        total_cost=round(total_cost, 2),
        total_market_value=round(total_market_value, 2),
        total_profit_loss=round(total_profit_loss, 2),
        total_return_percent=round(total_return_percent, 2),
        weighted_alpha_score=round(weighted_alpha_score, 2),
        weighted_confidence_score=(
            round(weighted_confidence_score, 2)
            if weighted_confidence_score is not None
            else None
        ),
        decision_ready_count=sum(row.decision_ready for row in rows),
        verification_required_count=sum(
            not row.decision_ready for row in rows
        ),
        decision_ready_value_percent=round(
            decision_ready_value_percent, 2
        ),
    )
