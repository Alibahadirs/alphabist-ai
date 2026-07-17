from datetime import date

import pytest
from pydantic import ValidationError

from app.audit.models import CompanyDataAudit, DataSourceType, MetricSourceType
from app.audit.service import (
    analysis_input_fingerprint,
    attach_analysis_snapshot,
    build_pdf_field_sources,
    compare_analysis_snapshots,
    document_fingerprint,
    document_identity_conflicts,
    is_duplicate_analysis,
)
from app.confidence.models import AnalysisConfidence
from app.core.settings import settings
from app.database import repository
from app.parser.models import (
    ActivityReportExtractionResult,
    CompanyMetadata,
    FinancialReportDraft,
    PdfExtractionResult,
)
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.sector.profiles import CompanyProfile


def _audit(symbol: str, score: float, source: DataSourceType) -> CompanyDataAudit:
    return CompanyDataAudit(
        symbol=symbol,
        source_type=source,
        company_profile=CompanyProfile.STANDARD,
        period_months=3,
        report_period_end=date(2026, 3, 31),
        financial_report_name="financial.pdf",
        activity_report_name="activity.pdf",
        financial_report_hash="b" * 64,
        activity_report_hash="c" * 64,
        financial_report_scale=1_000,
        completeness=92.5,
        alpha_score=score,
        grade="A",
        decision="Al",
        confidence_score=90,
        confidence_status="Yüksek",
        methodology_version="test-methodology",
        input_fingerprint="a" * 64,
        score_breakdown={"profitability": 12.5},
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
    assert latest.financial_report_hash == "b" * 64
    assert latest.activity_report_hash == "c" * 64
    assert latest.financial_report_scale == 1_000
    assert latest.report_period_end == date(2026, 3, 31)
    assert (
        latest.field_sources["revenue_growth"]
        == MetricSourceType.FINANCIAL_REPORT
    )
    assert latest.field_sources["risk_score_input"] == MetricSourceType.MANUAL
    assert latest.confidence_score == 90
    assert latest.methodology_version == "test-methodology"
    assert latest.input_fingerprint == "a" * 64
    assert latest.score_breakdown["profitability"] == 12.5

    audits = repository.list_latest_company_data_audits()
    assert len(audits) == 1
    assert audits[0].id == latest.id

    history = repository.list_company_data_audits("AKSA")
    assert [item.alpha_score for item in history] == [78.0, 84.0]
    usages = repository.list_document_usages("b" * 64)
    assert [item.alpha_score for item in usages] == [84.0, 78.0]


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


def test_audit_rejects_invalid_document_fingerprint():
    values = _audit("AKSA", 80, DataSourceType.PDF).model_dump()
    values["financial_report_hash"] = "not-a-sha256"
    with pytest.raises(ValidationError):
        CompanyDataAudit.model_validate(values)


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
        indexes = {
            row[1]
            for row in conn.execute(
                "PRAGMA index_list(company_data_audit)"
            ).fetchall()
        }
    assert {
        "field_sources",
        "report_period_end",
        "grade",
        "decision",
        "confidence_score",
        "confidence_status",
        "methodology_version",
        "input_fingerprint",
        "score_breakdown",
        "financial_report_hash",
        "activity_report_hash",
        "financial_report_scale",
    }.issubset(columns)
    assert {
        "idx_company_data_audit_financial_hash",
        "idx_company_data_audit_activity_hash",
    }.issubset(indexes)


def test_document_fingerprint_identifies_file_content():
    first = document_fingerprint(b"financial report")
    second = document_fingerprint(b"financial report")
    changed = document_fingerprint(b"financial report changed")

    assert len(first) == 64
    assert first == second
    assert first != changed
    assert document_fingerprint(b"") == ""


def test_document_identity_rejects_cross_company_and_period_reuse():
    existing = _audit("AKSA", 80, DataSourceType.PDF)

    company_conflicts = document_identity_conflicts(
        [existing],
        symbol="GUBRF",
        report_period_end=date(2026, 3, 31),
        financial_report_hash="b" * 64,
    )
    period_conflicts = document_identity_conflicts(
        [existing],
        symbol="AKSA",
        report_period_end=date(2026, 6, 30),
        financial_report_hash="b" * 64,
    )
    same_source = document_identity_conflicts(
        [existing],
        symbol="aksa",
        report_period_end=date(2026, 3, 31),
        financial_report_hash="b" * 64,
    )

    assert company_conflicts == [
        "Belge daha önce AKSA şirketi için kullanılmış."
    ]
    assert "31.03.2026" in period_conflicts[0]
    assert same_source == []


def test_document_usage_empty_hash_returns_no_records(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()

    assert repository.list_document_usages("") == []


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


def test_analysis_snapshot_freezes_methodology_and_breakdown():
    score = ScoreBreakdown(
        profitability=12,
        growth=11,
        leverage=10,
        liquidity=8,
        cash_flow=12,
        efficiency=8,
        valuation=7,
        risk=4,
        management=4,
        total=76,
        grade="B+",
        decision="İzle / Kademeli Al",
    )
    confidence = AnalysisConfidence(
        total=88,
        status="Yüksek",
        decision="İzle / Kademeli Al",
        completeness_component=55,
        source_component=20,
        report_component=5,
        period_component=5,
        validation_component=3,
    )

    snapshot = attach_analysis_snapshot(
        _audit("TEST", 0, DataSourceType.PDF),
        FinancialMetrics(symbol="TEST", company_name="Test"),
        score,
        confidence,
    )

    assert snapshot.alpha_score == 76
    assert snapshot.grade == "B+"
    assert snapshot.confidence_score == 88
    assert snapshot.methodology_version == settings.scoring_methodology_version
    assert len(snapshot.input_fingerprint) == 64
    assert snapshot.score_breakdown["profitability"] == 12


def test_analysis_snapshot_comparison_calculates_category_changes():
    previous = _audit("AKSA", 78, DataSourceType.PDF).model_copy(
        update={
            "confidence_score": 80,
            "grade": "B+",
            "decision": "İzle",
            "score_breakdown": {"profitability": 10, "growth": 9},
        }
    )
    current = _audit("aksa", 84, DataSourceType.CORRECTION).model_copy(
        update={
            "confidence_score": 90,
            "grade": "A",
            "decision": "Al",
            "score_breakdown": {"profitability": 12.5, "growth": 8},
        }
    )

    comparison = compare_analysis_snapshots(previous, current)

    assert comparison.score_delta == 6
    assert comparison.confidence_delta == 10
    assert comparison.category_deltas == {
        "profitability": 2.5,
        "growth": -1,
    }
    assert comparison.previous_grade == "B+"
    assert comparison.current_grade == "A"
    assert comparison.methodology_changed is False


def test_snapshot_comparison_handles_legacy_missing_fields():
    previous = _audit("TEST", 70, DataSourceType.LEGACY).model_copy(
        update={
            "confidence_score": None,
            "methodology_version": "legacy",
            "score_breakdown": {},
        }
    )
    current = _audit("TEST", 75, DataSourceType.PDF)

    comparison = compare_analysis_snapshots(previous, current)

    assert comparison.score_delta == 5
    assert comparison.confidence_delta is None
    assert comparison.category_deltas == {}
    assert comparison.methodology_changed is True


def test_snapshot_comparison_rejects_different_companies():
    with pytest.raises(ValueError, match="aynı şirkete"):
        compare_analysis_snapshots(
            _audit("AKSA", 80, DataSourceType.PDF),
            _audit("GUBRF", 82, DataSourceType.PDF),
        )


def test_analysis_fingerprint_is_stable_and_ignores_company_name():
    first = FinancialMetrics(
        symbol="AKSA",
        company_name="Aksa Akrilik",
        revenue_growth=12.5,
        free_cash_flow=0,
    )
    renamed = first.model_copy(update={"company_name": "AKSA AKRİLİK A.Ş."})
    equivalent = first.model_copy(update={"free_cash_flow": -0.0})
    changed = first.model_copy(update={"revenue_growth": 13})

    assert analysis_input_fingerprint(first) == analysis_input_fingerprint(renamed)
    assert analysis_input_fingerprint(first) == analysis_input_fingerprint(equivalent)
    assert analysis_input_fingerprint(first) != analysis_input_fingerprint(changed)


def test_duplicate_analysis_requires_same_period_and_fingerprint():
    metrics = FinancialMetrics(
        symbol="AKSA",
        company_name="Aksa Akrilik",
        revenue_growth=12.5,
    )
    latest = _audit("AKSA", 80, DataSourceType.PDF).model_copy(
        update={"input_fingerprint": analysis_input_fingerprint(metrics)}
    )

    assert is_duplicate_analysis(
        latest, metrics, date(2026, 3, 31)
    ) is True
    assert is_duplicate_analysis(
        latest, metrics, date(2026, 6, 30)
    ) is False
    assert is_duplicate_analysis(
        latest,
        metrics.model_copy(update={"revenue_growth": 13}),
        date(2026, 3, 31),
    ) is False
    assert is_duplicate_analysis(None, metrics, date(2026, 3, 31)) is False
