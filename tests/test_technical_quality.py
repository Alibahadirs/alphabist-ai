from datetime import date, datetime

from app.technical.models import TechnicalHistoryEntry
from app.technical.quality import (
    build_technical_quality_summary,
    select_technical_refresh_candidates,
)


def _score_breakdown(score: float) -> dict[str, float]:
    remaining = score
    breakdown: dict[str, float] = {}
    for field, maximum in (
        ("trend", 20),
        ("moving_averages", 20),
        ("rsi", 15),
        ("macd", 15),
        ("volume", 15),
        ("support_resistance", 15),
    ):
        value = min(remaining, maximum)
        breakdown[field] = value
        remaining -= value
    return breakdown


def _signal(score: float) -> str:
    if score >= 85:
        return "Güçlü Al"
    if score >= 70:
        return "Al"
    if score >= 55:
        return "İzle"
    if score >= 40:
        return "Bekle"
    return "Kaçın"


def _history_entry(
    entry_id: int,
    symbol: str,
    price_date: date,
    score: float,
    *,
    source: str = "Yahoo Finance",
    alignment_status: str = "Doğrulandı",
    methodology_version: str = "technical-2026.1",
) -> TechnicalHistoryEntry:
    return TechnicalHistoryEntry(
        id=entry_id,
        symbol=symbol,
        price_date=price_date,
        source=source,
        total_score=score,
        signal=_signal(score),
        rsi_value=55,
        atr_percent=2.4,
        score_breakdown=_score_breakdown(score),
        alignment_status=alignment_status,
        methodology_version=methodology_version,
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


def test_refresh_candidates_prioritize_errors_missing_and_oldest_stale():
    summary = build_technical_quality_summary(
        ["CURRENT", "STALE_NEW", "MISSING", "FUTURE", "STALE_OLD"],
        {
            "CURRENT": [
                _history_entry(1, "CURRENT", date(2026, 7, 17), 80)
            ],
            "STALE_NEW": [
                _history_entry(2, "STALE_NEW", date(2026, 7, 10), 70)
            ],
            "FUTURE": [
                _history_entry(3, "FUTURE", date(2026, 7, 19), 60)
            ],
            "STALE_OLD": [
                _history_entry(4, "STALE_OLD", date(2026, 6, 1), 50)
            ],
        },
        reference_date=date(2026, 7, 18),
    )

    assert select_technical_refresh_candidates(summary) == [
        "FUTURE",
        "MISSING",
        "STALE_OLD",
        "STALE_NEW",
    ]
    assert select_technical_refresh_candidates(summary, max_batch_size=2) == [
        "FUTURE",
        "MISSING",
    ]
    assert select_technical_refresh_candidates(summary, max_batch_size=0) == []


def test_technical_quality_rejects_unverified_record_metadata():
    summary = build_technical_quality_summary(
        ["METHOD", "ALIGN", "SOURCE", "HEALTHY"],
        {
            "METHOD": [
                _history_entry(
                    1,
                    "METHOD",
                    date(2026, 7, 17),
                    80,
                    methodology_version="technical-legacy",
                )
            ],
            "ALIGN": [
                _history_entry(
                    2,
                    "ALIGN",
                    date(2026, 7, 17),
                    75,
                    alignment_status="Fiyat tarihleri 3 gün farklı",
                )
            ],
            "SOURCE": [
                _history_entry(
                    3,
                    "SOURCE",
                    date(2026, 7, 17),
                    70,
                    source="Bilinmiyor",
                )
            ],
            "HEALTHY": [
                _history_entry(
                    4,
                    "HEALTHY",
                    date(2026, 7, 17),
                    85,
                    alignment_status="Fiyat ve grafik verisi uyumlu",
                )
            ],
        },
        reference_date=date(2026, 7, 18),
    )

    rows = {row.symbol: row for row in summary.rows}
    assert rows["METHOD"].status == "Eski teknik metodoloji"
    assert rows["ALIGN"].status == "Hizalama doğrulanmadı"
    assert rows["ALIGN"].alignment_status == "Fiyat tarihleri 3 gün farklı"
    assert rows["ALIGN"].alignment_verified is False
    assert rows["SOURCE"].status == "Kaynak doğrulanmadı"
    assert rows["SOURCE"].source_verified is False
    assert rows["HEALTHY"].current is True
    assert rows["HEALTHY"].methodology_current is True
    assert summary.current_count == 1
    assert summary.methodology_error_count == 1
    assert summary.alignment_error_count == 1
    assert summary.source_error_count == 1
    assert summary.score_integrity_error_count == 0
    assert select_technical_refresh_candidates(summary) == [
        "METHOD",
        "ALIGN",
        "SOURCE",
    ]


def test_technical_quality_rejects_score_breakdown_mismatch():
    invalid = _history_entry(
        1,
        "BROKEN",
        date(2026, 7, 17),
        80,
    ).model_copy(
        update={
            "score_breakdown": {
                **_score_breakdown(80),
                "trend": 5,
            }
        }
    )
    summary = build_technical_quality_summary(
        ["BROKEN"],
        {"BROKEN": [invalid]},
        reference_date=date(2026, 7, 18),
    )

    row = summary.rows[0]
    assert row.status == "Teknik puan tutarsız"
    assert row.current is False
    assert row.score_integrity_verified is False
    assert summary.score_integrity_error_count == 1
    assert select_technical_refresh_candidates(summary) == ["BROKEN"]
