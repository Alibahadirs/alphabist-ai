import pytest

from pm.portfolio.analytics import (
    category_allocation,
    instrument_allocation,
    largest_position_share_pct,
)


def _rows():
    return [
        {"Enstrüman": "THYAO", "Kategori": "Hisse (BIST)", "Güncel Değer": 3000.0},
        {"Enstrüman": "GARAN", "Kategori": "Hisse (BIST)", "Güncel Değer": 1000.0},
        {"Enstrüman": "USD/TRY", "Kategori": "Döviz", "Güncel Değer": 2000.0},
        # THYAO'ya ait ikinci bir lot (aynı enstrüman, farklı pozisyon):
        {"Enstrüman": "THYAO", "Kategori": "Hisse (BIST)", "Güncel Değer": 1000.0},
    ]


def test_category_allocation_sums_by_category():
    df = category_allocation(_rows())
    totals = dict(zip(df["Kategori"], df["Güncel Değer"]))
    assert totals == {"Hisse (BIST)": 5000.0, "Döviz": 2000.0}
    # En büyük kategori ilk sırada olmalı.
    assert df.iloc[0]["Kategori"] == "Hisse (BIST)"


def test_instrument_allocation_merges_same_instrument_positions():
    df = instrument_allocation(_rows())
    totals = dict(zip(df["Enstrüman"], df["Güncel Değer"]))
    assert totals == {"THYAO": 4000.0, "GARAN": 1000.0, "USD/TRY": 2000.0}
    assert df.iloc[0]["Enstrüman"] == "THYAO"


def test_largest_position_share_pct():
    share = largest_position_share_pct(_rows())
    # Toplam 7000, THYAO birleşik 4000 -> %57.14
    assert share == pytest.approx(4000 / 7000 * 100)


def test_empty_rows_return_empty_frames_and_none():
    assert category_allocation([]).empty
    assert instrument_allocation([]).empty
    assert largest_position_share_pct([]) is None
