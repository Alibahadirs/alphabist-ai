from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Position:
    instrument_code: str
    label: str
    category: str
    quantity: float
    unit_cost: float
    purchase_date: date
    note: str = ""
    id: int | None = None

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.unit_cost
