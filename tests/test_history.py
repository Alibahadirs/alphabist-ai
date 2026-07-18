from app.database import repository
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.technical.models import TechnicalScoreBreakdown
from datetime import date

import pytest


def _company(margin: float) -> FinancialMetrics:
    return FinancialMetrics(
        symbol="TEST",
        company_name="Test Şirketi",
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


def test_score_history_is_saved_in_chronological_order(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()

    first_company = _company(5)
    second_company = _company(25)
    repository.upsert_company(first_company)
    repository.add_score_history(
        first_company.symbol,
        calculate_alpha_score(first_company),
    )
    repository.upsert_company(second_company)
    repository.add_score_history(
        second_company.symbol,
        calculate_alpha_score(second_company),
    )

    history = repository.list_score_history("test")

    assert len(history) == 2
    assert history[0].id < history[1].id
    assert history[0].total_score < history[1].total_score
    assert all(entry.symbol == "TEST" for entry in history)


def test_technical_history_deduplicates_same_market_snapshot(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    company = _company(15)
    repository.upsert_company(company)
    score = TechnicalScoreBreakdown(
        trend=15,
        moving_averages=15,
        rsi=10,
        macd=10,
        volume=10,
        support_resistance=10,
        total=70,
        signal="Al",
        rsi_value=55,
        atr_percent=3.2,
    )

    first_insert = repository.add_technical_score_history(
        symbol="test",
        price_date=date(2026, 7, 17),
        source="Yahoo Finance",
        score=score,
        alignment_status="Fiyat ve grafik verisi uyumlu",
        methodology_version="technical-2026.1",
    )
    duplicate_insert = repository.add_technical_score_history(
        symbol="TEST",
        price_date=date(2026, 7, 17),
        source="Yahoo Finance",
        score=score,
        alignment_status="Fiyat ve grafik verisi uyumlu",
        methodology_version="technical-2026.1",
    )

    history = repository.list_technical_score_history("test")
    assert first_insert is True
    assert duplicate_insert is False
    assert len(history) == 1
    assert history[0].symbol == "TEST"
    assert history[0].price_date == date(2026, 7, 17)
    assert history[0].total_score == 70
    assert history[0].score_breakdown["trend"] == 15


def test_technical_history_repairs_changed_same_market_snapshot(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.upsert_company(_company(15))
    score = TechnicalScoreBreakdown(
        trend=15,
        moving_averages=15,
        rsi=10,
        macd=10,
        volume=10,
        support_resistance=10,
        total=70,
        signal="Al",
        rsi_value=55,
        atr_percent=3.2,
    )
    repository.add_technical_score_history(
        symbol="TEST",
        price_date=date(2026, 7, 17),
        source="Yahoo Finance",
        score=score,
        alignment_status="Fiyat ve grafik verisi uyumlu",
        methodology_version="technical-2026.1",
    )
    original_id = repository.list_technical_score_history("TEST")[0].id
    with repository.connect() as conn:
        conn.execute(
            """UPDATE technical_score_history
            SET total_score=99, score_breakdown='{}',
            alignment_status='Hatalı'
            WHERE symbol='TEST'"""
        )

    repaired = repository.add_technical_score_history(
        symbol="TEST",
        price_date=date(2026, 7, 17),
        source="Yahoo Finance",
        score=score,
        alignment_status="Fiyat ve grafik verisi uyumlu",
        methodology_version="technical-2026.1",
    )

    history = repository.list_technical_score_history("TEST")
    assert repaired is True
    assert len(history) == 1
    assert history[0].id == original_id
    assert history[0].total_score == 70
    assert history[0].score_breakdown["trend"] == 15
    assert history[0].alignment_status == "Fiyat ve grafik verisi uyumlu"


def test_technical_history_rejects_unknown_source(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.upsert_company(_company(15))
    score = TechnicalScoreBreakdown(
        trend=15,
        moving_averages=15,
        rsi=10,
        macd=10,
        volume=10,
        support_resistance=10,
        total=70,
        signal="Al",
        rsi_value=55,
        atr_percent=3.2,
    )

    with pytest.raises(ValueError, match="kaynağı doğrulanmadı"):
        repository.add_technical_score_history(
            symbol="TEST",
            price_date=date(2026, 7, 17),
            source="Bilinmiyor",
            score=score,
            alignment_status="Fiyat ve grafik verisi uyumlu",
            methodology_version="technical-2026.1",
        )
