from datetime import date, datetime, timezone

from app.reporting.company_report import company_report_fingerprint
from app.reporting.models import (
    CompanyInvestmentReport,
    ReportTrendAlertSeverity,
)
from app.reporting.monitor import build_company_report_trend_monitor
from app.sector.profiles import CompanyProfile


def _report(
    symbol: str,
    day: int,
    *,
    alpha: float,
    decision_ready: bool = True,
) -> CompanyInvestmentReport:
    report = CompanyInvestmentReport(
        symbol=symbol,
        company_name=f"{symbol} A.Ş.",
        company_profile=CompanyProfile.STANDARD,
        generated_at=datetime(2026, 7, day, tzinfo=timezone.utc),
        report_period_end=date(2026, 6, 30),
        alpha_score=alpha,
        alpha_grade="A",
        alpha_decision="Al",
        confidence_score=90,
        confidence_status="Yüksek",
        decision_ready=decision_ready,
        technical_score=75,
        technical_price_date=date(2026, 7, day),
        combined_score=alpha,
        combined_decision="Al adayı",
        summary="Özet",
        scoring_methodology_version="alpha-2026.4",
        technical_methodology_version="technical-2026.1",
    )
    return report.model_copy(
        update={"report_fingerprint": company_report_fingerprint(report)}
    )


def test_company_report_monitor_prioritizes_critical_company():
    monitor = build_company_report_trend_monitor(
        {
            "AAA": [_report("AAA", 19, alpha=80), _report("AAA", 20, alpha=82)],
            "BBB": [
                _report("BBB", 19, alpha=80),
                _report("BBB", 20, alpha=70, decision_ready=False),
            ],
        }
    )

    assert monitor.company_count == 2
    assert monitor.critical_count == 1
    assert monitor.rows[0].symbol == "BBB"
    assert monitor.rows[0].alert_severity == ReportTrendAlertSeverity.CRITICAL
    assert monitor.rows[0].priority_score > monitor.rows[1].priority_score


def test_company_report_monitor_counts_weakening_companies():
    monitor = build_company_report_trend_monitor(
        {
            "AAA": [_report("AAA", 19, alpha=80), _report("AAA", 20, alpha=72)],
            "BBB": [_report("BBB", 20, alpha=80)],
        }
    )

    assert monitor.weakening_count == 1
    assert monitor.warning_count == 1
    assert monitor.rows[0].symbol == "AAA"


def test_company_report_monitor_issue_identity_is_stable_until_change():
    reports = {
        "AAA": [_report("AAA", 19, alpha=80), _report("AAA", 20, alpha=72)]
    }

    first = build_company_report_trend_monitor(reports).rows[0]
    second = build_company_report_trend_monitor(reports).rows[0]
    changed = build_company_report_trend_monitor(
        {
            "AAA": [
                _report("AAA", 19, alpha=80),
                _report("AAA", 21, alpha=68),
            ]
        }
    ).rows[0]

    assert first.task_id == "report-trend:AAA"
    assert first.task_id == changed.task_id
    assert first.issue_fingerprint == second.issue_fingerprint
    assert first.issue_fingerprint != changed.issue_fingerprint
