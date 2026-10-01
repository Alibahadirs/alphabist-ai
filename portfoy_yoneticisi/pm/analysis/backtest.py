"""Öneri motorunun geçmiş sinyallerinin doğruluğunu ölçen backtest.

Lookahead bias'tan kaçınmak için: her günün skoru/sinyali yalnızca o güne
kadarki verilerle hesaplanır (bkz. `recommendation.total_score_series`, tüm
göstergeler geriye dönük pencerelerdir). İleri getiri ise o sinyalden
`holding_days` işlem günü SONRAKİ kapanışla karşılaştırılarak hesaplanır; yani
sinyal üretildiği anda bilinmeyen gelecek veri, sinyali etkilemez.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .recommendation import Signal, indicator_warmup_start, signal_from_score_series, total_score_series


@dataclass(frozen=True)
class SignalStats:
    signal: str
    count: int
    hit_rate_pct: float | None  # beklenen yönde hareket eden sinyallerin yüzdesi
    avg_forward_return_pct: float | None


@dataclass(frozen=True)
class BacktestResult:
    holding_days: int
    evaluated_days: int
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    al: SignalStats
    sat: SignalStats
    tut: SignalStats


def _signal_stats(signal_name: str, forward_returns: pd.Series, expect_positive: bool | None) -> SignalStats:
    count = int(len(forward_returns))
    if count == 0:
        return SignalStats(signal_name, 0, None, None)
    avg_return = float(forward_returns.mean())
    if expect_positive is None:
        hit_rate = None
    elif expect_positive:
        hit_rate = float((forward_returns > 0).mean() * 100)
    else:
        hit_rate = float((forward_returns < 0).mean() * 100)
    return SignalStats(signal_name, count, hit_rate, avg_return)


def run_signal_backtest(df: pd.DataFrame, holding_days: int = 20) -> BacktestResult:
    """`df`, ısınma payı dahil tam geçmiş veridir (en az `Close` sütunu gerekir).

    `holding_days`: her sinyalden kaç işlem günü sonraki getirinin
    değerlendirileceği (varsayılan 20 ≈ 1 ay).
    """

    if holding_days < 1:
        raise ValueError("Tutma süresi en az 1 işlem günü olmalı.")

    close = df["Close"].dropna()
    if close.empty:
        raise ValueError("Fiyat verisi bulunamadı.")

    warm_start = indicator_warmup_start(close)
    if warm_start is None:
        raise ValueError("Göstergelerin hesaplanabilmesi için yeterli geçmiş veri yok.")

    scores = total_score_series(close)
    signals = signal_from_score_series(scores)
    forward_return = (close.shift(-holding_days) / close - 1.0) * 100

    valid = forward_return.notna() & (close.index >= warm_start)
    if not valid.any():
        raise ValueError(
            "Seçilen tutma süresi için yeterli ileri tarihli veri yok; "
            "daha kısa bir tutma süresi veya daha geniş bir tarih aralığı deneyin."
        )

    al_returns = forward_return[valid & (signals == Signal.AL.value)]
    sat_returns = forward_return[valid & (signals == Signal.SAT.value)]
    tut_returns = forward_return[valid & (signals == Signal.TUT.value)]
    valid_dates = close.index[valid]

    return BacktestResult(
        holding_days=holding_days,
        evaluated_days=int(valid.sum()),
        start_date=valid_dates[0],
        end_date=valid_dates[-1],
        al=_signal_stats(Signal.AL.value, al_returns, expect_positive=True),
        sat=_signal_stats(Signal.SAT.value, sat_returns, expect_positive=False),
        tut=_signal_stats(Signal.TUT.value, tut_returns, expect_positive=None),
    )
