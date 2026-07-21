from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class QuoteComparison:
    valid: bool
    status: str
    price_difference_percent: float | None
    change_difference_points: float | None
    date_gap_days: int | None


def compare_quotes(
    primary: dict,
    secondary: dict,
    price_tolerance_percent: float = 0.5,
    change_tolerance_points: float = 0.2,
    max_date_gap_days: int = 1,
) -> QuoteComparison:
    primary_price = _optional_float(primary.get("last"))
    secondary_price = _optional_float(secondary.get("last"))
    primary_date = _optional_date(primary.get("as_of_date"))
    secondary_date = _optional_date(secondary.get("as_of_date"))
    if (
        primary_price is None
        or secondary_price is None
        or primary_date is None
        or secondary_date is None
    ):
        return QuoteComparison(
            valid=False,
            status="Karşılaştırma için fiyat veya tarih eksik",
            price_difference_percent=None,
            change_difference_points=None,
            date_gap_days=None,
        )

    price_base = max(abs(primary_price), abs(secondary_price))
    price_difference = (
        abs(primary_price - secondary_price) / price_base * 100
        if price_base
        else 0.0
    )
    date_gap = abs((primary_date - secondary_date).days)

    primary_change = _optional_float(primary.get("change_percent"))
    secondary_change = _optional_float(secondary.get("change_percent"))
    change_difference = (
        abs(primary_change - secondary_change)
        if primary_change is not None and secondary_change is not None
        else None
    )

    reasons = []
    if date_gap > max_date_gap_days:
        reasons.append(f"tarihler {date_gap} gün farklı")
    if price_difference > price_tolerance_percent:
        reasons.append(f"fiyatlar %{price_difference:.2f} farklı")
    if (
        change_difference is not None
        and change_difference > change_tolerance_points
    ):
        reasons.append(
            f"günlük değişimler {change_difference:.2f} puan farklı"
        )

    return QuoteComparison(
        valid=not reasons,
        status=(
            "Sağlayıcı verileri uyumlu"
            if not reasons
            else "; ".join(reasons)
        ),
        price_difference_percent=round(price_difference, 4),
        change_difference_points=(
            round(change_difference, 4)
            if change_difference is not None
            else None
        ),
        date_gap_days=date_gap,
    )


def _optional_float(value: object) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _optional_date(value: object) -> date | None:
    try:
        return None if value is None else date.fromisoformat(str(value))
    except ValueError:
        return None
