from app.audit.models import (
    CompanyDataAudit,
    DataSourceType,
    MetricSourceType,
)
from app.confidence.service import calculate_analysis_confidence
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
    return CompanyDataAudit(
        symbol="TEST",
        source_type=DataSourceType.PDF,
        company_profile=CompanyProfile.STANDARD,
        period_months=3,
        financial_report_name="financial.pdf",
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


def test_manual_sources_gate_strong_buy_decision():
    metrics = _strong_metrics()
    score = calculate_alpha_score(metrics)
    audit = _audit(MetricSourceType.MANUAL).model_copy(
        update={
            "source_type": DataSourceType.MANUAL,
            "period_months": None,
            "financial_report_name": "",
        }
    )

    confidence = calculate_analysis_confidence(metrics, score, audit)

    assert confidence.total == 82.5
    assert confidence.status == "Orta"
    assert confidence.decision == "İzle / Doğrula"
