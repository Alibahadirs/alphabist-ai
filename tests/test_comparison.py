from app.comparison.service import build_comparison
from app.scoring.models import FinancialMetrics
from app.technical.models import TechnicalScoreBreakdown


def _company(symbol: str, margin: float, roe: float) -> FinancialMetrics:
    return FinancialMetrics(
        symbol=symbol,
        company_name=f"{symbol} Test",
        revenue_growth=20,
        net_profit_growth=25,
        net_margin=margin,
        roe=roe,
        debt_to_equity=0.5,
        current_ratio=1.8,
        operating_cash_flow=100,
        free_cash_flow=50,
        asset_turnover=0.8,
        valuation_score_input=75,
        management_score_input=80,
        risk_score_input=70,
    )


def _technical(total: float) -> TechnicalScoreBreakdown:
    remaining = total
    allocated = []
    for maximum in (20, 20, 15, 15, 15, 15):
        value = min(remaining, maximum)
        allocated.append(value)
        remaining -= value
    return TechnicalScoreBreakdown(
        trend=allocated[0],
        moving_averages=allocated[1],
        rsi=allocated[2],
        macd=allocated[3],
        volume=allocated[4],
        support_resistance=allocated[5],
        total=total,
        signal="Al",
        rsi_value=55,
        atr_percent=3.5,
    )


def test_comparison_requires_two_companies():
    try:
        build_comparison([_company("AAA", 10, 15)])
    except ValueError as exc:
        assert "en az iki" in str(exc)
    else:
        raise AssertionError("Tek şirket karşılaştırmaya kabul edildi.")


def test_comparison_ranks_by_alpha_without_technical_data():
    result = build_comparison(
        [_company("LOW", 5, 8), _company("HIGH", 20, 30)]
    )

    assert result.leader_symbol == "HIGH"
    assert result.rows[0].alpha_score > result.rows[1].alpha_score
    assert result.average_combined_score is None


def test_comparison_ranks_by_combined_score_with_technical_data():
    companies = [_company("AAA", 20, 30), _company("BBB", 10, 15)]
    result = build_comparison(
        companies,
        {"AAA": _technical(60), "BBB": _technical(90)},
    )

    assert all(row.combined_score is not None for row in result.rows)
    assert result.average_combined_score is not None
    expected = round(
        sum(
            row.combined_score
            for row in result.rows
            if row.combined_score is not None
        )
        / 2,
        2,
    )
    assert result.average_combined_score == expected
