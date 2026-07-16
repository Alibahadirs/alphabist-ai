from calendar import monthrange
from datetime import date

from app.reporting.models import ReportFreshnessStatus, ReportPeriodAssessment


VALID_PERIOD_MONTHS = (3, 6, 9, 12)


def report_period_regresses(
    report_period_end: date | None,
    latest_period_end: date | None,
) -> bool:
    return bool(
        report_period_end
        and latest_period_end
        and report_period_end < latest_period_end
    )


def assess_report_period(
    report_period_end: date | None,
    period_months: int | None,
    *,
    as_of: date | None = None,
) -> ReportPeriodAssessment:
    if report_period_end is None:
        return ReportPeriodAssessment(
            status=ReportFreshnessStatus.UNKNOWN,
            confidence_points=2.5 if period_months in VALID_PERIOD_MONTHS else 0,
            message="Rapor dönem sonu tarihi doğrulanmamış.",
        )

    if period_months not in VALID_PERIOD_MONTHS:
        return ReportPeriodAssessment(
            status=ReportFreshnessStatus.INVALID,
            confidence_points=0,
            blocks_decision=True,
            message="Raporun 3, 6, 9 veya 12 aylık dönemi seçilmemiş.",
        )

    expected_day = monthrange(report_period_end.year, report_period_end.month)[1]
    if (
        report_period_end.month not in VALID_PERIOD_MONTHS
        or report_period_end.day != expected_day
        or report_period_end.month != period_months
    ):
        return ReportPeriodAssessment(
            status=ReportFreshnessStatus.INVALID,
            confidence_points=0,
            blocks_decision=True,
            message=(
                "Rapor dönem sonu ile seçilen dönem uyuşmuyor. Tarih; 31 Mart, "
                "30 Haziran, 30 Eylül veya 31 Aralık olmalıdır."
            ),
        )

    age_days = ((as_of or date.today()) - report_period_end).days
    if age_days < 0:
        return ReportPeriodAssessment(
            status=ReportFreshnessStatus.FUTURE,
            age_days=age_days,
            confidence_points=0,
            blocks_decision=True,
            message="Rapor dönem sonu gelecekte olamaz.",
        )
    if age_days <= 180:
        return ReportPeriodAssessment(
            status=ReportFreshnessStatus.CURRENT,
            age_days=age_days,
            confidence_points=5,
            message=f"Rapor güncel: dönem sonundan bu yana {age_days} gün geçti.",
        )
    if age_days <= 270:
        return ReportPeriodAssessment(
            status=ReportFreshnessStatus.AGING,
            age_days=age_days,
            confidence_points=2.5,
            message=f"Rapor eskimeye başladı: dönem sonundan bu yana {age_days} gün geçti.",
        )
    return ReportPeriodAssessment(
        status=ReportFreshnessStatus.STALE,
        age_days=age_days,
        confidence_points=0,
        blocks_decision=True,
        message=f"Rapor güncel değil: dönem sonundan bu yana {age_days} gün geçti.",
    )
