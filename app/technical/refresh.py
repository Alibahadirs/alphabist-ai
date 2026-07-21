from collections.abc import Callable, Sequence
from datetime import date

import pandas as pd

from app.market_data.readiness import assess_quote_readiness
from app.technical.engine import calculate_technical_score
from app.technical.models import (
    TechnicalRefreshItem,
    TechnicalRefreshSummary,
    TechnicalScoreBreakdown,
)


MarketLoader = Callable[[str], tuple[dict, pd.DataFrame]]
SnapshotSaver = Callable[
    [str, date, str, TechnicalScoreBreakdown, str, str],
    bool,
]
MAX_TECHNICAL_REFRESH_BATCH = 20


def refresh_technical_scores(
    symbols: Sequence[str],
    market_loader: MarketLoader,
    snapshot_saver: SnapshotSaver,
    methodology_version: str,
    reference_date: date | None = None,
    max_batch_size: int = MAX_TECHNICAL_REFRESH_BATCH,
) -> TechnicalRefreshSummary:
    normalized_symbols = list(
        dict.fromkeys(
            symbol.upper().strip()
            for symbol in symbols
            if symbol.strip()
        )
    )
    if len(normalized_symbols) > max_batch_size:
        raise ValueError(
            "Teknik güncelleme tek seferde en fazla "
            f"{max_batch_size} hisse kabul eder."
        )

    items: list[TechnicalRefreshItem] = []
    for symbol in normalized_symbols:
        try:
            quote, history = market_loader(symbol)
            quote_date_value = quote.get("as_of_date")
            quote_date = (
                date.fromisoformat(str(quote_date_value))
                if quote_date_value
                else None
            )
            readiness = assess_quote_readiness(
                quote,
                history,
                reference_date,
            )
            alignment = readiness.alignment
            if not readiness.ready or alignment is None:
                items.append(
                    TechnicalRefreshItem(
                        symbol=symbol,
                        status="Reddedildi",
                        detail=readiness.status,
                        price_date=quote_date,
                    )
                )
                continue

            source = str(quote.get("source") or "").strip()
            score = calculate_technical_score(history)
            changed = snapshot_saver(
                symbol,
                quote_date,
                source,
                score,
                alignment.status,
                methodology_version,
            )
            items.append(
                TechnicalRefreshItem(
                    symbol=symbol,
                    status="Kaydedildi" if changed else "Değişmedi",
                    detail=(
                        "Doğrulanmış teknik kayıt oluşturuldu veya onarıldı."
                        if changed
                        else "Aynı doğrulanmış teknik kayıt zaten mevcut."
                    ),
                    price_date=quote_date,
                    technical_score=score.total,
                )
            )
        except Exception as exc:
            items.append(
                TechnicalRefreshItem(
                    symbol=symbol,
                    status="Hata",
                    detail=str(exc),
                )
            )

    return TechnicalRefreshSummary(
        total=len(items),
        saved=sum(item.status == "Kaydedildi" for item in items),
        unchanged=sum(item.status == "Değişmedi" for item in items),
        rejected=sum(item.status == "Reddedildi" for item in items),
        failed=sum(item.status == "Hata" for item in items),
        items=items,
    )
