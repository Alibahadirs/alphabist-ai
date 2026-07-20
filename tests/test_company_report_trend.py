from datetime import date, datetime, timezone

from app.reporting.company_report import company_report_fingerprint
from app.reporting.models import (
    CompanyInvestmentReport,
    ReportTrendAlertSeverity,
)
from app.reporting.trend import build_company_report_trend
from app.sector.profiles import CompanyProfile


def _report(
    generated_at: datetime,
    *,
    alpha: float = 80,
    confidence: float = 90,
    technical: float = 75,
    combined: float = 78,
    scoring_version: str = "alpha-2026.4",
    decision_ready: bool = True,
) -> CompanyInvestmentReport:
    report = CompanyInvestmentReport(
        symbol="TEST",
        company_name="Test A.Ş.",
        company_profile=CompanyProfile.STANDARD,
        generated_at=generated_at,
        report_period_end=date(2026, 6, 30),
        alpha_score=alpha,
        alpha_grade="A",
        alpha_decision="Al",
        confidence_score=confidence,
        confidence_status="Yüksek",
        decision_ready=decision_ready,
        technical_score=technical,
        technical_price_date=date(2026, 7, 20),
        combined_score=combined,
        combined_decision="Al adayı",
        summary="Özet",
        category_scores={"profitability": alpha / 10},
        scoring_methodology_version=scoring_version,
        technical_methodology_version="technical-2026.1",
    )
    return report.model_copy(
        update={"report_fingerprint": company_report_fingerprint(report)}
    )


def test_company_report_trend_calculates_comparable_deltas():
    previous = _report(
        datetime(2026, 7, 19, tzinfo=timezone.utc),
        alpha=80,
        combined=78,
    )
    current = _report(
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        alpha=85,
        combined=84,
    )

    trend = build_company_report_trend([current, previous])

    assert trend.alpha_delta == 5
    assert trend.combined_delta == 6
    assert trend.category_deltas["profitability"] == 0.5
    assert trend.trend_label == "Güçleniyor"


def test_company_report_trend_warns_on_material_decline():
    previous = _report(datetime(2026, 7, 19, tzinfo=timezone.utc))
    current = _report(
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        alpha=72,
        confidence=75,
        technical=60,
        combined=65,
    )

    trend = build_company_report_trend([previous, current])

    assert trend.trend_label == "Zayıflıyor"
    codes = {alert.code for alert in trend.alerts}
    assert {"alpha_drop", "confidence_drop", "technical_drop"} <= codes


def test_company_report_trend_does_not_compare_changed_methodology():
    previous = _report(datetime(2026, 7, 19, tzinfo=timezone.utc))
    current = _report(
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        alpha=10,
        scoring_version="alpha-2027.1",
    )

    trend = build_company_report_trend([previous, current])

    assert trend.alpha_delta is None
    assert trend.combined_delta is None
    assert trend.trend_label == "Karşılaştırma gerekli"
    assert any(alert.code == "comparison_blocked" for alert in trend.alerts)


def test_company_report_trend_marks_blocked_latest_decision_critical():
    report = _report(
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        decision_ready=False,
    )

    trend = build_company_report_trend([report])

    assert trend.trend_label == "Geçmiş yetersiz"
    assert any(
        alert.severity == ReportTrendAlertSeverity.CRITICAL
        for alert in trend.alerts
    )
