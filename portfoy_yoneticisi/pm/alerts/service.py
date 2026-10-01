"""Günlük sinyal taraması: portföy + izleme listesindeki enstrümanlardan
Al/Sat eşiğini aşanları bulur.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..analysis.recommendation import Recommendation, Signal, build_recommendation
from ..core.symbols import Instrument, resolve_instrument
from ..data.market_data import NOT_FOUND_MESSAGE, fetch_instruments_history_with_warmup
from ..portfolio.store import list_positions

_LOOKBACK_DAYS = 10


@dataclass(frozen=True)
class AlertRow:
    instrument: Instrument
    recommendation: Recommendation


@dataclass(frozen=True)
class DailyScanResult:
    generated_at: datetime
    requested: int
    evaluated: int
    actionable: tuple[AlertRow, ...]  # Al veya Sat sinyaline ulaşanlar
    errors: tuple[str, ...]


def build_watch_list(extra_codes: list[str] | tuple[str, ...] = ()) -> list[Instrument]:
    """Portföydeki pozisyonlar ile ek izleme kodlarının tekilleştirilmiş birleşimi."""

    instruments: dict[str, Instrument] = {}
    for pos in list_positions():
        inst = resolve_instrument(pos.instrument_code)
        instruments[inst.code] = inst
    for code in extra_codes:
        inst = resolve_instrument(code)
        instruments[inst.code] = inst
    return list(instruments.values())


def run_daily_scan(
    extra_codes: list[str] | tuple[str, ...] = (), lookback_days: int = _LOOKBACK_DAYS
) -> DailyScanResult:
    instruments = build_watch_list(extra_codes)
    if not instruments:
        raise RuntimeError(
            "İzlenecek enstrüman yok: portföye pozisyon ekleyin veya izleme listesine kod girin."
        )

    today = date.today()
    start = today - timedelta(days=lookback_days)
    history_by_code = fetch_instruments_history_with_warmup(instruments, start, today)

    actionable: list[AlertRow] = []
    errors: list[str] = []
    evaluated = 0
    for inst in instruments:
        fetched = history_by_code.get(inst.code)
        if fetched is None:
            errors.append(f"{inst.label}: {NOT_FOUND_MESSAGE}")
            continue
        padded, _visible = fetched
        try:
            rec = build_recommendation(padded)
        except ValueError as exc:
            errors.append(f"{inst.label}: {exc}")
            continue
        evaluated += 1
        if rec.signal in (Signal.AL, Signal.SAT):
            actionable.append(AlertRow(inst, rec))

    return DailyScanResult(
        generated_at=datetime.now(),
        requested=len(instruments),
        evaluated=evaluated,
        actionable=tuple(actionable),
        errors=tuple(errors),
    )
