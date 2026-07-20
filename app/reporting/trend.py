from app.reporting.comparability import (
    assess_company_report_comparability,
)
from app.reporting.company_report import company_report_fingerprint
from app.reporting.models import (
    CompanyInvestmentReport,
    CompanyReportTrendAlert,
    CompanyReportTrendSummary,
    ReportTrendAlertSeverity,
)


def _delta(previous: float, current: float) -> float:
    return round(current - previous, 2)


def build_company_report_trend(
    reports: list[CompanyInvestmentReport],
) -> CompanyReportTrendSummary:
    if not reports:
        raise ValueError("Trend analizi için en az bir rapor gerekli.")
    normalized_symbol = reports[0].symbol.upper().strip()
    for report in reports:
        if report.symbol.upper().strip() != normalized_symbol:
            raise ValueError("Trend analizi yalnızca tek bir şirket içerebilir.")
        if (
            not report.report_fingerprint
            or report.report_fingerprint
            != company_report_fingerprint(report)
        ):
            raise ValueError("Rapor içerik parmak izi doğrulanamadı.")

    ordered = sorted(reports, key=lambda report: report.generated_at)
    latest = ordered[-1]
    alerts: list[CompanyReportTrendAlert] = []
    if not latest.decision_ready:
        alerts.append(
            CompanyReportTrendAlert(
                code="decision_blocked",
                severity=ReportTrendAlertSeverity.CRITICAL,
                message=(
                    "En güncel rapor yatırım kararı üretmek için yeterince "
                    "doğrulanmış değil."
                ),
            )
        )
    if len(ordered) == 1:
        alerts.append(
            CompanyReportTrendAlert(
                code="history_missing",
                severity=ReportTrendAlertSeverity.INFO,
                message="Trend için en az iki rapor anlık görüntüsü gerekli.",
            )
        )
        return CompanyReportTrendSummary(
            symbol=latest.symbol,
            report_count=1,
            latest_fingerprint=latest.report_fingerprint,
            trend_label="Geçmiş yetersiz",
            alerts=alerts,
        )

    previous = ordered[-2]
    comparability = assess_company_report_comparability(previous, latest)
    alpha_delta = None
    confidence_delta = None
    technical_delta = None
    combined_delta = None
    category_deltas: dict[str, float] = {}

    if comparability.financial_comparable:
        alpha_delta = _delta(previous.alpha_score, latest.alpha_score)
        confidence_delta = _delta(
            previous.confidence_score,
            latest.confidence_score,
        )
        for category in sorted(
            set(previous.category_scores) & set(latest.category_scores)
        ):
            category_deltas[category] = _delta(
                previous.category_scores[category],
                latest.category_scores[category],
            )
    if comparability.technical_comparable:
        technical_delta = _delta(
            previous.technical_score or 0,
            latest.technical_score or 0,
        )
    if comparability.combined_comparable:
        combined_delta = _delta(
            previous.combined_score or 0,
            latest.combined_score or 0,
        )

    signal_delta = (
        combined_delta if combined_delta is not None else alpha_delta
    )
    if signal_delta is None:
        trend_label = "Karşılaştırma gerekli"
    elif signal_delta >= 3:
        trend_label = "Güçleniyor"
    elif signal_delta <= -3:
        trend_label = "Zayıflıyor"
    else:
        trend_label = "Yatay"

    for note in comparability.notes:
        alerts.append(
            CompanyReportTrendAlert(
                code="comparison_blocked",
                severity=ReportTrendAlertSeverity.WARNING,
                message=note,
            )
        )
    for code, value, threshold, message in (
        (
            "alpha_drop",
            alpha_delta,
            -5,
            "Alpha Score son karşılaştırılabilir rapora göre belirgin düştü.",
        ),
        (
            "confidence_drop",
            confidence_delta,
            -10,
            "Analiz güveni son karşılaştırılabilir rapora göre belirgin düştü.",
        ),
        (
            "technical_drop",
            technical_delta,
            -8,
            "Teknik puan son karşılaştırılabilir rapora göre belirgin düştü.",
        ),
        (
            "combined_drop",
            combined_delta,
            -5,
            "Birleşik puan son karşılaştırılabilir rapora göre belirgin düştü.",
        ),
    ):
        if value is not None and value <= threshold:
            alerts.append(
                CompanyReportTrendAlert(
                    code=code,
                    severity=ReportTrendAlertSeverity.WARNING,
                    message=message,
                )
            )
    if not alerts:
        alerts.append(
            CompanyReportTrendAlert(
                code="stable",
                severity=ReportTrendAlertSeverity.INFO,
                message="Belirgin bir rapor geçmişi uyarısı bulunmuyor.",
            )
        )

    return CompanyReportTrendSummary(
        symbol=latest.symbol,
        report_count=len(ordered),
        latest_fingerprint=latest.report_fingerprint,
        previous_fingerprint=previous.report_fingerprint,
        trend_label=trend_label,
        comparability=comparability,
        alpha_delta=alpha_delta,
        confidence_delta=confidence_delta,
        technical_delta=technical_delta,
        combined_delta=combined_delta,
        category_deltas=category_deltas,
        alerts=alerts,
    )
