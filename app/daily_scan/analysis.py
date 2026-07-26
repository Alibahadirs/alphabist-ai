from __future__ import annotations

import math

import pandas as pd

from app.daily_scan.models import DailyTechnicalAssessment


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    relative_strength = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + relative_strength))


def _cluster_levels(values: list[float], tolerance: float = 0.015) -> list[float]:
    clusters: list[list[float]] = []
    for value in sorted(value for value in values if value > 0):
        for cluster in clusters:
            center = sum(cluster) / len(cluster)
            if abs(value - center) / center <= tolerance:
                cluster.append(value)
                break
        else:
            clusters.append([value])
    return [sum(cluster) / len(cluster) for cluster in clusters]


def _support_resistance(frame: pd.DataFrame, close: float) -> tuple[float, float]:
    recent = frame.tail(120)
    lows = recent["Low"]
    highs = recent["High"]
    local_lows = lows[(lows == lows.rolling(5, center=True).min())].dropna().tolist()
    local_highs = highs[(highs == highs.rolling(5, center=True).max())].dropna().tolist()
    supports = [level for level in _cluster_levels(local_lows) if level < close]
    resistances = [level for level in _cluster_levels(local_highs) if level > close]
    support = max(supports) if supports else float(recent["Low"].tail(20).min())
    resistance = (
        min(resistances) if resistances else float(recent["High"].tail(20).max())
    )
    if resistance <= close:
        resistance = float(recent["High"].max())
    if support >= close:
        support = float(recent["Low"].min())
    return support, resistance


def assess_symbol(symbol: str, history: pd.DataFrame) -> DailyTechnicalAssessment:
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not set(required).issubset(history.columns):
        raise ValueError("OHLCV sütunları eksik.")
    clean = history[list(required)].copy().dropna(subset=["Close"])
    if len(clean) < 60:
        raise ValueError("En az 60 işlem günü gerekir.")

    close_series = clean["Close"].astype(float)
    ema_20 = close_series.ewm(span=20, adjust=False).mean()
    ema_50 = close_series.ewm(span=50, adjust=False).mean()
    rsi_series = _rsi(close_series)
    close = float(close_series.iloc[-1])
    previous = float(close_series.iloc[-2])
    daily_change = ((close / previous) - 1) * 100 if previous else None
    support, resistance = _support_resistance(clean, close)
    support_distance = ((close / support) - 1) * 100
    resistance_distance = ((resistance / close) - 1) * 100
    stop_level = support * 0.98
    downside = close - stop_level
    upside = resistance - close
    risk_reward = upside / downside if downside > 0 and upside > 0 else None
    volume_average = clean["Volume"].astype(float).tail(20).mean()
    volume_ratio = (
        float(clean["Volume"].iloc[-1]) / float(volume_average)
        if volume_average and not math.isnan(volume_average)
        else None
    )
    latest_rsi = float(rsi_series.iloc[-1])
    latest_ema_20 = float(ema_20.iloc[-1])
    latest_ema_50 = float(ema_50.iloc[-1])

    score = 50
    score += 15 if close > latest_ema_20 else -15
    score += 15 if latest_ema_20 > latest_ema_50 else -15
    score += 10 if 45 <= latest_rsi <= 65 else (-10 if latest_rsi < 35 else 0)
    score += 5 if volume_ratio is not None and volume_ratio >= 1.2 else 0
    score += 5 if risk_reward is not None and risk_reward >= 1.5 else 0
    score = max(0, min(100, score))

    if close < support * 0.99 or (close < latest_ema_20 < latest_ema_50):
        status = "Teknik görünüm zayıf"
        explanation = "Destek/trend yapısı zayıf; yeni pozisyon için uygun değil."
    elif resistance_distance <= 1.5 and close > latest_ema_20 > latest_ema_50:
        status = "Direnç kırılımı izleniyor"
        explanation = "Dirence yakın ve trend olumlu; kapanış teyidi beklenmeli."
    elif support_distance <= 2.0 and 35 <= latest_rsi <= 55:
        status = "Destekten tepki izlenebilir"
        explanation = "Desteğe yakın; destek korunumu ve hacim teyidi izlenmeli."
    elif close > latest_ema_20 > latest_ema_50 and 45 <= latest_rsi <= 70:
        status = "Teknik görünüm güçlü"
        explanation = "Kısa ve orta trend olumlu; risk seviyesi korunarak izlenebilir."
    else:
        status = "Nötr / teyit bekleniyor"
        explanation = "Belirgin teknik üstünlük yok; destek veya direnç teyidi beklenmeli."

    price_date = pd.Timestamp(clean.index[-1]).date()
    return DailyTechnicalAssessment(
        symbol=symbol,
        price_date=price_date,
        close=close,
        daily_change_percent=daily_change,
        support=support,
        resistance=resistance,
        support_distance_percent=support_distance,
        resistance_distance_percent=resistance_distance,
        stop_level=stop_level,
        risk_reward_ratio=risk_reward,
        rsi=latest_rsi,
        ema_20=latest_ema_20,
        ema_50=latest_ema_50,
        volume_ratio=volume_ratio,
        status=status,
        score=score,
        explanation=explanation,
    )
