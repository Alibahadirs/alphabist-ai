from app.reporting.models import (
    CompanyInvestmentReport,
    CompanyReportTrendMonitor,
    CompanyReportTrendMonitorRow,
    ReportTrendAlertSeverity,
)
from app.reporting.trend import build_company_report_trend


_SEVERITY_RANK = {
    ReportTrendAlertSeverity.INFO: 0,
    ReportTrendAlertSeverity.WARNING: 1,
    ReportTrendAlertSeverity.CRITICAL: 2,
}


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
