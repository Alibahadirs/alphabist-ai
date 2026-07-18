from datetime import date, datetime

from app.scanner.models import ScannerFilters
from app.scanner.service import scan_companies
from app.scoring.models import FinancialMetrics
from app.technical.models import TechnicalHistoryEntry


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


def _company(
    symbol: str,
    margin: float,
    revenue_growth: float,
    debt_to_equity: float,
    operating_cash_flow: float,
) -> FinancialMetrics:
    return FinancialMetrics(
        symbol=symbol,
        company_name=f"{symbol} Şirketi",
        revenue_growth=revenue_growth,
        net_profit_growth=25,
        net_margin=margin,
        roe=25,
        debt_to_equity=debt_to_equity,
        current_ratio=1.8,
        operating_cash_flow=operating_cash_flow,
        free_cash_flow=50,
        asset_turnover=0.8,
        valuation_score_input=75,
        management_score_input=80,
        risk_score_input=70,
    )


def test_scanner_filters_and_ranks_matching_companies():
    strong = _company("STRONG", 25, 30, 0.4, 100)
    weak_cash = _company("CASH", 20, 25, 0.5, -10)
    high_debt = _company("DEBT", 20, 25, 4, 100)

    summary = scan_companies(
        [weak_cash, high_debt, strong],
        ScannerFilters(
            minimum_alpha_score=50,
            minimum_revenue_growth=10,
            minimum_net_margin=10,
            maximum_debt_to_equity=2,
            positive_operating_cash_flow_only=True,
        ),
    )

    assert summary.total_scanned == 3
    assert summary.matched_count == 1
    assert summary.rows[0].symbol == "STRONG"


def test_scanner_returns_empty_summary_when_nothing_matches():
    summary = scan_companies(
        [_company("LOW", 1, -20, 5, -10)],
        ScannerFilters(minimum_alpha_score=90),
    )

    assert summary.rows == []
    assert summary.matched_count == 0
    assert summary.average_alpha_score == 0


def test_scanner_uses_confidence_gated_decision_when_audits_are_supplied():
    company = _company("SAFE", 25, 30, 0.4, 100)

    summary = scan_companies(
        [company],
        ScannerFilters(minimum_alpha_score=0),
        {},
    )

    assert summary.rows[0].decision == "Doğrula / Karar verme"
    assert summary.rows[0].confidence_score is not None
    assert summary.rows[0].confidence_status == "Düşük"
    assert summary.rows[0].decision_ready is False


def test_scanner_can_hide_companies_that_are_not_decision_ready():
    company = _company("SAFE", 25, 30, 0.4, 100)

    summary = scan_companies(
        [company],
        ScannerFilters(
            minimum_alpha_score=0,
            decision_ready_only=True,
        ),
        {},
    )

    assert summary.rows == []
    assert summary.matched_count == 0


def _technical_history(
    symbol: str,
    identifier: int,
    score: float,
    price_date: date,
    *,
    methodology_version: str = "technical-2026.1",
) -> TechnicalHistoryEntry:
    return TechnicalHistoryEntry(
        id=identifier,
        symbol=symbol,
        price_date=price_date,
        source="Yahoo Finance",
        total_score=score,
        signal=_signal(score),
        rsi_value=55,
        atr_percent=3,
        score_breakdown=_score_breakdown(score),
        alignment_status="Fiyat ve grafik verisi uyumlu",
        methodology_version=methodology_version,
        created_at=datetime(2026, 7, 18, 10, identifier),
    )


def test_scanner_filters_by_current_and_strengthening_technical_score():
    rising = _company("RISING", 25, 30, 0.4, 100)
    stale = _company("STALE", 25, 30, 0.4, 100)
    summary = scan_companies(
        [rising, stale],
        ScannerFilters(
            minimum_alpha_score=0,
            positive_operating_cash_flow_only=False,
            minimum_technical_score=70,
            technical_strengthening_only=True,
        ),
        technical_histories={
            "RISING": [
                _technical_history(
                    "RISING", 1, 65, date(2026, 7, 16)
                ),
                _technical_history(
                    "RISING", 2, 75, date(2026, 7, 17)
                ),
            ],
            "STALE": [
                _technical_history(
                    "STALE", 3, 65, date(2026, 7, 1)
                ),
                _technical_history(
                    "STALE", 4, 80, date(2026, 7, 2)
                ),
            ],
        },
        reference_date=date(2026, 7, 18),
    )

    assert [row.symbol for row in summary.rows] == ["RISING"]
    assert summary.rows[0].technical_score == 75
    assert summary.rows[0].technical_delta == 10
    assert summary.rows[0].technical_current is True
    assert summary.current_technical_count == 1


def test_scanner_keeps_companies_without_technical_filter():
    company = _company("PLAIN", 25, 30, 0.4, 100)
    summary = scan_companies(
        [company],
        ScannerFilters(
            minimum_alpha_score=0,
            positive_operating_cash_flow_only=False,
        ),
        technical_histories={},
        reference_date=date(2026, 7, 18),
    )

    assert summary.matched_count == 1
    assert summary.rows[0].technical_score is None
    assert summary.rows[0].technical_status == "Kayıt yok"
    assert summary.rows[0].combined_decision_ready is False


def test_scanner_combined_readiness_requires_current_technical_record():
    current = _company("CURRENT", 25, 30, 0.4, 100)
    stale = _company("STALE", 25, 30, 0.4, 100)
    summary = scan_companies(
        [current, stale],
        ScannerFilters(
            minimum_alpha_score=0,
            positive_operating_cash_flow_only=False,
            combined_decision_ready_only=True,
        ),
        technical_histories={
            "CURRENT": [
                _technical_history(
                    "CURRENT", 1, 75, date(2026, 7, 17)
                )
            ],
            "STALE": [
                _technical_history(
                    "STALE", 2, 80, date(2026, 7, 1)
                )
            ],
        },
        reference_date=date(2026, 7, 18),
    )

    assert [row.symbol for row in summary.rows] == ["CURRENT"]
    assert summary.rows[0].combined_decision_ready is True
    assert summary.combined_decision_ready_count == 1


def test_scanner_combined_readiness_requires_financial_confidence():
    company = _company("UNVERIFIED", 25, 30, 0.4, 100)
    summary = scan_companies(
        [company],
        ScannerFilters(
            minimum_alpha_score=0,
            positive_operating_cash_flow_only=False,
            combined_decision_ready_only=True,
        ),
        latest_audits={},
        technical_histories={
            "UNVERIFIED": [
                _technical_history(
                    "UNVERIFIED", 1, 75, date(2026, 7, 17)
                )
            ]
        },
        reference_date=date(2026, 7, 18),
    )

    assert summary.rows == []
    assert summary.combined_decision_ready_count == 0


def test_scanner_rejects_current_record_from_old_methodology():
    company = _company("LEGACY", 25, 30, 0.4, 100)
    summary = scan_companies(
        [company],
        ScannerFilters(
            minimum_alpha_score=0,
            positive_operating_cash_flow_only=False,
            current_technical_only=True,
        ),
        technical_histories={
            "LEGACY": [
                _technical_history(
                    "LEGACY",
                    1,
                    90,
                    date(2026, 7, 17),
                    methodology_version="technical-legacy",
                )
            ]
        },
        reference_date=date(2026, 7, 18),
    )

    assert summary.rows == []
    assert summary.current_technical_count == 0


def test_scanner_strengthening_skips_invalid_intermediate_record():
    company = _company("RISING", 25, 30, 0.4, 100)
    invalid_middle = _technical_history(
        "RISING",
        2,
        95,
        date(2026, 7, 16),
    ).model_copy(
        update={
            "score_breakdown": {
                **_score_breakdown(95),
                "trend": 0,
            }
        }
    )
    summary = scan_companies(
        [company],
        ScannerFilters(
            minimum_alpha_score=0,
            positive_operating_cash_flow_only=False,
            technical_strengthening_only=True,
        ),
        technical_histories={
            "RISING": [
                _technical_history(
                    "RISING", 1, 60, date(2026, 7, 15)
                ),
                invalid_middle,
                _technical_history(
                    "RISING", 3, 70, date(2026, 7, 17)
                ),
            ]
        },
        reference_date=date(2026, 7, 18),
    )

    assert [row.symbol for row in summary.rows] == ["RISING"]
    assert summary.rows[0].technical_delta == 10
