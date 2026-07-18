from collections.abc import Mapping, Sequence

from app.audit.models import CompanyDataAudit
from app.confidence.service import calculate_analysis_confidence
from app.portfolio.models import (
    PortfolioPosition,
    PortfolioRow,
    PortfolioStressScenario,
    PortfolioSummary,
)
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


MAX_POSITION_WEIGHT = 35.0
MAX_PROFILE_WEIGHT = 60.0
STRESS_SHOCKS = (-20.0, -10.0, 10.0)
LARGEST_POSITION_SHOCK = -25.0
LARGEST_PROFILE_SHOCK = -15.0


def _diversification_status(concentration_index: float) -> str:
    if concentration_index <= 20:
        return "Dengeli"
    if concentration_index <= 35:
        return "Orta yoğun"
    return "Yoğun"


def _build_stress_scenarios(
    total_market_value: float,
    total_cost: float,
    rows: Sequence[PortfolioRow],
) -> list[PortfolioStressScenario]:
    scenarios: list[PortfolioStressScenario] = []

    def add_scenario(
        label: str,
        affected_scope: str,
        shock_percent: float,
        affected_market_value: float,
    ) -> None:
        projected_market_value = (
            total_market_value
            + affected_market_value * shock_percent / 100
        )
        value_change = projected_market_value - total_market_value
        projected_profit_loss = projected_market_value - total_cost
        projected_return_percent = (
            projected_profit_loss / total_cost * 100
            if total_cost
            else 0
        )
        scenarios.append(
            PortfolioStressScenario(
                label=label,
                affected_scope=affected_scope,
                shock_percent=shock_percent,
                projected_market_value=round(projected_market_value, 2),
                value_change=round(value_change, 2),
                projected_profit_loss=round(projected_profit_loss, 2),
                projected_return_percent=round(
                    projected_return_percent, 2
                ),
            )
        )

    for shock_percent in STRESS_SHOCKS:
        direction = "düşüş" if shock_percent < 0 else "yükseliş"
        add_scenario(
            label=f"%{abs(shock_percent):.0f} {direction}",
            affected_scope="Tüm portföy",
            shock_percent=shock_percent,
            affected_market_value=total_market_value,
        )

    if rows and total_market_value > 0:
        largest_position = max(rows, key=lambda row: row.market_value)
        add_scenario(
            label="En büyük pozisyon düşüşü",
            affected_scope=largest_position.symbol,
            shock_percent=LARGEST_POSITION_SHOCK,
            affected_market_value=largest_position.market_value,
        )

        profile_values: dict[str, float] = {}
        for row in rows:
            profile_values[row.company_profile] = (
                profile_values.get(row.company_profile, 0)
                + row.market_value
            )
        largest_profile, largest_profile_value = max(
            profile_values.items(),
            key=lambda item: item[1],
        )
        add_scenario(
            label="En büyük profil düşüşü",
            affected_scope=f"{largest_profile} profili",
            shock_percent=LARGEST_PROFILE_SHOCK,
            affected_market_value=largest_profile_value,
        )

    return scenarios


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
                company_profile=CompanyProfile(
                    company.company_profile
                ).value,
            )
        )

    total_cost = sum(row.cost_value for row in rows)
    total_market_value = sum(row.market_value for row in rows)
    total_profit_loss = total_market_value - total_cost
    total_return_percent = total_profit_loss / total_cost * 100 if total_cost else 0
    weight_base = total_market_value or total_cost
    rows = [
        row.model_copy(
            update={
                "weight_percent": (
                    round(row.market_value / weight_base * 100, 2)
                    if weight_base
                    else 0
                )
            }
        )
        for row in rows
    ]
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
    profile_exposure: dict[str, float] = {}
    for row in rows:
        profile_exposure[row.company_profile] = (
            profile_exposure.get(row.company_profile, 0)
            + row.weight_percent
        )
    profile_exposure = {
        profile: round(weight, 2)
        for profile, weight in profile_exposure.items()
    }
    weight_fractions = [
        row.market_value / weight_base
        for row in rows
        if weight_base
    ]
    concentration_fraction = sum(
        weight**2 for weight in weight_fractions
    )
    concentration_index = round(concentration_fraction * 100, 2)
    effective_position_count = (
        1 / concentration_fraction
        if concentration_fraction
        else 0
    )
    largest_position = max(
        rows,
        key=lambda row: row.weight_percent,
        default=None,
    )
    concentration_warnings: list[str] = []
    if (
        largest_position is not None
        and largest_position.weight_percent > MAX_POSITION_WEIGHT
    ):
        concentration_warnings.append(
            f"{largest_position.symbol} portföyün "
            f"%{largest_position.weight_percent:.1f}'ini oluşturuyor."
        )
    for profile, weight in profile_exposure.items():
        if weight > MAX_PROFILE_WEIGHT:
            concentration_warnings.append(
                f"{profile} profili portföyün %{weight:.1f}'ini oluşturuyor."
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
        largest_position_symbol=(
            largest_position.symbol if largest_position else ""
        ),
        largest_position_percent=(
            largest_position.weight_percent if largest_position else 0
        ),
        profile_exposure=profile_exposure,
        concentration_warnings=concentration_warnings,
        concentration_index=concentration_index,
        effective_position_count=round(
            effective_position_count, 2
        ),
        diversification_status=(
            _diversification_status(concentration_index)
            if rows
            else "Veri yok"
        ),
        stress_scenarios=_build_stress_scenarios(
            total_market_value,
            total_cost,
            rows,
        ),
    )
