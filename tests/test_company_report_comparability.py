from datetime import date, datetime, timezone

from app.reporting.comparability import (
    assess_company_report_comparability,
)
from app.reporting.company_report import company_report_fingerprint
from app.reporting.models import CompanyInvestmentReport
from app.sector.profiles import CompanyProfile


def _report(
    generated_at: datetime,
    *,
    period: date = date(2026, 6, 30),
    scoring_version: str = "alpha-2026.4",
    technical_version: str = "technical-2026.1",
    profile: CompanyProfile = CompanyProfile.STANDARD,
    technical_date: date = date(2026, 7, 20),
) -> CompanyInvestmentReport:
    report = CompanyInvestmentReport(
        symbol="TEST",
        company_name="Test A.Ş.",
        company_profile=profile,
        generated_at=generated_at,
        report_period_end=period,
        alpha_score=80,
        alpha_grade="A",
        alpha_decision="Al",
        confidence_score=90,
        confidence_status="Yüksek",
        decision_ready=True,
        technical_score=75,
        technical_price_date=technical_date,
        combined_score=78,
        combined_decision="Al adayı",
        summary="Özet",
        scoring_methodology_version=scoring_version,
        technical_methodology_version=technical_version,
    )
    return report.model_copy(
        update={"report_fingerprint": company_report_fingerprint(report)}
    )


def test_company_report_comparability_accepts_aligned_reports():
    previous = _report(datetime(2026, 7, 19, tzinfo=timezone.utc))
    current = _report(
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        period=date(2026, 9, 30),
        technical_date=date(2026, 7, 21),
    )

    result = assess_company_report_comparability(previous, current)

    assert result.financial_comparable is True
    assert result.technical_comparable is True
    assert result.combined_comparable is True
    assert result.notes == []


def test_company_report_comparability_blocks_methodology_change():
    previous = _report(datetime(2026, 7, 19, tzinfo=timezone.utc))
    current = _report(
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        scoring_version="alpha-2027.1",
    )

    result = assess_company_report_comparability(previous, current)

    assert result.financial_comparable is False
    assert result.combined_comparable is False
    assert "Temel analiz metodolojileri farklı." in result.notes


def test_company_report_comparability_detects_period_regression():
    previous = _report(
        datetime(2026, 7, 19, tzinfo=timezone.utc),
        period=date(2026, 9, 30),
    )
    current = _report(
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        period=date(2026, 6, 30),
    )

    result = assess_company_report_comparability(previous, current)

    assert result.financial_comparable is False
    assert "Finansal rapor dönemi geriye gidiyor." in result.notes
