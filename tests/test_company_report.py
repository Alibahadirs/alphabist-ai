from datetime import datetime, timezone

from app.reporting.models import CompanyInvestmentReport
from app.sector.profiles import CompanyProfile


def test_company_investment_report_keeps_missing_technical_data_explicit():
    report = CompanyInvestmentReport(
        symbol="TEST",
        company_name="Test A.Ş.",
        company_profile=CompanyProfile.STANDARD,
        generated_at=datetime.now(timezone.utc),
        alpha_score=82,
        alpha_grade="A",
        alpha_decision="Al",
        confidence_score=90,
        confidence_status="Yüksek",
        decision_ready=True,
        combined_decision="Teknik doğrulama gerekli",
        summary="Özet",
        scoring_methodology_version="alpha-2026.4",
        technical_methodology_version="technical-2026.1",
    )

    assert report.technical_score is None
    assert report.combined_score is None
    assert report.technical_signal is None
