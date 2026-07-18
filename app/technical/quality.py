from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from math import isfinite

from app.core.settings import settings
from app.market_data.freshness import assess_price_freshness
from app.technical.models import (
    TechnicalHistoryEntry,
    TechnicalQualityRow,
    TechnicalQualitySummary,
)
from app.technical.refresh import MAX_TECHNICAL_REFRESH_BATCH


CURRENT_STATUS = "Güncel günlük veri"
STALE_STATUS = "Eski fiyat"
MISSING_STATUS = "Kayıt yok"
DATE_ERROR_STATUS = "Tarih hatası"
METHODOLOGY_ERROR_STATUS = "Eski teknik metodoloji"
ALIGNMENT_ERROR_STATUS = "Hizalama doğrulanmadı"
SOURCE_ERROR_STATUS = "Kaynak doğrulanmadı"
SCORE_INTEGRITY_ERROR_STATUS = "Teknik puan tutarsız"
TECHNICAL_STATUS_OPTIONS = [
    CURRENT_STATUS,
    STALE_STATUS,
    MISSING_STATUS,
    DATE_ERROR_STATUS,
    METHODOLOGY_ERROR_STATUS,
    ALIGNMENT_ERROR_STATUS,
    SOURCE_ERROR_STATUS,
    SCORE_INTEGRITY_ERROR_STATUS,
]
VERIFIED_ALIGNMENT_STATUSES = {
    "Fiyat ve grafik verisi uyumlu",
    "Doğrulandı",
}
INVALID_SOURCES = {"", "bilinmiyor", "unknown"}
SCORE_FIELD_LIMITS = {
    "trend": 20.0,
    "moving_averages": 20.0,
    "rsi": 15.0,
    "macd": 15.0,
    "volume": 15.0,
    "support_resistance": 15.0,
}
SCORE_TOLERANCE = 0.01


@dataclass(frozen=True)
class TechnicalRecordHealth:
    status: str
    age_days: int | None
    current: bool
    methodology_current: bool
    alignment_verified: bool
    source_verified: bool
    score_integrity_verified: bool


def _expected_signal(total_score: float) -> str:
    if total_score >= 85:
        return "Güçlü Al"
    if total_score >= 70:
        return "Al"
    if total_score >= 55:
        return "İzle"
    if total_score >= 40:
        return "Bekle"
    return "Kaçın"


def verify_technical_score_integrity(
    entry: TechnicalHistoryEntry,
) -> bool:
    if set(entry.score_breakdown) != set(SCORE_FIELD_LIMITS):
        return False

    values: list[float] = []
    for field, maximum in SCORE_FIELD_LIMITS.items():
        raw_value = entry.score_breakdown.get(field)
        if isinstance(raw_value, bool):
            return False
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return False
        if not isfinite(value) or not 0 <= value <= maximum:
            return False
        values.append(value)

    return (
        abs(sum(values) - entry.total_score) <= SCORE_TOLERANCE
        and entry.signal == _expected_signal(entry.total_score)
    )


def select_latest_technical_record(
    history: Sequence[TechnicalHistoryEntry],
) -> TechnicalHistoryEntry | None:
    return max(history, key=lambda entry: entry.id, default=None)


def select_previous_comparable_record(
    history: Sequence[TechnicalHistoryEntry],
    latest: TechnicalHistoryEntry | None,
) -> TechnicalHistoryEntry | None:
    if latest is None:
        return None

    candidates = [
        entry
        for entry in history
        if entry.id != latest.id
        and entry.price_date < latest.price_date
        and entry.methodology_version == latest.methodology_version
        and entry.alignment_status in VERIFIED_ALIGNMENT_STATUSES
        and entry.source.strip().casefold() not in INVALID_SOURCES
        and verify_technical_score_integrity(entry)
    ]
    return max(
        candidates,
        key=lambda entry: (entry.price_date, entry.id),
        default=None,
    )


def assess_technical_record(
    entry: TechnicalHistoryEntry | None,
    reference_date: date | None = None,
) -> TechnicalRecordHealth:
    if entry is None:
        return TechnicalRecordHealth(
            status=MISSING_STATUS,
            age_days=None,
            current=False,
            methodology_current=False,
            alignment_verified=False,
            source_verified=False,
            score_integrity_verified=False,
        )

    freshness = assess_price_freshness(
        entry.price_date,
        reference_date=reference_date,
    )
    methodology_current = (
        entry.methodology_version == settings.technical_methodology_version
    )
    alignment_verified = (
        entry.alignment_status in VERIFIED_ALIGNMENT_STATUSES
    )
    source_verified = entry.source.strip().casefold() not in INVALID_SOURCES
    score_integrity_verified = verify_technical_score_integrity(entry)

    if not freshness.current:
        status = freshness.status
    elif not methodology_current:
        status = METHODOLOGY_ERROR_STATUS
    elif not alignment_verified:
        status = ALIGNMENT_ERROR_STATUS
    elif not source_verified:
        status = SOURCE_ERROR_STATUS
    elif not score_integrity_verified:
        status = SCORE_INTEGRITY_ERROR_STATUS
    else:
        status = CURRENT_STATUS

    return TechnicalRecordHealth(
        status=status,
        age_days=freshness.age_days,
        current=(
            freshness.current
            and methodology_current
            and alignment_verified
            and source_verified
            and score_integrity_verified
        ),
        methodology_current=methodology_current,
        alignment_verified=alignment_verified,
        source_verified=source_verified,
        score_integrity_verified=score_integrity_verified,
    )


def build_technical_quality_summary(
    symbols: Sequence[str],
    histories: Mapping[str, Sequence[TechnicalHistoryEntry]],
    reference_date: date | None = None,
) -> TechnicalQualitySummary:
    normalized_histories = {
        symbol.upper().strip(): list(entries)
        for symbol, entries in histories.items()
    }
    normalized_symbols = list(
        dict.fromkeys(
            symbol.upper().strip()
            for symbol in symbols
            if symbol and symbol.strip()
        )
    )
    rows: list[TechnicalQualityRow] = []

    for symbol in normalized_symbols:
        history = normalized_histories.get(symbol, [])
        if not history:
            rows.append(
                TechnicalQualityRow(
                    symbol=symbol,
                    status=MISSING_STATUS,
                )
            )
            continue

        latest = select_latest_technical_record(history)
        if latest is None:
            continue
        health = assess_technical_record(latest, reference_date)
        rows.append(
            TechnicalQualityRow(
                symbol=symbol,
                technical_score=latest.total_score,
                signal=latest.signal,
                price_date=latest.price_date,
                source=latest.source,
                methodology_version=latest.methodology_version,
                alignment_status=latest.alignment_status,
                status=health.status,
                age_days=health.age_days,
                current=health.current,
                methodology_current=health.methodology_current,
                alignment_verified=health.alignment_verified,
                source_verified=health.source_verified,
                score_integrity_verified=health.score_integrity_verified,
            )
        )

    return TechnicalQualitySummary(
        rows=rows,
        total=len(rows),
        current_count=sum(row.status == CURRENT_STATUS for row in rows),
        stale_count=sum(row.status == STALE_STATUS for row in rows),
        missing_count=sum(row.status == MISSING_STATUS for row in rows),
        date_error_count=sum(row.status == DATE_ERROR_STATUS for row in rows),
        methodology_error_count=sum(
            row.status == METHODOLOGY_ERROR_STATUS for row in rows
        ),
        alignment_error_count=sum(
            row.status == ALIGNMENT_ERROR_STATUS for row in rows
        ),
        source_error_count=sum(
            row.status == SOURCE_ERROR_STATUS for row in rows
        ),
        score_integrity_error_count=sum(
            row.status == SCORE_INTEGRITY_ERROR_STATUS for row in rows
        ),
    )


def select_technical_refresh_candidates(
    summary: TechnicalQualitySummary,
    max_batch_size: int = MAX_TECHNICAL_REFRESH_BATCH,
) -> list[str]:
    if max_batch_size < 1:
        return []

    priority = {
        DATE_ERROR_STATUS: 0,
        METHODOLOGY_ERROR_STATUS: 1,
        ALIGNMENT_ERROR_STATUS: 2,
        SOURCE_ERROR_STATUS: 3,
        SCORE_INTEGRITY_ERROR_STATUS: 4,
        MISSING_STATUS: 5,
        STALE_STATUS: 6,
    }
    candidates = [
        row for row in summary.rows
        if row.status in priority
    ]
    candidates.sort(
        key=lambda row: (
            priority[row.status],
            -(row.age_days or 0),
            row.symbol,
        )
    )
    return [row.symbol for row in candidates[:max_batch_size]]
