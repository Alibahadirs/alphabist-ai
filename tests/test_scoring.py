import pytest
from pydantic import ValidationError

from app.core.exceptions import ScoringError
from app.scoring.engine import (
    calculate_alpha_score,
    get_grade_and_decision,
    scale,
)
from app.scoring.models import FinancialMetrics


def test_score_stays_between_zero_and_one_hundred():
    metrics = FinancialMetrics(
        symbol="TEST",
        company_name="Test Şirketi",
        revenue_growth=20,
        net_profit_growth=25,
        net_margin=12,
        roe=22,
        debt_to_equity=0.6,
        current_ratio=1.8,
        operating_cash_flow=100,
        free_cash_flow=50,
        asset_turnover=0.8,
        valuation_score_input=75,
        management_score_input=80,
        risk_score_input=70,
    )

    score = calculate_alpha_score(metrics)

    assert 0 <= score.total <= 100


def test_strong_company_receives_full_score():
    metrics = FinancialMetrics(
        symbol="STRONG",
        company_name="Güçlü Şirket",
        revenue_growth=40,
        net_profit_growth=60,
        net_margin=25,
        roe=35,
        debt_to_equity=0,
        current_ratio=2.5,
        operating_cash_flow=100,
        free_cash_flow=50,
        asset_turnover=1.5,
        valuation_score_input=100,
        management_score_input=100,
        risk_score_input=100,
    )

    score = calculate_alpha_score(metrics)

    assert score.total == 100
    assert score.raw_total == 100
    assert score.completeness_factor == 1
    assert score.completeness_adjustment == 0
    assert score.grade == "A+"
    assert score.decision == "Güçlü Al"


def test_weak_company_receives_zero_score():
    metrics = FinancialMetrics(
        symbol="WEAK",
        company_name="Zayıf Şirket",
        revenue_growth=-10,
        net_profit_growth=-20,
        net_margin=0,
        roe=0,
        debt_to_equity=2,
        current_ratio=0.5,
        operating_cash_flow=0,
        free_cash_flow=0,
        asset_turnover=0,
        valuation_score_input=0,
        management_score_input=0,
        risk_score_input=0,
    )

    score = calculate_alpha_score(metrics)

    assert score.total == 0
    assert score.grade == "D"
    assert score.decision == "Kaçın"


@pytest.mark.parametrize(
    ("total", "expected_grade"),
    [
        (90, "A+"),
        (80, "A"),
        (70, "B+"),
        (60, "B"),
        (50, "C"),
        (49.99, "D"),
    ],
)
def test_grade_boundaries(total, expected_grade):
    grade, _ = get_grade_and_decision(total)

    assert grade == expected_grade


def test_invalid_manual_score_is_rejected():
    with pytest.raises(ValidationError):
        FinancialMetrics(
            symbol="TEST",
            company_name="Test Şirketi",
            valuation_score_input=101,
        )


def test_invalid_scale_range_raises_scoring_error():
    with pytest.raises(ScoringError):
        scale(value=10, low=20, high=20, points=15)


def test_incomplete_data_adjustment_is_explicit_and_reproducible():
    metrics = FinancialMetrics(
        symbol="TEST",
        company_name="Eksik Test Şirketi",
        revenue_growth=20,
        net_profit_growth=25,
        net_margin=12,
        roe=22,
    )

    score = calculate_alpha_score(metrics)
    category_total = sum(
        (
            score.profitability,
            score.growth,
            score.leverage,
            score.liquidity,
            score.cash_flow,
            score.efficiency,
            score.valuation,
            score.risk,
            score.management,
        )
    )

    assert score.raw_total == pytest.approx(category_total)
    assert score.completeness_factor < 1
    assert score.completeness_adjustment < 0
    assert score.total == pytest.approx(
        round(score.raw_total * score.completeness_factor, 2)
    )
    assert score.completeness_adjustment == pytest.approx(
        round(score.total - score.raw_total, 2)
    )
