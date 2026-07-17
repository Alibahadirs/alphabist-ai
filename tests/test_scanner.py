from app.scanner.models import ScannerFilters
from app.scanner.service import scan_companies
from app.scoring.models import FinancialMetrics


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
