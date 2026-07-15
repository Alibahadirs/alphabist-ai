import pytest
from pydantic import ValidationError

from app.audit.models import CompanyDataAudit, DataSourceType, MetricSourceType
from app.audit.service import build_pdf_field_sources
from app.database import repository
from app.parser.models import (
    ActivityReportExtractionResult,
    CompanyMetadata,
    FinancialReportDraft,
    PdfExtractionResult,
)
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


def _audit(symbol: str, score: float, source: DataSourceType) -> CompanyDataAudit:
    return CompanyDataAudit(
        symbol=symbol,
        source_type=source,
        company_profile=CompanyProfile.STANDARD,
        period_months=3,
        financial_report_name="financial.pdf",
        activity_report_name="activity.pdf",
        completeness=92.5,
        alpha_score=score,
        field_sources={
            "revenue_growth": MetricSourceType.FINANCIAL_REPORT,
            "risk_score_input": MetricSourceType.MANUAL,
        },
    )


def test_audit_repository_returns_latest_record(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.upsert_company(
        FinancialMetrics(symbol="AKSA", company_name="Aksa Akrilik")
    )

    repository.add_company_data_audit(
        _audit("AKSA", 78.0, DataSourceType.PDF)
    )
    repository.add_company_data_audit(
        _audit("AKSA", 84.0, DataSourceType.CORRECTION)
    )

    latest = repository.get_latest_company_data_audit("aksa")
    assert latest is not None
    assert latest.alpha_score == 84.0
    assert latest.source_type == DataSourceType.CORRECTION
    assert latest.financial_report_name == "financial.pdf"
    assert (
        latest.field_sources["revenue_growth"]
        == MetricSourceType.FINANCIAL_REPORT
    )
    assert latest.field_sources["risk_score_input"] == MetricSourceType.MANUAL

    audits = repository.list_latest_company_data_audits()
    assert len(audits) == 1
    assert audits[0].id == latest.id

    history = repository.list_company_data_audits("AKSA")
    assert [item.alpha_score for item in history] == [78.0, 84.0]


def test_audit_period_must_be_valid():
    with pytest.raises(ValidationError):
        CompanyDataAudit(
            symbol="AKSA",
            source_type=DataSourceType.PDF,
            company_profile=CompanyProfile.STANDARD,
            period_months=13,
            completeness=100,
            alpha_score=80,
        )


def test_init_db_migrates_existing_audit_table(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "legacy.db")
    with repository.connect() as conn:
        conn.execute(
            """CREATE TABLE company_data_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            source_type TEXT NOT NULL,
            company_profile TEXT NOT NULL,
            period_months INTEGER,
            financial_report_name TEXT NOT NULL DEFAULT '',
            activity_report_name TEXT NOT NULL DEFAULT '',
            completeness REAL NOT NULL,
            alpha_score REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
        )

    repository.init_db()

    with repository.connect() as conn:
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(company_data_audit)"
            ).fetchall()
        }
    assert "field_sources" in columns


def test_pdf_field_sources_distinguish_reports_and_user_changes():
    financial_result = PdfExtractionResult(
        draft=FinancialReportDraft(),
        page_count=10,
        extracted_fields=["revenue", "previous_revenue"],
    )
    activity_result = ActivityReportExtractionResult(
        metadata=CompanyMetadata(),
        page_count=5,
        sector_metrics={"capital_adequacy_ratio": 18.5},
    )
    defaults = FinancialMetrics(
        symbol="TEST",
        company_name="Test",
        revenue_growth=20,
        capital_adequacy_ratio=18.5,
        risk_score_input=50,
    )

    sources = build_pdf_field_sources(
        financial_result,
        activity_result,
        defaults,
        {
            "revenue_growth": 20,
            "capital_adequacy_ratio": 18.5,
            "risk_score_input": 50,
        },
    )
    changed_sources = build_pdf_field_sources(
        financial_result,
        activity_result,
        defaults,
        {"revenue_growth": 25},
    )

    assert sources["revenue_growth"] == MetricSourceType.FINANCIAL_REPORT
    assert (
        sources["capital_adequacy_ratio"]
        == MetricSourceType.ACTIVITY_REPORT
    )
    assert sources["risk_score_input"] == MetricSourceType.MANUAL
    assert changed_sources["revenue_growth"] == MetricSourceType.MANUAL
