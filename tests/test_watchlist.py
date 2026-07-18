from datetime import date, datetime

from app.database import repository
from app.scoring.models import FinancialMetrics
from app.watchlist.models import WatchlistEntry
from app.watchlist.service import build_watchlist_summary
from app.technical.models import TechnicalHistoryEntry


def _company(symbol: str, margin: float = 15) -> FinancialMetrics:
    return FinancialMetrics(
        symbol=symbol,
        company_name=f"{symbol} Test",
        revenue_growth=20,
        net_profit_growth=25,
        net_margin=margin,
        roe=25,
        debt_to_equity=0.5,
        current_ratio=1.8,
        operating_cash_flow=100,
        free_cash_flow=50,
        asset_turnover=0.8,
        valuation_score_input=75,
        management_score_input=80,
        risk_score_input=70,
    )


def test_watchlist_repository_adds_updates_and_removes(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()

    repository.upsert_watchlist_entry(
        WatchlistEntry(symbol="aaa", note="İlk not", target_alpha_score=80)
    )
    repository.upsert_watchlist_entry(
        WatchlistEntry(symbol="AAA", note="Güncel not", target_alpha_score=85)
    )

    entries = repository.list_watchlist_entries()
    assert len(entries) == 1
    assert entries[0].symbol == "AAA"
    assert entries[0].note == "Güncel not"
    assert entries[0].target_alpha_score == 85

    repository.remove_watchlist_entry("aaa")
    assert repository.list_watchlist_entries() == []


def test_watchlist_summary_ranks_scores_and_marks_targets():
    companies = {
        "HIGH": _company("HIGH", margin=25),
        "LOW": _company("LOW", margin=5),
    }
    entries = [
        WatchlistEntry(symbol="LOW", target_alpha_score=90),
        WatchlistEntry(symbol="HIGH", target_alpha_score=50),
    ]

    summary = build_watchlist_summary(entries, companies)

    assert summary.rows[0].symbol == "HIGH"
    assert summary.rows[0].target_reached is True
    assert summary.rows[1].target_reached is False
    assert summary.targets_reached == 1


def test_watchlist_uses_confidence_gated_decision_when_audits_are_supplied():
    company = _company("SAFE", margin=25)

    summary = build_watchlist_summary(
        [WatchlistEntry(symbol="SAFE")],
        {"SAFE": company},
        {},
    )

    assert summary.rows[0].decision == "Doğrula / Karar verme"
    assert summary.rows[0].confidence_score is not None
    assert summary.rows[0].confidence_status == "Düşük"
    assert summary.rows[0].decision_ready is False
    assert summary.rows[0].combined_decision_ready is False
    assert summary.rows[0].target_reached is False
    assert summary.decision_ready_count == 0
    assert summary.combined_decision_ready_count == 0


def _technical_history(
    identifier: int,
    score: float,
    price_date: date,
) -> TechnicalHistoryEntry:
    return TechnicalHistoryEntry(
        id=identifier,
        symbol="SAFE",
        price_date=price_date,
        source="Yahoo Finance",
        total_score=score,
        signal="Al",
        rsi_value=55,
        atr_percent=3,
        score_breakdown={},
        alignment_status="Fiyat ve grafik verisi uyumlu",
        methodology_version="technical-2026.1",
        created_at=datetime(2026, 7, 18, 10, identifier),
    )


def test_watchlist_tracks_current_technical_score_change():
    company = _company("SAFE", margin=25)
    summary = build_watchlist_summary(
        [WatchlistEntry(symbol="SAFE")],
        {"SAFE": company},
        technical_histories={
            "SAFE": [
                _technical_history(1, 65, date(2026, 7, 16)),
                _technical_history(2, 72, date(2026, 7, 17)),
            ]
        },
        reference_date=date(2026, 7, 18),
    )

    row = summary.rows[0]
    assert row.technical_score == 72
    assert row.technical_delta == 7
    assert row.technical_signal == "Al"
    assert row.technical_current is True
    assert row.combined_decision_ready is True
    assert row.technical_status == "Güncel günlük veri"
    assert summary.current_technical_count == 1
    assert summary.combined_decision_ready_count == 1
    assert summary.technical_strengthening_count == 1


def test_watchlist_does_not_count_stale_technical_signal():
    company = _company("SAFE", margin=25)
    summary = build_watchlist_summary(
        [WatchlistEntry(symbol="SAFE")],
        {"SAFE": company},
        technical_histories={
            "SAFE": [
                _technical_history(1, 65, date(2026, 7, 1)),
                _technical_history(2, 72, date(2026, 7, 2)),
            ]
        },
        reference_date=date(2026, 7, 18),
    )

    row = summary.rows[0]
    assert row.technical_current is False
    assert row.combined_decision_ready is False
    assert row.technical_status == "Eski fiyat"
    assert summary.current_technical_count == 0
    assert summary.combined_decision_ready_count == 0
    assert summary.technical_strengthening_count == 0
