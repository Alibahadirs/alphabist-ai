from app.data_quality.models import (
    DataQualityRow,
    DataQualitySummary,
    DecisionReadinessRow,
    DecisionReadinessSummary,
)
from app.data_quality.remediation import (
    build_remediation_queue,
    remediation_task_id,
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
