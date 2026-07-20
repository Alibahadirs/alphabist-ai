from datetime import date, datetime, timezone

from app.audit.models import CompanyDataAudit, DataSourceType
from app.confidence.models import AnalysisConfidence
from app.reporting.company_report import (
    build_company_investment_report,
    company_report_fingerprint,
    render_company_report_markdown,
    serialize_company_report_markdown,
)
from app.reporting.models import CompanyInvestmentReport
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile
from app.technical.models import TechnicalQualityRow


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


def _confidence(ready: bool = True) -> AnalysisConfidence:
    return AnalysisConfidence(
        total=90 if ready else 55,
        status="Yüksek" if ready else "Düşük",
        decision="Al" if ready else "Doğrula / Karar verme",
        decision_ready=ready,
        completeness_component=50,
        source_component=20,
        report_component=10,
        period_component=5,
        validation_component=5 if ready else 0,
        reasons=[] if ready else ["Finansal doğrulama eksik."],
    )


def test_company_report_combines_only_verified_technical_score():
    company = FinancialMetrics(
        symbol="TEST",
        company_name="Test A.Ş.",
        revenue_growth=20,
        net_profit_growth=25,
        net_margin=12,
        roe=22,
        debt_to_equity=0.6,
        current_ratio=1.8,
        operating_cash_flow=100,
        free_cash_flow=50,
        asset_turnover=0.8,
    )
    score = calculate_alpha_score(company)
    audit = CompanyDataAudit(
        symbol="TEST",
        source_type=DataSourceType.PDF,
        company_profile=CompanyProfile.STANDARD,
        report_period_end=date(2026, 6, 30),
        completeness=100,
        alpha_score=score.total,
        methodology_version="alpha-2026.4",
    )
    technical = TechnicalQualityRow(
        symbol="TEST",
        technical_score=80,
        signal="Al",
        price_date=date(2026, 7, 20),
        status="Güncel günlük veri",
        current=True,
    )

    report = build_company_investment_report(
        company,
        score,
        _confidence(),
        audit,
        technical,
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )

    assert report.report_period_end == date(2026, 6, 30)
    assert report.technical_score == 80
    assert report.combined_score is not None
    assert report.combined_decision != "Doğrulama gerekli"
    assert report.category_scores["profitability"] == score.profitability


def test_company_report_blocks_combined_decision_when_financial_not_ready():
    company = FinancialMetrics(symbol="BANK", company_name="Test Bankası")
    score = calculate_alpha_score(company)
    technical = TechnicalQualityRow(
        symbol="BANK",
        technical_score=90,
        signal="Güçlü Al",
        price_date=date(2026, 7, 20),
        status="Güncel günlük veri",
        current=True,
    )

    report = build_company_investment_report(
        company,
        score,
        _confidence(False),
        None,
        technical,
    )

    assert report.combined_score is None
    assert report.combined_decision == "Finansal doğrulama gerekli"
    assert "audit kaydı bulunmuyor" in " ".join(
        report.data_quality_notes
    )


def test_company_report_markdown_formats_units_and_missing_values():
    company = FinancialMetrics(
        symbol="TEST",
        company_name="Test A.Ş.",
        revenue_growth=18.5,
        current_ratio=1.25,
    )
    score = calculate_alpha_score(company)
    report = build_company_investment_report(
        company,
        score,
        _confidence(False),
        None,
        None,
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )

    markdown = render_company_report_markdown(report)
    payload = serialize_company_report_markdown(report)

    assert "# TEST - Test A.Ş." in markdown
    assert "%18,50" in markdown
    assert "1,25x" in markdown
    assert "| Teknik puan | - |" in markdown
    assert "| Birleşik puan | - |" in markdown
    assert "yatırım tavsiyesi değildir" in markdown
    assert payload.startswith(b"\xef\xbb\xbf")


def test_company_report_fingerprint_ignores_generation_time():
    company = FinancialMetrics(symbol="TEST", company_name="Test A.Ş.")
    score = calculate_alpha_score(company)
    first = build_company_investment_report(
        company,
        score,
        _confidence(False),
        None,
        None,
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )
    second = build_company_investment_report(
        company,
        score,
        _confidence(False),
        None,
        None,
        generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )

    assert first.report_fingerprint == second.report_fingerprint
    assert first.report_fingerprint == company_report_fingerprint(first)


def test_company_report_fingerprint_changes_with_report_content():
    company = FinancialMetrics(symbol="TEST", company_name="Test A.Ş.")
    score = calculate_alpha_score(company)
    report = build_company_investment_report(
        company,
        score,
        _confidence(False),
        None,
        None,
    )
    changed = report.model_copy(
        update={"alpha_score": report.alpha_score + 1}
    )

    assert company_report_fingerprint(report) != company_report_fingerprint(
        changed
    )
