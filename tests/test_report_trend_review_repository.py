from app.database import repository
from app.reporting.models import (
    CompanyReportTrendReviewState,
    ReportTrendReviewStatus,
)


def test_report_trend_review_state_adds_and_updates(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.upsert_report_trend_review_state(
        CompanyReportTrendReviewState(
            task_id="report-trend:TEST",
            symbol="test",
            status=ReportTrendReviewStatus.IN_REVIEW,
            note="İlk inceleme",
            issue_fingerprint="a" * 64,
        )
    )
    repository.upsert_report_trend_review_state(
        CompanyReportTrendReviewState(
            task_id="report-trend:TEST",
            symbol="TEST",
            status=ReportTrendReviewStatus.RESOLVED,
            note="KAP raporuyla doğrulandı",
            issue_fingerprint="b" * 64,
        )
    )

    states = repository.list_report_trend_review_states()

    assert len(states) == 1
    assert states[0].symbol == "TEST"
    assert states[0].status == ReportTrendReviewStatus.RESOLVED
    assert states[0].note == "KAP raporuyla doğrulandı"
    assert states[0].issue_fingerprint == "b" * 64
    assert states[0].updated_at is not None
