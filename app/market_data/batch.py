from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.market_data.diagnostics import MarketDiagnostic, diagnose_market_data


MAX_MARKET_DIAGNOSTIC_BATCH = 20
DiagnosticLoader = Callable[[str], MarketDiagnostic]


@dataclass(frozen=True)
class MarketBatchItem:
    symbol: str
    diagnostic: MarketDiagnostic | None
    status: str
    error: str | None = None


@dataclass(frozen=True)
class MarketBatchSummary:
    total: int
    cross_verified: int
    partial: int
    unavailable: int
    failed: int
    items: tuple[MarketBatchItem, ...]


def diagnose_market_batch(
    symbols: Sequence[str],
    diagnostic_loader: DiagnosticLoader = diagnose_market_data,
    max_batch_size: int = MAX_MARKET_DIAGNOSTIC_BATCH,
) -> MarketBatchSummary:
    normalized = list(
        dict.fromkeys(
            symbol.strip().upper()
            for symbol in symbols
            if symbol.strip()
        )
    )
    if len(normalized) > max_batch_size:
        raise ValueError(
            f"Toplu piyasa kontrolü en fazla {max_batch_size} hisse kabul eder."
        )
    invalid = [symbol for symbol in normalized if not symbol.isalnum()]
    if invalid:
        raise ValueError("Geçersiz hisse kodu: " + ", ".join(invalid))

    items = []
    for symbol in normalized:
        try:
            diagnostic = diagnostic_loader(symbol)
        except Exception as exc:
            items.append(
                MarketBatchItem(
                    symbol=symbol,
                    diagnostic=None,
                    status="Hata",
                    error=str(exc),
                )
            )
            continue
        if diagnostic.cross_verified:
            status = "Çapraz doğrulandı"
        elif diagnostic.primary.available or diagnostic.secondary.available:
            status = "Kısmi veri"
        else:
            status = "Veri yok"
        items.append(
            MarketBatchItem(
                symbol=symbol,
                diagnostic=diagnostic,
                status=status,
            )
        )

    return MarketBatchSummary(
        total=len(items),
        cross_verified=sum(item.status == "Çapraz doğrulandı" for item in items),
        partial=sum(item.status == "Kısmi veri" for item in items),
        unavailable=sum(item.status == "Veri yok" for item in items),
        failed=sum(item.status == "Hata" for item in items),
        items=tuple(items),
    )
