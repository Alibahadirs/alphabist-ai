from collections.abc import Mapping, Sequence
from datetime import date

from app.market_data.freshness import assess_price_freshness
from app.technical.models import (
    TechnicalHistoryEntry,
    TechnicalQualityRow,
    TechnicalQualitySummary,
)


CURRENT_STATUS = "Güncel günlük veri"
STALE_STATUS = "Eski fiyat"
MISSING_STATUS = "Kayıt yok"
DATE_ERROR_STATUS = "Tarih hatası"


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
        freshness = assess_price_freshness(
            latest.price_date,
            reference_date=reference_date,
        )
        rows.append(
            TechnicalQualityRow(
                symbol=symbol,
                technical_score=latest.total_score,
                signal=latest.signal,
                price_date=latest.price_date,
                source=latest.source,
                methodology_version=latest.methodology_version,
                status=freshness.status,
                age_days=freshness.age_days,
                current=freshness.current,
            )
        )

    return TechnicalQualitySummary(
        rows=rows,
        total=len(rows),
        current_count=sum(row.status == CURRENT_STATUS for row in rows),
        stale_count=sum(row.status == STALE_STATUS for row in rows),
        missing_count=sum(row.status == MISSING_STATUS for row in rows),
        date_error_count=sum(row.status == DATE_ERROR_STATUS for row in rows),
    )
