from app.data_quality.models import (
    RemediationTaskState,
    RemediationTaskStatus,
)
from app.database import repository


def test_remediation_state_repository_adds_and_updates(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()

    repository.upsert_remediation_task_state(
        RemediationTaskState(
            task_id="task-1",
            symbol="test",
            task_category="Finansal",
            status=RemediationTaskStatus.IN_PROGRESS,
            note="Rapor bekleniyor",
        )
    )
    repository.upsert_remediation_task_state(
        RemediationTaskState(
            task_id="task-1",
            symbol="TEST",
            task_category="Finansal",
            status=RemediationTaskStatus.COMPLETED,
            note="KAP raporuyla doğrulandı",
        )
    )

    states = repository.list_remediation_task_states()

    assert len(states) == 1
    assert states[0].symbol == "TEST"
    assert states[0].status == RemediationTaskStatus.COMPLETED
    assert states[0].note == "KAP raporuyla doğrulandı"
    assert states[0].updated_at is not None
