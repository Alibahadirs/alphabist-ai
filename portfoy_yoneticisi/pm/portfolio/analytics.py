"""Portföy pozisyonlarından dağılım ve yoğunlaşma metrikleri.

Girdi olarak Streamlit sayfasında zaten oluşturulan, her biri en az
``Kategori``, ``Enstrüman`` ve ``Güncel Değer`` anahtarlarını içeren satır
sözlüklerinin listesi beklenir (yalnızca güncel değeri hesaplanabilen
pozisyonlar — ``Güncel Değer`` None olmayanlar).
"""

from __future__ import annotations

import pandas as pd

_CATEGORY_COLUMNS = ["Kategori", "Güncel Değer"]
_INSTRUMENT_COLUMNS = ["Enstrüman", "Güncel Değer"]


def category_allocation(valued_rows: list[dict]) -> pd.DataFrame:
    """Varlık sınıfına (Hisse/Kıymetli Maden/Döviz) göre toplam güncel değer dağılımı."""

    if not valued_rows:
        return pd.DataFrame(columns=_CATEGORY_COLUMNS)
    df = pd.DataFrame(valued_rows)
    grouped = df.groupby("Kategori", as_index=False)["Güncel Değer"].sum()
    return grouped.sort_values("Güncel Değer", ascending=False).reset_index(drop=True)


def instrument_allocation(valued_rows: list[dict]) -> pd.DataFrame:
    """Enstrümana göre toplam güncel değer dağılımı.

    Aynı enstrümanda birden fazla pozisyon/lot varsa birleştirilir.
    """

    if not valued_rows:
        return pd.DataFrame(columns=_INSTRUMENT_COLUMNS)
    df = pd.DataFrame(valued_rows)
    grouped = df.groupby("Enstrüman", as_index=False)["Güncel Değer"].sum()
    return grouped.sort_values("Güncel Değer", ascending=False).reset_index(drop=True)


def largest_position_share_pct(valued_rows: list[dict]) -> float | None:
    """Tek bir enstrümanın portföy içindeki en yüksek payı (%); boşsa None."""

    allocation = instrument_allocation(valued_rows)
    if allocation.empty:
        return None
    total = allocation["Güncel Değer"].sum()
    if total <= 0:
        return None
    return float(allocation["Güncel Değer"].iloc[0] / total * 100)
