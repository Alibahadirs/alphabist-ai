"""Seçilen tarih aralığı için geriye dönük performans metrikleri."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import indicators as ind


@dataclass(frozen=True)
class RangePerformance:
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    start_price: float
    end_price: float
    total_return_pct: float
    annualized_volatility_pct: float
    max_drawdown_pct: float
    best_day_pct: float
    worst_day_pct: float
    trading_days: int


def compute_range_performance(df_visible: pd.DataFrame) -> RangePerformance:
    close = df_visible["Close"].dropna()
    if len(close) < 2:
        raise ValueError("Seçilen tarih aralığında yeterli veri yok (en az 2 işlem günü gerekir).")

    returns = ind.daily_returns(close).dropna()
    total_return = (close.iloc[-1] / close.iloc[0] - 1) * 100
    ann_vol = float(returns.std() * (252 ** 0.5) * 100) if not returns.empty else 0.0

    return RangePerformance(
        start_date=close.index[0],
        end_date=close.index[-1],
        start_price=float(close.iloc[0]),
        end_price=float(close.iloc[-1]),
        total_return_pct=float(total_return),
        annualized_volatility_pct=ann_vol,
        max_drawdown_pct=ind.max_drawdown_pct(close),
        best_day_pct=float(returns.max() * 100) if not returns.empty else 0.0,
        worst_day_pct=float(returns.min() * 100) if not returns.empty else 0.0,
        trading_days=len(close),
    )
