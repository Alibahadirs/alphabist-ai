from dataclasses import dataclass
from datetime import date


DEFAULT_MAX_PRICE_AGE_DAYS = 5


@dataclass(frozen=True)
class PriceFreshness:
    current: bool
    status: str
    age_days: int | None


def assess_price_freshness(
    as_of_date: date | None,
    reference_date: date | None = None,
    max_age_days: int = DEFAULT_MAX_PRICE_AGE_DAYS,
) -> PriceFreshness:
    if as_of_date is None:
        return PriceFreshness(
            current=False,
            status="Tarih bilinmiyor",
            age_days=None,
        )

    effective_reference_date = reference_date or date.today()
    age_days = (effective_reference_date - as_of_date).days
    if age_days < 0:
        return PriceFreshness(
            current=False,
            status="Tarih hatası",
            age_days=0,
        )
    if age_days <= max_age_days:
        return PriceFreshness(
            current=True,
            status="Güncel günlük veri",
            age_days=age_days,
        )
    return PriceFreshness(
        current=False,
        status="Eski fiyat",
        age_days=age_days,
    )
