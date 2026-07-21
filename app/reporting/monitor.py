import hashlib
import json

from app.reporting.models import (
    CompanyInvestmentReport,
    CompanyReportTrendMonitor,
    CompanyReportTrendMonitorFilters,
    CompanyReportTrendMonitorRow,
    CompanyReportTrendSummary,
    ReportTrendAlertSeverity,
)
from app.reporting.trend import build_company_report_trend


_SEVERITY_RANK = {
    ReportTrendAlertSeverity.INFO: 0,
    ReportTrendAlertSeverity.WARNING: 1,
    ReportTrendAlertSeverity.CRITICAL: 2,
}


def report_trend_task_id(symbol: str) -> str:
    return f"report-trend:{symbol.upper().strip()}"


def report_trend_issue_fingerprint(
    trend: CompanyReportTrendSummary,
) -> str:
    payload = {
        "symbol": trend.symbol.upper().strip(),
        "latest_fingerprint": trend.latest_fingerprint,
        "trend_label": trend.trend_label,
        "alpha_delta": trend.alpha_delta,
        "combined_delta": trend.combined_delta,
        "alerts": [
            {
                "code": alert.code,
                "severity": alert.severity.value,
                "message": alert.message,
            }
            for alert in trend.alerts
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _priority_score(
    severity: ReportTrendAlertSeverity,
    trend_label: str,
    alpha_delta: float | None,
    decision_ready: bool,
) -> float:
    score = {
        ReportTrendAlertSeverity.INFO: 5,
        ReportTrendAlertSeverity.WARNING: 35,
        ReportTrendAlertSeverity.CRITICAL: 65,
    }[severity]
    if trend_label == "Zayıflıyor":
        score += 15
    if not decision_ready:
        score += 15
    if alpha_delta is not None and alpha_delta < 0:
        score += min(abs(alpha_delta), 15)
    return round(min(score, 100), 2)


def build_company_report_trend_monitor(
    reports_by_symbol: dict[str, list[CompanyInvestmentReport]],
) -> CompanyReportTrendMonitor:
    rows: list[CompanyReportTrendMonitorRow] = []
    for reports in reports_by_symbol.values():
        if not reports:
            continue
        trend = build_company_report_trend(reports)
        latest = max(reports, key=lambda report: report.generated_at)
        severity = max(
            (alert.severity for alert in trend.alerts),
            key=_SEVERITY_RANK.get,
            default=ReportTrendAlertSeverity.INFO,
        )
        primary_alert = next(
            (
                alert.message
                for alert in trend.alerts
                if alert.severity == severity
            ),
            "Belirgin rapor geçmişi uyarısı bulunmuyor.",
        )
        rows.append(
            CompanyReportTrendMonitorRow(
                task_id=report_trend_task_id(latest.symbol),
                issue_fingerprint=report_trend_issue_fingerprint(trend),
                symbol=latest.symbol,
                company_name=latest.company_name,
                company_profile=latest.company_profile,
                report_count=trend.report_count,
                latest_generated_at=latest.generated_at,
                latest_report_period_end=latest.report_period_end,
                latest_alpha_score=latest.alpha_score,
                trend_label=trend.trend_label,
                alpha_delta=trend.alpha_delta,
                combined_delta=trend.combined_delta,
                decision_ready=latest.decision_ready,
                alert_severity=severity,
                alert_count=sum(
                    alert.severity != ReportTrendAlertSeverity.INFO
                    for alert in trend.alerts
                ),
                primary_alert=primary_alert,
                priority_score=_priority_score(
                    severity,
                    trend.trend_label,
                    trend.alpha_delta,
                    latest.decision_ready,
                ),
            )
        )

    rows.sort(key=lambda row: (-row.priority_score, row.symbol))
    return CompanyReportTrendMonitor(
        rows=rows,
        company_count=len(rows),
        critical_count=sum(
            row.alert_severity == ReportTrendAlertSeverity.CRITICAL
            for row in rows
        ),
        warning_count=sum(
            row.alert_severity == ReportTrendAlertSeverity.WARNING
            for row in rows
        ),
        weakening_count=sum(
            row.trend_label == "Zayıflıyor" for row in rows
        ),
    )


def filter_company_report_trend_monitor(
    monitor: CompanyReportTrendMonitor,
    filters: CompanyReportTrendMonitorFilters,
) -> CompanyReportTrendMonitor:
    search = filters.search.casefold().strip()
    rows = [
        row
        for row in monitor.rows
        if (
            not search
            or search in row.symbol.casefold()
            or search in row.company_name.casefold()
        )
        and (
            not filters.severities
            or row.alert_severity in filters.severities
        )
        and (
            not filters.trend_labels
            or row.trend_label in filters.trend_labels
        )
        and (
            not filters.company_profiles
            or row.company_profile in filters.company_profiles
        )
        and row.priority_score >= filters.minimum_priority
        and (not filters.decision_blocked_only or not row.decision_ready)
    ]
    return CompanyReportTrendMonitor(
        rows=rows,
        company_count=len(rows),
        critical_count=sum(
            row.alert_severity == ReportTrendAlertSeverity.CRITICAL
            for row in rows
        ),
        warning_count=sum(
            row.alert_severity == ReportTrendAlertSeverity.WARNING
            for row in rows
        ),
        weakening_count=sum(
            row.trend_label == "Zayıflıyor" for row in rows
        ),
    )
