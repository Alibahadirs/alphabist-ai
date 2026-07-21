from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


PERCENT_TOLERANCE = 0.05


@dataclass(frozen=True)
class NormalizedQuote:
    last: float
    previous: float | None
    change: float | None
    change_percent: float | None
    percent_corrected: bool


def normalize_quote_values(
    last: float,
    previous: float | None,
    change: float | None = None,
    change_percent: float | None = None,
) -> NormalizedQuote:
    """Derive internally consistent price-change values.

    Provider percentages are treated as advisory. Whenever a valid previous
    close is available, the application recalculates both the absolute and
    percentage change from prices.
    """
    last_value = _finite_number(last, "Son fiyat")
    if last_value <= 0:
        raise ValueError("Son fiyat sıfırdan büyük olmalıdır.")

    previous_value = _optional_finite_number(previous, "Önceki kapanış")
    if previous_value is None or previous_value <= 0:
        return NormalizedQuote(
            last=last_value,
            previous=previous_value,
            change=_optional_finite_number(change, "Değişim"),
            change_percent=_optional_finite_number(
                change_percent,
                "Değişim yüzdesi",
            ),
            percent_corrected=False,
        )

    calculated_change = last_value - previous_value
    calculated_percent = calculated_change / previous_value * 100
    supplied_percent = _optional_finite_number(
        change_percent,
        "Değişim yüzdesi",
    )
    percent_corrected = (
        supplied_percent is not None
        and abs(supplied_percent - calculated_percent) > PERCENT_TOLERANCE
    )
    return NormalizedQuote(
        last=last_value,
        previous=previous_value,
        change=calculated_change,
        change_percent=calculated_percent,
        percent_corrected=percent_corrected,
    )


def _finite_number(value: float, label: str) -> float:
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{label} geçerli bir sayı olmalıdır.")
    return number


def _optional_finite_number(
    value: float | None,
    label: str,
) -> float | None:
    return None if value is None else _finite_number(value, label)
