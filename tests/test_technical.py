import numpy as np
import pandas as pd
import pytest

from app.core.exceptions import TechnicalAnalysisError
from app.technical.engine import (
    calculate_combined_score,
    calculate_technical_score,
    calculate_verified_combined_score,
    enrich_history,
)


def _price_frame(days: int = 260, direction: float = 1.0) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=days, freq="D")
    trend = np.linspace(50, 100 if direction > 0 else 25, days)
    wave = np.sin(np.arange(days) / 4) * 2
    close = trend + wave
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.linspace(1_000_000, 1_500_000, days),
        },
        index=index,
    )


def test_enrich_history_adds_indicators():
    enriched = enrich_history(_price_frame())

    assert "EMA_200" in enriched
    assert "RSI_14" in enriched
    assert "MACD_SIGNAL" in enriched
    assert "ATR_14" in enriched


def test_rising_market_scores_higher_than_falling_market():
    rising = calculate_technical_score(_price_frame(direction=1))
    falling = calculate_technical_score(_price_frame(direction=-1))

    assert rising.total > falling.total
    assert 0 <= rising.total <= 100
    assert 0 <= falling.total <= 100


def test_short_history_is_rejected():
    with pytest.raises(TechnicalAnalysisError):
        calculate_technical_score(_price_frame(days=100))


def test_combined_score_uses_seventy_thirty_weighting():
    assert calculate_combined_score(90, 60) == pytest.approx(81)


def test_invalid_combined_weight_is_rejected():
    with pytest.raises(TechnicalAnalysisError):
        calculate_combined_score(90, 60, alpha_weight=1.1)


def test_verified_combined_score_requires_both_readiness_gates():
    assert calculate_verified_combined_score(
        90,
        60,
        financial_ready=True,
        technical_ready=True,
    ) == pytest.approx(81)
    assert calculate_verified_combined_score(
        90,
        60,
        financial_ready=False,
        technical_ready=True,
    ) is None
    assert calculate_verified_combined_score(
        90,
        60,
        financial_ready=True,
        technical_ready=False,
    ) is None
