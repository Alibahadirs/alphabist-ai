import csv
import io
from datetime import datetime, timezone

from app.reporting.models import (
    CompanyReportTrendMonitor,
    CompanyReportTrendMonitorFilters,
    CompanyReportTrendMonitorRow,
    CompanyReportTrendReviewState,
    ReportTrendAlertSeverity,
    ReportTrendReviewStatus,
)
from app.reporting.monitor import (
    apply_report_trend_review_states,
    filter_company_report_trend_monitor,
)
from app.reporting.monitor_export import (
    serialize_company_report_trend_monitor_csv,
)
from app.sector.profiles import CompanyProfile


def _row(
    symbol: str,
    *,
    severity: ReportTrendAlertSeverity,
    trend: str,
    priority: float,
    decision_ready: bool = True,
) -> CompanyReportTrendMonitorRow:
    return CompanyReportTrendMonitorRow(
        task_id=f"report-trend:{symbol}",
        issue_fingerprint=(symbol[0].lower() * 64),
        symbol=symbol,
        company_name=f"{symbol} Şirketi",
        company_profile=CompanyProfile.STANDARD,
        report_count=2,
        latest_generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        latest_alpha_score=75,
        trend_label=trend,
        decision_ready=decision_ready,
        alert_severity=severity,
        alert_count=1,
        primary_alert="Kontrol gerekli.",
        priority_score=priority,
    )


def _monitor() -> CompanyReportTrendMonitor:
    rows = [
        _row(
            "AAA",
            severity=ReportTrendAlertSeverity.WARNING,
            trend="Zayıflıyor",
            priority=60,
        ),
        _row(
            "BBB",
            severity=ReportTrendAlertSeverity.CRITICAL,
            trend="Karşılaştırma gerekli",
            priority=85,
            decision_ready=False,
        ),
    ]
    return CompanyReportTrendMonitor(
        rows=rows,
        company_count=2,
        critical_count=1,
        warning_count=1,
        weakening_count=1,
    )


def test_company_report_monitor_filters_combined_conditions():
    filtered = filter_company_report_trend_monitor(
        _monitor(),
        CompanyReportTrendMonitorFilters(
            severities=[ReportTrendAlertSeverity.CRITICAL],
            minimum_priority=80,
            decision_blocked_only=True,
        ),
    )

    assert filtered.company_count == 1
    assert filtered.rows[0].symbol == "BBB"
    assert filtered.critical_count == 1
    assert filtered.warning_count == 0


def test_company_report_monitor_csv_exports_filtered_rows():
    filtered = filter_company_report_trend_monitor(
        _monitor(),
        CompanyReportTrendMonitorFilters(search="aaa"),
    )

    payload = serialize_company_report_trend_monitor_csv(filtered)
    rows = list(
        csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    )

    assert payload.startswith(b"\xef\xbb\xbf")
    assert len(rows) == 1
    assert rows[0]["Hisse"] == "AAA"
    assert rows[0]["Önem"] == "Uyarı"


def test_company_report_monitor_reopens_changed_closed_issue():
    monitor = _monitor()
    state = CompanyReportTrendReviewState(
        task_id="report-trend:AAA",
        symbol="AAA",
        status=ReportTrendReviewStatus.RESOLVED,
        note="Önceki sorun çözüldü",
        issue_fingerprint="f" * 64,
    )

    enriched = apply_report_trend_review_states(monitor, [state])
    row = next(row for row in enriched.rows if row.symbol == "AAA")

    assert row.review_status == ReportTrendReviewStatus.REOPEN_REQUIRED
    assert row.review_needs_reopen is True
    assert enriched.reopen_required_count == 1


def test_company_report_monitor_filters_review_status():
    state = CompanyReportTrendReviewState(
        task_id="report-trend:AAA",
        symbol="AAA",
        status=ReportTrendReviewStatus.IN_REVIEW,
        note="İnceleniyor",
        issue_fingerprint="a" * 64,
    )
    enriched = apply_report_trend_review_states(_monitor(), [state])

    filtered = filter_company_report_trend_monitor(
        enriched,
        CompanyReportTrendMonitorFilters(
            review_statuses=[ReportTrendReviewStatus.IN_REVIEW]
        ),
    )

    assert filtered.company_count == 1
    assert filtered.rows[0].symbol == "AAA"
