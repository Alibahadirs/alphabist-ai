from datetime import date

import pandas as pd

from app.market_data.readiness import assess_quote_readiness


def _quote(source="Yahoo Finance", quote_date="2026-07-21"):
    return {
        "last": 100,
        "as_of_date": quote_date,
        "source": source,
        "data_mode": "delayed",
        "official": False,
    }


def _history(price=100, history_date="2026-07-21"):
    return pd.DataFrame(
        {"Close": [price]},
        index=pd.to_datetime([history_date]),
    )


def test_known_fresh_aligned_quote_is_ready():
    result = assess_quote_readiness(
        _quote(),
        _history(),
        reference_date=date(2026, 7, 21),
    )

    assert result.ready is True
    assert result.status == "Karara uygun gecikmeli veri"
    assert result.source_eligible is True
    assert result.alignment is not None and result.alignment.valid


def test_unknown_source_is_rejected_even_when_fresh():
    result = assess_quote_readiness(
        _quote(source="Bilinmeyen kaynak"),
        _history(),
        reference_date=date(2026, 7, 21),
    )

    assert result.ready is False
    assert "karar verisine dahil edilmez" in result.status


def test_stale_or_misaligned_quote_is_rejected():
    stale = assess_quote_readiness(
        _quote(quote_date="2026-07-01"),
        _history(history_date="2026-07-01"),
        reference_date=date(2026, 7, 21),
    )
    misaligned = assess_quote_readiness(
        _quote(),
        _history(price=90),
        reference_date=date(2026, 7, 21),
    )

    assert stale.ready is False
    assert "Eski fiyat" in stale.status
    assert misaligned.ready is False
    assert "grafik kapanışı" in misaligned.status
