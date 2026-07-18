from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

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
TECHNICAL_STATUS_OPTIONS = [
    CURRENT_STATUS,
    STALE_STATUS,
    MISSING_STATUS,
    DATE_ERROR_STATUS,
    METHODOLOGY_ERROR_STATUS,
    ALIGNMENT_ERROR_STATUS,
    SOURCE_ERROR_STATUS,
]
VERIFIED_ALIGNMENT_STATUSES = {
    "Fiyat ve grafik verisi uyumlu",
    "Doğrulandı",
}
INVALID_SOURCES = {"", "bilinmiyor", "unknown"}


@dataclass(frozen=True)
class TechnicalRecordHealth:
    status: str
    age_days: int | None
    current: bool
    methodology_current: bool
    alignment_verified: bool
    source_verified: bool


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

    if not freshness.current:
        status = freshness.status
    elif not methodology_current:
        status = METHODOLOGY_ERROR_STATUS
    elif not alignment_verified:
        status = ALIGNMENT_ERROR_STATUS
    elif not source_verified:
        status = SOURCE_ERROR_STATUS
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
        ),
        methodology_current=methodology_current,
        alignment_verified=alignment_verified,
        source_verified=source_verified,
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

        latest = max(history, key=lambda entry: entry.id)
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
        MISSING_STATUS: 4,
        STALE_STATUS: 5,
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
