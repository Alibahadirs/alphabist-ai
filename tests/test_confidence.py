from calendar import monthrange
from datetime import date

from app.audit.models import (
    CompanyDataAudit,
    DataSourceType,
    MetricSourceType,
)
from app.confidence.service import calculate_analysis_confidence
from app.core.settings import settings
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile
from app.validation.service import PROFILE_REQUIREMENTS


def _strong_metrics() -> FinancialMetrics:
    return FinancialMetrics(
        symbol="TEST",
        company_name="Test Şirketi",
        revenue_growth=40,
        net_profit_growth=60,
        net_margin=25,
        roe=35,
        debt_to_equity=0,
        current_ratio=2.5,
        operating_cash_flow=100,
        free_cash_flow=50,
        asset_turnover=1.5,
        valuation_score_input=100,
        management_score_input=100,
        risk_score_input=100,
    )


def _audit(source: MetricSourceType) -> CompanyDataAudit:
    required = PROFILE_REQUIREMENTS[CompanyProfile.STANDARD]
    today = date.today()
    quarter_ends = [
        date(today.year - 1, 12, 31),
        *[
            date(today.year, month, monthrange(today.year, month)[1])
            for month in (3, 6, 9, 12)
        ],
    ]
    report_period_end = max(value for value in quarter_ends if value <= today)
    return CompanyDataAudit(
        symbol="TEST",
        source_type=DataSourceType.PDF,
        company_profile=CompanyProfile.STANDARD,
        period_months=report_period_end.month,
        report_period_end=report_period_end,
        financial_report_name="financial.pdf",
        financial_report_hash="a" * 64,
        comparison_period_end=report_period_end.replace(
            year=report_period_end.year - 1
        ),
        comparison_period_confirmed=True,
        completeness=100,
        alpha_score=100,
        field_sources={field: source for field in required},
    )


def test_legacy_record_cannot_produce_investment_decision():
    metrics = _strong_metrics()
    score = calculate_alpha_score(metrics)

    confidence = calculate_analysis_confidence(metrics, score, None)

    assert confidence.total == 60
    assert confidence.status == "Düşük"
    assert confidence.decision == "Doğrula / Karar verme"


def test_complete_pdf_sources_produce_high_confidence():
    metrics = _strong_metrics()
    score = calculate_alpha_score(metrics)

    confidence = calculate_analysis_confidence(
        metrics,
        score,
        _audit(MetricSourceType.FINANCIAL_REPORT),
    )

    assert confidence.total == 100
    assert confidence.status == "Yüksek"
    assert confidence.decision == "Güçlü Al"


def test_pdf_source_corrections_keep_high_but_not_full_confidence():
    metrics = _strong_metrics()
    score = calculate_alpha_score(metrics)

    confidence = calculate_analysis_confidence(
        metrics,
        score,
        _audit(MetricSourceType.SOURCE_CORRECTION),
    )

    assert confidence.total == 98.75
    assert confidence.status == "Yüksek"


def test_manual_sources_gate_strong_buy_decision():
    metrics = _strong_metrics()
    score = calculate_alpha_score(metrics)
    audit = _audit(MetricSourceType.MANUAL).model_copy(
        update={
            "source_type": DataSourceType.MANUAL,
            "period_months": None,
            "report_period_end": None,
            "financial_report_name": "",
            "financial_report_hash": "",
            "comparison_period_end": None,
            "comparison_period_confirmed": False,
        }
    )

    confidence = calculate_analysis_confidence(metrics, score, audit)

    assert confidence.total == 82.5
    assert confidence.status == "Orta"
    assert confidence.decision == "İzle / Doğrula"


def test_legacy_pdf_without_document_hash_loses_proof_points():
    metrics = _strong_metrics()
    score = calculate_alpha_score(metrics)
    audit = _audit(MetricSourceType.FINANCIAL_REPORT).model_copy(
        update={"financial_report_hash": ""}
    )

    confidence = calculate_analysis_confidence(metrics, score, audit)

    assert confidence.total == 98
    assert any("belge kimliği yok" in reason for reason in confidence.reasons)


def test_stale_report_caps_confidence_and_blocks_decision():
    metrics = _strong_metrics()
    score = calculate_alpha_score(metrics)
    audit = _audit(MetricSourceType.FINANCIAL_REPORT).model_copy(
        update={
            "period_months": 12,
            "report_period_end": date(2020, 12, 31),
        }
    )

    confidence = calculate_analysis_confidence(metrics, score, audit)

    assert confidence.total == 69
    assert confidence.status == "Düşük"
    assert confidence.decision == "Doğrula / Karar verme"
    assert any("güncel değil" in reason for reason in confidence.reasons)


def test_calculation_mismatch_caps_confidence_and_blocks_decision():
    metrics = _strong_metrics()
    score = calculate_alpha_score(metrics)
    audit = _audit(MetricSourceType.FINANCIAL_REPORT).model_copy(
        update={
            "methodology_version": settings.scoring_methodology_version,
            "source_values": {
                "revenue": 1_200_000,
                "previous_revenue": 1_000_000,
            },
            "metric_values": {
                "company_name": "Test Şirketi",
                "revenue_growth": 25.0,
            },
        }
    )

    confidence = calculate_analysis_confidence(metrics, score, audit)

    assert confidence.total == 69
    assert confidence.status == "Düşük"
    assert confidence.decision == "Doğrula / Karar verme"
    assert confidence.validation_component == 0
    assert confidence.calculation_check_status == "Uyuşmazlık"
    assert confidence.calculation_mismatch_fields == ["Gelir büyümesi"]
    assert any("eşleşmiyor" in reason for reason in confidence.reasons)


def test_old_methodology_calculation_snapshot_does_not_block_decision():
    metrics = _strong_metrics()
    score = calculate_alpha_score(metrics)
    audit = _audit(MetricSourceType.FINANCIAL_REPORT).model_copy(
        update={
            "methodology_version": "alpha-2025.1",
            "source_values": {
                "revenue": 1_200_000,
                "previous_revenue": 1_000_000,
            },
            "metric_values": {
                "company_name": "Test Şirketi",
                "revenue_growth": 25.0,
            },
        }
    )

    confidence = calculate_analysis_confidence(metrics, score, audit)

    assert confidence.total == 100
    assert confidence.decision == "Güçlü Al"
    assert confidence.calculation_check_status == "Eski metodoloji"
    assert confidence.calculation_mismatch_fields == []
