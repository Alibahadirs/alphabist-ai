from datetime import datetime, timezone

from app.database import repository
from app.reporting.company_report import company_report_fingerprint
from app.reporting.exchange import (
    build_company_report_exchange_package,
    serialize_company_report_exchange_package,
)
from app.reporting.importer import (
    import_company_report_exchange_package,
)
from app.reporting.models import CompanyInvestmentReport
from app.sector.profiles import CompanyProfile


def _payload(symbol: str = "TEST") -> bytes:
    report = CompanyInvestmentReport(
        symbol=symbol,
        company_name="Test A.Ş.",
        company_profile=CompanyProfile.STANDARD,
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        alpha_score=80,
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
    report = report.model_copy(
        update={"report_fingerprint": company_report_fingerprint(report)}
    )
    return serialize_company_report_exchange_package(
        build_company_report_exchange_package([report])
    )


def test_company_report_importer_adds_and_deduplicates_reports(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    payload = _payload()

    first = import_company_report_exchange_package(
        payload,
        expected_symbol="test",
    )
    second = import_company_report_exchange_package(
        payload,
        expected_symbol="TEST",
    )

    assert first.valid is True
    assert first.imported_count == 1
    assert first.duplicate_count == 0
    assert second.valid is True
    assert second.imported_count == 0
    assert second.duplicate_count == 1
    assert len(repository.list_company_report_snapshots("TEST")) == 1


def test_company_report_importer_rejects_wrong_company(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()

    result = import_company_report_exchange_package(
        _payload("OTHER"),
        expected_symbol="TEST",
    )

    assert result.valid is False
    assert "seçili şirkete ait değil" in result.errors[0]
    assert repository.list_company_report_snapshots("TEST") == []


def test_company_report_importer_rejects_invalid_package(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()

    result = import_company_report_exchange_package(
        b"not-json",
        expected_symbol="TEST",
    )

    assert result.valid is False
    assert result.imported_count == 0
    assert repository.list_company_report_snapshots("TEST") == []
