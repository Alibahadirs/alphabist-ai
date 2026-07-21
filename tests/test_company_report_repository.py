from datetime import datetime, timezone

import pytest

from app.database import repository
from app.reporting.company_report import company_report_fingerprint
from app.reporting.models import CompanyInvestmentReport
from app.sector.profiles import CompanyProfile


def _report(
    alpha_score: float = 80,
    symbol: str = "TEST",
) -> CompanyInvestmentReport:
    report = CompanyInvestmentReport(
        symbol=symbol,
        company_name="Test A.Ş.",
        company_profile=CompanyProfile.STANDARD,
        generated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        alpha_score=alpha_score,
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
    return report.model_copy(
        update={"report_fingerprint": company_report_fingerprint(report)}
    )


def test_company_report_snapshot_repository_prevents_duplicates(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    report = _report()

    assert repository.add_company_report_snapshot(report) is True
    assert repository.add_company_report_snapshot(report) is False

    snapshots = repository.list_company_report_snapshots("test")
    assert len(snapshots) == 1
    assert snapshots[0].report_fingerprint == report.report_fingerprint
    restored = CompanyInvestmentReport.model_validate(
        snapshots[0].report_payload
    )
    assert restored == report


def test_company_report_snapshot_repository_keeps_changed_report(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()

    assert repository.add_company_report_snapshot(_report(80)) is True
    assert repository.add_company_report_snapshot(_report(81)) is True

    assert len(repository.list_company_report_snapshots("TEST")) == 2


def test_company_report_snapshot_rejects_tampered_report(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    report = _report().model_copy(update={"alpha_score": 12})

    with pytest.raises(ValueError, match="parmak izi"):
        repository.add_company_report_snapshot(report)


def test_company_report_snapshot_repository_groups_and_limits_symbols(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.add_company_report_snapshot(_report(70, "AAA"))
    repository.add_company_report_snapshot(_report(71, "AAA"))
    repository.add_company_report_snapshot(_report(80, "BBB"))
    repository.add_company_report_snapshot(_report(81, "BBB"))

    grouped = repository.list_company_report_snapshots_by_symbol(1)

    assert set(grouped) == {"AAA", "BBB"}
    assert len(grouped["AAA"]) == 1
    assert len(grouped["BBB"]) == 1
    assert grouped["AAA"][0].report_payload["alpha_score"] == 71
    assert grouped["BBB"][0].report_payload["alpha_score"] == 81
