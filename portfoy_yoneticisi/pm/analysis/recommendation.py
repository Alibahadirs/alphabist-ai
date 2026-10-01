"""Kural tabanlı, teknik gösterge ağırlıklı öneri motoru.

Bu modül yatırım tavsiyesi değildir; yalnızca trend (SMA, MACD), momentum/aşırı
alım-satım (RSI, Bollinger %B) ve N-günlük getiri göstergelerinden türetilen
mekanik bir karar-destek skorudur.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from ..core.settings import settings
from . import indicators as ind

INSUFFICIENT_DATA = "Yetersiz geçmiş veri"


class Signal(str, Enum):
    AL = "Al"
    TUT = "Tut"
    SAT = "Sat"


@dataclass(frozen=True)
class FactorScore:
    name: str
    score: float  # -1..+1, sadece skora katkısı olanlar için anlamlıdır
    weight: float
    detail: str


@dataclass(frozen=True)
class Recommendation:
    signal: Signal
    score: float  # -1..+1 arası ağırlıklı toplam
    confidence: str  # "Düşük" | "Orta" | "Yüksek"
    factors: tuple[FactorScore, ...]
    as_of: pd.Timestamp
    price: float
    rsi_value: float | None = None
    momentum_value: float | None = None
    volatility_value: float | None = None
    macd_histogram: float | None = None
    bollinger_pctb: float | None = None

    @property
    def factor_table(self) -> list[dict]:
        return [
            {
                "Faktör": f.name,
                "Skor": round(f.score, 2),
                "Ağırlık": f.weight,
                "Açıklama": f.detail,
            }
            for f in self.factors
        ]


_TREND_WEIGHT = 0.35
_MACD_WEIGHT = 0.15
_RSI_WEIGHT = 0.20
_MOMENTUM_WEIGHT = 0.20
_BOLLINGER_WEIGHT = 0.10
_SIGNAL_THRESHOLD = 0.25
_HIGH_VOLATILITY_PCT = 45.0
_MACD_HIST_SATURATION = 0.004  # histogram fiyatın %0.4'üne ulaşınca MACD faktörü tam skora ulaşır


def _clip(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _trend_factor(close: pd.Series) -> FactorScore:
    sma_short = ind.sma(close, settings.sma_short)
    sma_long = ind.sma(close, settings.sma_long)
    if pd.isna(sma_short.iloc[-1]) or pd.isna(sma_long.iloc[-1]):
        return FactorScore(
            f"Trend (SMA{settings.sma_short}/SMA{settings.sma_long})",
            0.0,
            _TREND_WEIGHT,
            INSUFFICIENT_DATA,
        )
    s, l = float(sma_short.iloc[-1]), float(sma_long.iloc[-1])
    spread = (s - l) / l
    score = _clip(spread / 0.05)  # %5 fark -> tam skor
    yon = "yükseliş" if score > 0.1 else "düşüş" if score < -0.1 else "yatay"
    return FactorScore(
        f"Trend (SMA{settings.sma_short}/SMA{settings.sma_long})",
        score,
        _TREND_WEIGHT,
        f"Kısa vadeli ortalama uzun vadeliye göre {yon} (fark %{spread * 100:.1f})",
    )


def _rsi_factor(close: pd.Series) -> tuple[FactorScore, float | None]:
    rsi_series = ind.rsi(close, settings.rsi_period)
    last_rsi = rsi_series.iloc[-1]
    if pd.isna(last_rsi):
        return FactorScore(f"RSI ({settings.rsi_period})", 0.0, _RSI_WEIGHT, INSUFFICIENT_DATA), None
    last_rsi = float(last_rsi)
    if last_rsi <= 30:
        score = _clip((30 - last_rsi) / 20)
    elif last_rsi >= 70:
        score = -_clip((last_rsi - 70) / 20)
    else:
        score = 0.0
    factor = FactorScore(f"RSI ({settings.rsi_period})", score, _RSI_WEIGHT, f"RSI {last_rsi:.1f}")
    return factor, last_rsi


def _momentum_factor(close: pd.Series) -> tuple[FactorScore, float | None]:
    mom_series = ind.momentum(close, settings.momentum_period)
    last_mom = mom_series.iloc[-1]
    if pd.isna(last_mom):
        factor = FactorScore(
            f"Momentum ({settings.momentum_period} gün)", 0.0, _MOMENTUM_WEIGHT, INSUFFICIENT_DATA
        )
        return factor, None
    last_mom = float(last_mom)
    score = _clip(last_mom / 10)  # %10 hareket -> tam skor
    factor = FactorScore(
        f"Momentum ({settings.momentum_period} gün)",
        score,
        _MOMENTUM_WEIGHT,
        f"Son {settings.momentum_period} günde %{last_mom:.1f} değişim",
    )
    return factor, last_mom


def _macd_factor(close: pd.Series) -> tuple[FactorScore, float | None]:
    # MACD, yüzdesel (bileşik) trendlerde ham fiyat yerine LOG fiyat üzerinden
    # hesaplanır: aksi halde sabit yüzdeli bir trendde bile mutlak fiyat farkları
    # zamanla küçülüp/büyüyüp histogramın işaretini yapay şekilde ters çevirebilir.
    log_close = np.log(close)
    _macd_line, _signal_line, histogram = ind.macd(
        log_close, settings.macd_fast, settings.macd_slow, settings.macd_signal
    )
    last_hist = histogram.iloc[-1]
    name = f"MACD ({settings.macd_fast}/{settings.macd_slow}/{settings.macd_signal}, log fiyat)"
    if pd.isna(last_hist):
        return FactorScore(name, 0.0, _MACD_WEIGHT, INSUFFICIENT_DATA), None
    last_hist = float(last_hist)
    score = _clip(last_hist / _MACD_HIST_SATURATION)
    yon = "pozitif" if score > 0.1 else "negatif" if score < -0.1 else "zayıf"
    return (
        FactorScore(name, score, _MACD_WEIGHT, f"Histogram {yon} (log-fiyat farkı {last_hist:+.4f})"),
        last_hist,
    )


def _bollinger_factor(close: pd.Series) -> tuple[FactorScore, float | None]:
    _middle, upper, lower = ind.bollinger_bands(close, settings.bollinger_window, settings.bollinger_std)
    name = f"Bollinger Bantları ({settings.bollinger_window}, {settings.bollinger_std:g} std)"
    last_upper, last_lower = upper.iloc[-1], lower.iloc[-1]
    if pd.isna(last_upper) or pd.isna(last_lower):
        return FactorScore(name, 0.0, _BOLLINGER_WEIGHT, INSUFFICIENT_DATA), None

    band_width = float(last_upper - last_lower)
    if band_width == 0:
        return FactorScore(name, 0.0, _BOLLINGER_WEIGHT, "Bant genişliği sıfır (fiyat hareketsiz)"), 0.5

    pct_b = float((close.iloc[-1] - last_lower) / band_width)
    if pct_b <= 0.2:
        score = _clip((0.2 - pct_b) / 0.2)
    elif pct_b >= 0.8:
        score = -_clip((pct_b - 0.8) / 0.2)
    else:
        score = 0.0
    return FactorScore(name, score, _BOLLINGER_WEIGHT, f"%B {pct_b:.2f} (0=alt bant, 1=üst bant)"), pct_b


def _volatility_info(close: pd.Series) -> tuple[FactorScore, float | None]:
    vol_series = ind.annualized_volatility(close, settings.volatility_period)
    last_vol = vol_series.iloc[-1]
    if pd.isna(last_vol):
        return FactorScore("Volatilite (yıllıklandırılmış)", 0.0, 0.0, INSUFFICIENT_DATA), None
    last_vol = float(last_vol)
    return (
        FactorScore(
            "Volatilite (yıllıklandırılmış)",
            0.0,
            0.0,
            f"Yıllıklandırılmış volatilite %{last_vol:.1f}",
        ),
        last_vol,
    )


def build_recommendation(df: pd.DataFrame) -> Recommendation:
    """`df` en az `Close` sütunu içeren, ısınma payı dahil tam geçmiş veridir."""

    close = df["Close"].dropna()
    if close.empty:
        raise ValueError("Fiyat verisi bulunamadı.")

    trend = _trend_factor(close)
    macd_factor, macd_value = _macd_factor(close)
    rsi_factor, rsi_value = _rsi_factor(close)
    momentum_factor, momentum_value = _momentum_factor(close)
    bollinger_factor, bollinger_value = _bollinger_factor(close)
    vol_factor, vol_value = _volatility_info(close)

    scoring_factors = (trend, macd_factor, rsi_factor, momentum_factor, bollinger_factor)
    total_score = _clip(sum(f.score * f.weight for f in scoring_factors))

    if total_score >= _SIGNAL_THRESHOLD:
        signal = Signal.AL
    elif total_score <= -_SIGNAL_THRESHOLD:
        signal = Signal.SAT
    else:
        signal = Signal.TUT

    insufficient = any(f.detail == INSUFFICIENT_DATA for f in scoring_factors)
    if insufficient:
        confidence = "Düşük"
    elif vol_value is not None and vol_value > _HIGH_VOLATILITY_PCT:
        confidence = "Orta"
    elif abs(total_score) > 0.5:
        confidence = "Yüksek"
    else:
        confidence = "Orta"

    return Recommendation(
        signal=signal,
        score=total_score,
        confidence=confidence,
        factors=(trend, macd_factor, rsi_factor, momentum_factor, bollinger_factor, vol_factor),
        as_of=close.index[-1],
        price=float(close.iloc[-1]),
        rsi_value=rsi_value,
        momentum_value=momentum_value,
        volatility_value=vol_value,
        macd_histogram=macd_value,
        bollinger_pctb=bollinger_value,
    )


# --- Vektörize skor serileri -------------------------------------------------
#
# Aşağıdaki fonksiyonlar, yukarıdaki skorlama formüllerinin TÜM geçmiş için
# (her gün yalnızca o güne kadarki veriyle, ileriye bakmadan) hesaplanmış
# halidir. `build_recommendation` tek bir "son gün" anlık görüntüsü
# üretirken, bunlar backtest gibi geçmişin tamamını değerlendirmesi gereken
# analizler için kullanılır. Formüller yukarıdaki skaler fonksiyonlarla
# birebir aynıdır (bkz. test_recommendation.py'deki tutarlılık testleri).


def trend_score_series(close: pd.Series) -> pd.Series:
    sma_short = ind.sma(close, settings.sma_short)
    sma_long = ind.sma(close, settings.sma_long)
    spread = (sma_short - sma_long) / sma_long
    return (spread / 0.05).clip(-1.0, 1.0)


def rsi_score_series(close: pd.Series) -> pd.Series:
    rsi_series = ind.rsi(close, settings.rsi_period)
    oversold_score = ((30 - rsi_series) / 20).clip(upper=1.0)
    overbought_score = (-(rsi_series - 70) / 20).clip(lower=-1.0)
    score = np.select(
        [rsi_series <= 30, rsi_series >= 70],
        [oversold_score, overbought_score],
        default=0.0,
    )
    return pd.Series(score, index=rsi_series.index).mask(rsi_series.isna())


def momentum_score_series(close: pd.Series) -> pd.Series:
    mom_series = ind.momentum(close, settings.momentum_period)
    return (mom_series / 10).clip(-1.0, 1.0)


def macd_score_series(close: pd.Series) -> pd.Series:
    log_close = np.log(close)
    _macd_line, _signal_line, histogram = ind.macd(
        log_close, settings.macd_fast, settings.macd_slow, settings.macd_signal
    )
    return (histogram / _MACD_HIST_SATURATION).clip(-1.0, 1.0)


def bollinger_score_series(close: pd.Series) -> pd.Series:
    _middle, upper, lower = ind.bollinger_bands(close, settings.bollinger_window, settings.bollinger_std)
    band_width = upper - lower
    # Bölme yalnızca bant genişliği NaN iken (ısınma dönemi) sorun yaratır; tam
    # sıfır genişlik (hareketsiz fiyat) geçerli bir veridir ve aşağıda ayrıca
    # ele alınır — bu yüzden burada sıfıra bölme NaN'a çevrilmez.
    with np.errstate(divide="ignore", invalid="ignore"):
        pct_b = (close - lower) / band_width
    bullish = ((0.2 - pct_b) / 0.2).clip(upper=1.0)
    bearish = (-(pct_b - 0.8) / 0.2).clip(lower=-1.0)
    score = np.select(
        [pct_b <= 0.2, pct_b >= 0.8],
        [bullish, bearish],
        default=0.0,
    )
    score_series = pd.Series(score, index=close.index)
    # Sıfır bant genişliği de "nötr" (0.0) kabul edilir; yalnızca ısınma
    # döneminde (band_width NaN) gerçek veri yetersizliği söz konusudur.
    return score_series.mask(band_width.isna())


def total_score_series(close: pd.Series) -> pd.Series:
    """Her gün için ağırlıklı toplam skor; eksik gösterge nötr (0.0) kabul edilir."""

    trend = trend_score_series(close).fillna(0.0)
    macd_s = macd_score_series(close).fillna(0.0)
    rsi_s = rsi_score_series(close).fillna(0.0)
    mom = momentum_score_series(close).fillna(0.0)
    boll = bollinger_score_series(close).fillna(0.0)
    total = (
        trend * _TREND_WEIGHT
        + macd_s * _MACD_WEIGHT
        + rsi_s * _RSI_WEIGHT
        + mom * _MOMENTUM_WEIGHT
        + boll * _BOLLINGER_WEIGHT
    )
    return total.clip(-1.0, 1.0)


def signal_from_score_series(scores: pd.Series) -> pd.Series:
    signal = np.select(
        [scores >= _SIGNAL_THRESHOLD, scores <= -_SIGNAL_THRESHOLD],
        [Signal.AL.value, Signal.SAT.value],
        default=Signal.TUT.value,
    )
    return pd.Series(signal, index=scores.index)


def indicator_warmup_start(close: pd.Series) -> pd.Timestamp | None:
    """Beş gösterge faktörünün de ilk kez tanımlı olduğu tarih.

    Bu tarihten önceki günler, göstergeler için yeterli ısınma verisi
    birikmediğinden anlamlı bir sinyal taşımaz.
    """

    series_list = (
        trend_score_series(close),
        macd_score_series(close),
        rsi_score_series(close),
        momentum_score_series(close),
        bollinger_score_series(close),
    )
    first_valid = [s.first_valid_index() for s in series_list]
    if any(idx is None for idx in first_valid):
        return None
    return max(first_valid)
