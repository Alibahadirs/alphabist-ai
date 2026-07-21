from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketSourcePolicy:
    source: str
    delayed: bool
    official: bool
    supports_daily_decisions: bool
    disclosure: str


_SOURCE_POLICIES = {
    "yahoo finance": MarketSourcePolicy(
        source="Yahoo Finance",
        delayed=True,
        official=False,
        supports_daily_decisions=True,
        disclosure="Gecikmeli, resmi olmayan günlük piyasa verisi",
    ),
    "borsa-api / yahoo finance": MarketSourcePolicy(
        source="borsa-api / Yahoo Finance",
        delayed=True,
        official=False,
        supports_daily_decisions=True,
        disclosure="Yahoo Finance tabanlı gecikmeli yedek veri",
    ),
}


def get_source_policy(source: str | None) -> MarketSourcePolicy:
    normalized = str(source or "").strip().casefold()
    policy = _SOURCE_POLICIES.get(normalized)
    if policy is not None:
        return policy
    return MarketSourcePolicy(
        source=str(source or "Bilinmiyor").strip() or "Bilinmiyor",
        delayed=True,
        official=False,
        supports_daily_decisions=False,
        disclosure="Kaynak politikası tanımlı değil; karar verisine dahil edilmez",
    )


def quote_source_is_eligible(quote: dict) -> bool:
    policy = get_source_policy(quote.get("source"))
    return (
        policy.supports_daily_decisions
        and quote.get("data_mode") == "delayed"
        and quote.get("official") is False
    )
