"""Teknik göstergeler. Bağımsız ve test edilebilir olacak şekilde pandas ile yazılmıştır."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, min_periods=span, adjust=False).mean()


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """(macd_line, signal_line, histogram) döndürür."""

    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, min_periods=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """(orta bant/SMA, üst bant, alt bant) döndürür."""

    middle = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return middle, upper, lower


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_values = 100 - (100 / (1 + rs))
    # Ortalama kayıp sıfırken RS tanımsızdır: sadece yükseliş varsa RSI=100,
    # hiç hareket yoksa (avg_gain de 0) nötr kabul edilip RSI=50 yazılır.
    no_loss_no_gain = (avg_loss == 0) & (avg_gain == 0)
    rsi_values = rsi_values.where(avg_loss != 0, other=100.0)
    rsi_values = rsi_values.where(~no_loss_no_gain, other=50.0)
    rsi_values = rsi_values.mask(avg_gain.isna())
    return rsi_values


def momentum(series: pd.Series, period: int) -> pd.Series:
    return series.pct_change(periods=period) * 100


def daily_returns(series: pd.Series) -> pd.Series:
    return series.pct_change()


def annualized_volatility(series: pd.Series, window: int) -> pd.Series:
    returns = daily_returns(series)
    return returns.rolling(window=window).std() * np.sqrt(252) * 100


def max_drawdown_pct(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    cumulative_max = series.cummax()
    drawdown = (series - cumulative_max) / cumulative_max
    return float(drawdown.min() * 100)
