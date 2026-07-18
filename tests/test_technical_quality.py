from datetime import date, datetime

from app.technical.models import TechnicalHistoryEntry
from app.technical.quality import build_technical_quality_summary


def _history_entry(
    entry_id: int,
    symbol: str,
    price_date: date,
    score: float,
) -> TechnicalHistoryEntry:
    return TechnicalHistoryEntry(
        id=entry_id,
        symbol=symbol,
        price_date=price_date,
        source="Yahoo Finance",
        total_score=score,
        signal="Al",
        rsi_value=55,
        atr_percent=2.4,
        score_breakdown={"trend": 15.0},
        alignment_status="Doğrulandı",
        methodology_version="technical-2026.1",
        created_at=datetime(2026, 7, 18, 9, 0),
    )


def test_build_technical_quality_summary_counts_all_statuses():
    summary = build_technical_quality_summary(
        ["AKSA", "GUBRF", "KERVN", "DEVA"],
        {
            "AKSA": [_history_entry(1, "AKSA", date(2026, 7, 17), 82)],
            "GUBRF": [_history_entry(2, "GUBRF", date(2026, 7, 1), 68)],
            "KERVN": [_history_entry(3, "KERVN", date(2026, 7, 19), 45)],
        },
        reference_date=date(2026, 7, 18),
    )

    assert summary.total == 4
    assert summary.current_count == 1
    assert summary.stale_count == 1
    assert summary.missing_count == 1
    assert summary.date_error_count == 1
    assert [row.status for row in summary.rows] == [
        "Güncel günlük veri",
        "Eski fiyat",
        "Tarih hatası",
        "Kayıt yok",
    ]


def test_build_technical_quality_summary_uses_latest_inserted_record():
    summary = build_technical_quality_summary(
        ["aksa", "AKSA", " "],
        {
            "aksa": [
                _history_entry(4, "AKSA", date(2026, 7, 17), 75),
                _history_entry(9, "AKSA", date(2026, 7, 18), 88),
            ]
        },
        reference_date=date(2026, 7, 18),
    )

    assert summary.total == 1
    assert summary.rows[0].technical_score == 88
    assert summary.rows[0].price_date == date(2026, 7, 18)
    assert summary.rows[0].current is True
