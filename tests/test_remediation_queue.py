from app.data_quality.models import (
    DataQualityRow,
    DataQualitySummary,
    DecisionReadinessRow,
    DecisionReadinessSummary,
    RemediationTaskState,
    RemediationTaskStatus,
)
from app.data_quality.remediation import (
    build_remediation_queue,
    remediation_issue_fingerprint,
    remediation_task_id,
    validate_remediation_transition,
)
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile


def _quality_summary(rows: list[DataQualityRow]) -> DataQualitySummary:
    return DataQualitySummary(
        rows=rows,
        total_companies=len(rows),
        verified_count=0,
        review_count=len(rows),
        critical_count=0,
        average_completeness=80,
    )


def _readiness_summary(
    rows: list[DecisionReadinessRow],
) -> DecisionReadinessSummary:
    return DecisionReadinessSummary(
        rows=rows,
        total=len(rows),
        ready_count=0,
        financial_only_count=0,
        technical_only_count=0,
        combined_issue_count=len(rows),
    )


def test_remediation_queue_uses_sector_specific_financial_action():
    company = FinancialMetrics(
        symbol="BANK",
        company_name="Test Bankası",
        company_profile=CompanyProfile.BANK,
    )
    readiness = _readiness_summary(
        [
            DecisionReadinessRow(
                symbol="BANK",
                company_name=company.company_name,
                financial_ready=False,
                technical_ready=True,
                status="Finansal doğrulama gerekli",
                recommended_action="Finansal raporu doğrula",
                priority_score=55,
                priority_level="Orta",
            )
        ]
    )
    quality = _quality_summary(
        [
            DataQualityRow(
                symbol="BANK",
                company_name=company.company_name,
                company_profile=CompanyProfile.BANK,
                completeness=80,
                status="İncele",
            )
        ]
    )

    queue = build_remediation_queue([company], readiness, quality)

    assert queue.total_tasks == 1
    assert queue.financial_task_count == 1
    assert queue.rows[0].task_id == remediation_task_id(
        "BANK",
        "Finansal",
    )
    assert "sermaye yeterliliği" in queue.rows[0].recommended_action
    assert "takipteki kredi" in queue.rows[0].recommended_action


def test_remediation_queue_elevates_critical_errors_and_combined_work():
    company = FinancialMetrics(
        symbol="GYO",
        company_name="Test GYO",
        company_profile=CompanyProfile.REIT,
    )
    readiness = _readiness_summary(
        [
            DecisionReadinessRow(
                symbol="GYO",
                company_name=company.company_name,
                financial_ready=False,
                technical_ready=False,
                status="Finansal ve teknik doğrulama gerekli",
                recommended_action="İki kaydı doğrula",
                blockers=["Hesap uyuşmazlığı", "Teknik kayıt yok"],
                priority_score=85,
                priority_level="Yüksek",
            )
        ]
    )
    quality = _quality_summary(
        [
            DataQualityRow(
                symbol="GYO",
                company_name=company.company_name,
                company_profile=CompanyProfile.REIT,
                completeness=70,
                status="Kritik",
                errors=["Net kâr marjı yeniden üretilemiyor."],
            )
        ]
    )

    queue = build_remediation_queue([company], readiness, quality)

    row = queue.rows[0]
    assert row.priority_score == 95
    assert row.priority_level == "Acil"
    assert row.task_category == "Finansal + teknik"
    assert "portföy/NAD" in row.recommended_action
    assert "teknik puanı yeniden hesapla" in row.recommended_action
    assert queue.urgent_count == 1
    assert queue.technical_task_count == 1


def test_remediation_task_id_is_normalized_and_stable():
    first = remediation_task_id(" bank ", "Finansal")
    second = remediation_task_id("BANK", "Finansal")

    assert first == second
    assert len(first) == 20
    assert first != remediation_task_id("BANK", "Teknik")


def test_remediation_issue_fingerprint_tracks_issue_content():
    first = remediation_issue_fingerprint(
        "bank",
        CompanyProfile.BANK,
        "Finansal",
        "Sermaye yeterliliğini doğrula",
        ["Teknik kayıt yok", "Rapor eski"],
    )
    reordered = remediation_issue_fingerprint(
        "BANK",
        CompanyProfile.BANK,
        "Finansal",
        "Sermaye yeterliliğini doğrula",
        ["Rapor eski", "Teknik kayıt yok"],
    )
    changed = remediation_issue_fingerprint(
        "BANK",
        CompanyProfile.BANK,
        "Finansal",
        "Takipteki kredileri doğrula",
        ["Rapor eski", "Teknik kayıt yok"],
    )

    assert first == reordered
    assert len(first) == 64
    assert first != changed


def test_remediation_queue_applies_persisted_workflow_state():
    company = FinancialMetrics(
        symbol="BANK",
        company_name="Test Bankası",
        company_profile=CompanyProfile.BANK,
    )
    readiness = _readiness_summary(
        [
            DecisionReadinessRow(
                symbol="BANK",
                company_name=company.company_name,
                financial_ready=False,
                technical_ready=True,
                status="Finansal doğrulama gerekli",
                recommended_action="Finansal raporu doğrula",
                priority_score=55,
                priority_level="Orta",
            )
        ]
    )
    quality = _quality_summary([])
    task_id = remediation_task_id("BANK", "Finansal")
    state = RemediationTaskState(
        task_id=task_id,
        symbol="BANK",
        task_category="Finansal",
        status=RemediationTaskStatus.IN_PROGRESS,
        note="Denetim raporu bekleniyor",
        issue_fingerprint=remediation_issue_fingerprint(
            "BANK",
            CompanyProfile.BANK,
            "Finansal",
            (
                "Net dönem kârı, özkaynak, sermaye yeterliliği ve "
                "takipteki kredi göstergelerini banka raporundan doğrula"
            ),
            [],
        ),
    )

    queue = build_remediation_queue(
        [company],
        readiness,
        quality,
        {task_id: state},
    )

    assert queue.rows[0].workflow_status == (
        RemediationTaskStatus.IN_PROGRESS
    )
    assert queue.rows[0].workflow_note == "Denetim raporu bekleniyor"
    assert queue.in_progress_count == 1
    assert queue.open_count == 0
    assert queue.completed_count == 0


def test_changed_issue_reopens_non_open_workflow_state():
    company = FinancialMetrics(
        symbol="BANK",
        company_name="Test Bankası",
        company_profile=CompanyProfile.BANK,
    )
    readiness = _readiness_summary(
        [
            DecisionReadinessRow(
                symbol="BANK",
                company_name=company.company_name,
                financial_ready=False,
                technical_ready=True,
                status="Finansal doğrulama gerekli",
                recommended_action="Finansal raporu doğrula",
                blockers=["Yeni rapor dönemi doğrulanmadı."],
                priority_score=55,
                priority_level="Orta",
            )
        ]
    )
    task_id = remediation_task_id("BANK", "Finansal")
    old_state = RemediationTaskState(
        task_id=task_id,
        symbol="BANK",
        task_category="Finansal",
        status=RemediationTaskStatus.COMPLETED,
        note="Önceki dönem tamamlandı",
        issue_fingerprint="a" * 64,
    )

    queue = build_remediation_queue(
        [company],
        readiness,
        _quality_summary([]),
        {task_id: old_state},
    )

    assert queue.rows[0].workflow_status == (
        RemediationTaskStatus.REOPEN_REQUIRED
    )
    assert queue.rows[0].issue_fingerprint_matches is False
    assert queue.reopen_required_count == 1
    assert queue.completed_count == 0


def test_remediation_transition_requires_closed_task_to_reopen():
    blocked = validate_remediation_transition(
        RemediationTaskStatus.COMPLETED,
        RemediationTaskStatus.DISMISSED,
    )
    reopened = validate_remediation_transition(
        RemediationTaskStatus.COMPLETED,
        RemediationTaskStatus.OPEN,
    )

    assert blocked.allowed is False
    assert "önce yeniden açılmalıdır" in blocked.message
    assert reopened.allowed is True


def test_system_reopen_status_cannot_be_selected_manually():
    result = validate_remediation_transition(
        RemediationTaskStatus.OPEN,
        RemediationTaskStatus.REOPEN_REQUIRED,
    )

    assert result.allowed is False
    assert "yalnız sistem" in result.message
