import pytest
from pydantic import ValidationError

from app.audit.models import CompanyDataAudit, DataSourceType
from app.database import repository
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
