import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange

from app.core.exceptions import TechnicalAnalysisError
from app.technical.models import TechnicalScoreBreakdown


REQUIRED_COLUMNS = {"Open", "High", "Low", "Close", "Volume"}
MINIMUM_HISTORY_ROWS = 200


def enrich_history(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise TechnicalAnalysisError(
            f"Teknik analiz için eksik sütunlar: {', '.join(sorted(missing))}"
        )
    if frame.empty:
        raise TechnicalAnalysisError("Teknik analiz için fiyat verisi bulunamadı.")

    enriched = frame.copy().sort_index()
    close = enriched["Close"].astype(float)
    high = enriched["High"].astype(float)
    low = enriched["Low"].astype(float)
    volume = enriched["Volume"].astype(float)

    enriched["SMA_20"] = close.rolling(20).mean()
    enriched["SMA_50"] = close.rolling(50).mean()
    enriched["SMA_200"] = close.rolling(200).mean()
    enriched["EMA_20"] = EMAIndicator(close, window=20).ema_indicator()
    enriched["EMA_50"] = EMAIndicator(close, window=50).ema_indicator()
    enriched["EMA_200"] = EMAIndicator(close, window=200).ema_indicator()
    enriched["RSI_14"] = RSIIndicator(close, window=14).rsi()

    macd = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    enriched["MACD"] = macd.macd()
    enriched["MACD_SIGNAL"] = macd.macd_signal()
    enriched["MACD_HIST"] = macd.macd_diff()

    atr = AverageTrueRange(high, low, close, window=14)
    enriched["ATR_14"] = atr.average_true_range()
    enriched["VOLUME_SMA_20"] = volume.rolling(20).mean()
    enriched["VOLUME_RATIO"] = volume / enriched["VOLUME_SMA_20"].replace(0, pd.NA)
    enriched["SUPPORT_20"] = low.rolling(20).min()
    enriched["RESISTANCE_20"] = high.rolling(20).max()
    return enriched


def _rsi_score(rsi_value: float) -> float:
    if 45 <= rsi_value <= 65:
        return 15
    if 35 <= rsi_value <= 75:
        return 10
    if 25 <= rsi_value <= 80:
        return 5
    return 0


def _volume_score(volume_ratio: float) -> float:
    if volume_ratio >= 1.5:
        return 15
    if volume_ratio >= 1.1:
        return 10
    if volume_ratio >= 0.8:
        return 7
    return 3


def _level_score(
    close: float,
    support: float,
    resistance: float,
    volume_ratio: float,
) -> float:
    price_range = resistance - support
    if price_range <= 0:
        return 5

    position = (close - support) / price_range
    if close >= resistance * 0.995 and volume_ratio >= 1.1:
        return 15
    if 0.35 <= position <= 0.85:
        return 12
    if 0.15 <= position <= 0.95:
        return 8
    return 4


def _signal(total: float) -> str:
    if total >= 85:
        return "Güçlü Al"
    if total >= 70:
        return "Al"
    if total >= 55:
        return "İzle"
    if total >= 40:
        return "Bekle"
    return "Kaçın"


def calculate_technical_score(frame: pd.DataFrame) -> TechnicalScoreBreakdown:
    if len(frame) < MINIMUM_HISTORY_ROWS:
        raise TechnicalAnalysisError(
            f"Teknik puan için en az {MINIMUM_HISTORY_ROWS} günlük veri gerekir."
        )

    enriched = enrich_history(frame)
    latest = enriched.iloc[-1]
    previous_week = enriched.iloc[-6]
    previous_day = enriched.iloc[-2]

    required_values = [
        latest["Close"],
        latest["EMA_20"],
        latest["EMA_50"],
        latest["EMA_200"],
        latest["RSI_14"],
        latest["MACD"],
        latest["MACD_SIGNAL"],
        latest["MACD_HIST"],
        latest["ATR_14"],
        latest["VOLUME_RATIO"],
        latest["SUPPORT_20"],
        latest["RESISTANCE_20"],
    ]
    if any(pd.isna(value) for value in required_values):
        raise TechnicalAnalysisError("Teknik göstergeler hesaplanamadı.")

    close = float(latest["Close"])
    ema_20 = float(latest["EMA_20"])
    ema_50 = float(latest["EMA_50"])
    ema_200 = float(latest["EMA_200"])
    rsi_value = float(latest["RSI_14"])
    volume_ratio = float(latest["VOLUME_RATIO"])

    trend = 0
    trend += 10 if close > ema_200 else 0
    trend += 5 if ema_50 > ema_200 else 0
    trend += 5 if close > ema_50 else 0

    moving_averages = 0
    moving_averages += 8 if close > ema_20 else 0
    moving_averages += 7 if ema_20 > ema_50 else 0
    moving_averages += 5 if ema_50 > float(previous_week["EMA_50"]) else 0

    macd_score = 0
    macd_score += 10 if latest["MACD"] > latest["MACD_SIGNAL"] else 0
    macd_score += 5 if latest["MACD_HIST"] > previous_day["MACD_HIST"] else 0

    rsi_score = _rsi_score(rsi_value)
    volume_score = _volume_score(volume_ratio)
    support_resistance = _level_score(
        close,
        float(latest["SUPPORT_20"]),
        float(latest["RESISTANCE_20"]),
        volume_ratio,
    )

    total = round(
        trend
        + moving_averages
        + rsi_score
        + macd_score
        + volume_score
        + support_resistance,
        2,
    )
    atr_percent = max(float(latest["ATR_14"]) / close * 100, 0)

    return TechnicalScoreBreakdown(
        trend=trend,
        moving_averages=moving_averages,
        rsi=rsi_score,
        macd=macd_score,
        volume=volume_score,
        support_resistance=support_resistance,
        total=total,
        signal=_signal(total),
        rsi_value=rsi_value,
        atr_percent=atr_percent,
    )


def calculate_combined_score(
    alpha_score: float,
    technical_score: float,
    alpha_weight: float = 0.70,
) -> float:
    if not 0 <= alpha_weight <= 1:
        raise TechnicalAnalysisError("Temel analiz ağırlığı 0 ile 1 arasında olmalıdır.")
    combined = alpha_score * alpha_weight + technical_score * (1 - alpha_weight)
    return round(max(0, min(combined, 100)), 2)
