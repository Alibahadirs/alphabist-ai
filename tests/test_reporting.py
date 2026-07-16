from datetime import date, timedelta

from app.reporting.models import ReportFreshnessStatus
from app.reporting.service import assess_report_period, report_period_regresses


def test_current_quarter_end_gets_full_confidence():
    assessment = assess_report_period(
        date(2026, 3, 31),
        3,
        as_of=date(2026, 7, 16),
    )

    assert assessment.status == ReportFreshnessStatus.CURRENT
    assert assessment.age_days == 107
    assert assessment.confidence_points == 5
    assert assessment.blocks_decision is False


def test_aging_report_loses_period_confidence_without_blocking():
    report_period_end = date(2026, 3, 31)
    assessment = assess_report_period(
        report_period_end,
        3,
        as_of=report_period_end + timedelta(days=181),
    )

    assert assessment.status == ReportFreshnessStatus.AGING
    assert assessment.confidence_points == 2.5
    assert assessment.blocks_decision is False


def test_stale_report_blocks_investment_decision():
    assessment = assess_report_period(
        date(2025, 12, 31),
        12,
        as_of=date(2026, 10, 1),
    )

    assert assessment.status == ReportFreshnessStatus.STALE
    assert assessment.blocks_decision is True


def test_future_and_mismatched_periods_are_invalid():
    future = assess_report_period(
        date(2026, 9, 30),
        9,
        as_of=date(2026, 7, 16),
    )
    mismatch = assess_report_period(
        date(2026, 6, 30),
        3,
        as_of=date(2026, 7, 16),
    )

    assert future.status == ReportFreshnessStatus.FUTURE
    assert future.blocks_decision is True
    assert mismatch.status == ReportFreshnessStatus.INVALID
    assert mismatch.blocks_decision is True


def test_period_sequence_only_rejects_older_reports():
    latest = date(2026, 6, 30)

    assert report_period_regresses(date(2026, 3, 31), latest) is True
    assert report_period_regresses(date(2026, 6, 30), latest) is False
    assert report_period_regresses(date(2026, 9, 30), latest) is False
    assert report_period_regresses(None, latest) is False
