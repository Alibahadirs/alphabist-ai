from datetime import datetime, timezone

import pytest

from app.reporting.company_report import (
    company_report_fingerprint,
    compare_company_reports,
)
from app.reporting.models import CompanyInvestmentReport
from app.sector.profiles import CompanyProfile


def _report(
    *,
    symbol: str = "TEST",
    generated_at: datetime,
    alpha_score: float = 80,
    combined_decision: str = "İzle",
) -> CompanyInvestmentReport:
    report = CompanyInvestmentReport(
        symbol=symbol,
        company_name="Test A.Ş.",
        company_profile=CompanyProfile.STANDARD,
        generated_at=generated_at,
        alpha_score=alpha_score,
        alpha_grade="A",
        alpha_decision="Al",
        confidence_score=90,
        confidence_status="Yüksek",
        decision_ready=True,
        combined_score=75,
        combined_decision=combined_decision,
        summary="Özet",
        category_scores={"profitability": alpha_score / 10},
        scoring_methodology_version="alpha-2026.4",
        technical_methodology_version="technical-2026.1",
    )
    return report.model_copy(
        update={"report_fingerprint": company_report_fingerprint(report)}
    )


def test_company_report_comparison_orders_reports_and_calculates_deltas():
    older = _report(
        generated_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
        alpha_score=80,
    )
    newer = _report(
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        alpha_score=84,
        combined_decision="Al adayı",
    )

    comparison = compare_company_reports(newer, older)

    assert comparison.previous_fingerprint == older.report_fingerprint
    assert comparison.current_fingerprint == newer.report_fingerprint
    assert comparison.changed is True
    alpha_change = next(
        change
        for change in comparison.changes
        if change.field == "alpha_score"
    )
    assert alpha_change.numeric_delta == 4
    assert any(
        change.field == "combined_decision"
        for change in comparison.changes
    )


def test_company_report_comparison_rejects_different_companies():
    first = _report(
        generated_at=datetime(2026, 7, 19, tzinfo=timezone.utc)
    )
    second = _report(
        symbol="OTHER",
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="aynı şirkete"):
        compare_company_reports(first, second)


def test_company_report_comparison_rejects_tampered_report():
    first = _report(
        generated_at=datetime(2026, 7, 19, tzinfo=timezone.utc)
    )
    second = _report(
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc)
    ).model_copy(update={"alpha_score": 5})

    with pytest.raises(ValueError, match="parmak izi"):
        compare_company_reports(first, second)


def test_company_report_comparison_can_be_unchanged():
    first = _report(
        generated_at=datetime(2026, 7, 19, tzinfo=timezone.utc)
    )
    second = _report(
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc)
    )

    comparison = compare_company_reports(first, second)

    assert comparison.changed is False
    assert comparison.changes == []
