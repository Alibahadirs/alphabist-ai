from collections.abc import Callable, Sequence
from datetime import date

import pandas as pd

from app.market_data.freshness import assess_price_freshness
from app.market_data.validation import validate_quote_history_alignment
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


def refresh_technical_scores(
    symbols: Sequence[str],
    market_loader: MarketLoader,
    snapshot_saver: SnapshotSaver,
    methodology_version: str,
    reference_date: date | None = None,
) -> TechnicalRefreshSummary:
    items: list[TechnicalRefreshItem] = []
    for raw_symbol in symbols:
        symbol = raw_symbol.upper().strip()
        try:
            quote, history = market_loader(symbol)
            quote_date_value = quote.get("as_of_date")
            quote_date = (
                date.fromisoformat(str(quote_date_value))
                if quote_date_value
                else None
            )
            freshness = assess_price_freshness(
                quote_date,
                reference_date,
            )
            alignment = validate_quote_history_alignment(
                quote,
                history,
            )
            if not freshness.current or not alignment.valid:
                items.append(
                    TechnicalRefreshItem(
                        symbol=symbol,
                        status="Reddedildi",
                        detail=f"{freshness.status}; {alignment.status}",
                        price_date=quote_date,
                    )
                )
                continue

            score = calculate_technical_score(history)
            inserted = snapshot_saver(
                symbol,
                quote_date,
                str(quote.get("source") or "Bilinmiyor"),
                score,
                alignment.status,
                methodology_version,
            )
            items.append(
                TechnicalRefreshItem(
                    symbol=symbol,
                    status="Kaydedildi" if inserted else "Değişmedi",
                    detail=(
                        "Yeni doğrulanmış teknik kayıt oluşturuldu."
                        if inserted
                        else "Aynı piyasa günü ve metodoloji zaten kayıtlı."
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
