from app.data_quality.models import (
    RemediationTaskState,
    RemediationTaskStatus,
)
from app.database import repository
from app.data_quality.remediation import verify_remediation_event_chain


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
            issue_fingerprint="a" * 64,
        )
    )
    repository.upsert_remediation_task_state(
        RemediationTaskState(
            task_id="task-1",
            symbol="TEST",
            task_category="Finansal",
            status=RemediationTaskStatus.COMPLETED,
            note="KAP raporuyla doğrulandı",
            issue_fingerprint="b" * 64,
        )
    )

    states = repository.list_remediation_task_states()
    events = repository.list_remediation_task_events("task-1")

    assert len(states) == 1
    assert states[0].symbol == "TEST"
    assert states[0].status == RemediationTaskStatus.COMPLETED
    assert states[0].note == "KAP raporuyla doğrulandı"
    assert states[0].issue_fingerprint == "b" * 64
    assert states[0].updated_at is not None
    assert len(events) == 2
    assert events[0].previous_status is None
    assert events[0].new_status == RemediationTaskStatus.IN_PROGRESS
    assert events[1].previous_status == RemediationTaskStatus.IN_PROGRESS
    assert events[1].new_status == RemediationTaskStatus.COMPLETED
    assert events[0].previous_event_hash == ""
    assert events[0].event_hash
    assert events[1].previous_event_hash == events[0].event_hash
    assert verify_remediation_event_chain(events).valid is True


def test_remediation_state_does_not_duplicate_unchanged_event(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    state = RemediationTaskState(
        task_id="task-1",
        symbol="TEST",
        task_category="Finansal",
        status=RemediationTaskStatus.OPEN,
        note="Aynı",
        issue_fingerprint="a" * 64,
    )

    repository.upsert_remediation_task_state(state)
    repository.upsert_remediation_task_state(state)

    assert len(repository.list_remediation_task_events("task-1")) == 1


def test_remediation_event_chain_detects_database_tampering(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.db")
    repository.init_db()
    repository.upsert_remediation_task_state(
        RemediationTaskState(
            task_id="task-1",
            symbol="TEST",
            task_category="Finansal",
            status=RemediationTaskStatus.OPEN,
            note="İlk kayıt",
            issue_fingerprint="a" * 64,
        )
    )
    with repository.connect() as conn:
        conn.execute(
            """UPDATE remediation_task_event SET note='Değiştirildi'
            WHERE task_id='task-1'"""
        )

    result = verify_remediation_event_chain(
        repository.list_remediation_task_events("task-1")
    )

    assert result.valid is False
    assert result.invalid_event_id is not None


def test_remediation_state_migrates_legacy_table(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "legacy.db")
    with repository.connect() as conn:
        conn.execute(
            """CREATE TABLE remediation_task_state(
            task_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            task_category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Açık',
            note TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
        )
        conn.execute(
            """INSERT INTO remediation_task_state(
            task_id, symbol, task_category, status, note)
            VALUES('legacy-1', 'TEST', 'Finansal', 'Tamamlandı', 'Eski')"""
        )

    repository.init_db()
    states = repository.list_remediation_task_states()

    assert states[0].task_id == "legacy-1"
    assert states[0].issue_fingerprint == ""
