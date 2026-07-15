from app.audit.models import CompanyDataAudit, MetricSourceType
from app.confidence.models import AnalysisConfidence
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.sector.profiles import CompanyProfile
from app.validation.service import PROFILE_REQUIREMENTS, validate_financial_metrics


SOURCE_WEIGHTS = {
    MetricSourceType.FINANCIAL_REPORT: 1.0,
    MetricSourceType.ACTIVITY_REPORT: 1.0,
    MetricSourceType.CORRECTION: 0.9,
    MetricSourceType.MANUAL: 0.7,
}


def _status(total: float) -> str:
    if total >= 85:
        return "Yüksek"
    if total >= 70:
        return "Orta"
    return "Düşük"


def _gated_decision(
    score: ScoreBreakdown,
    confidence: float,
    has_errors: bool,
) -> str:
    if has_errors or confidence < 70:
        return "Doğrula / Karar verme"
    if confidence < 85 and score.decision in ("Güçlü Al", "Al"):
        return "İzle / Doğrula"
    return score.decision


def calculate_analysis_confidence(
    metrics: FinancialMetrics,
    score: ScoreBreakdown,
    audit: CompanyDataAudit | None,
) -> AnalysisConfidence:
    validation = validate_financial_metrics(metrics)
    profile = CompanyProfile(metrics.company_profile)
    required_fields = PROFILE_REQUIREMENTS[profile]

    completeness_component = round(validation.completeness * 0.55, 2)
    sourced_required = (
        sum(field in audit.field_sources for field in required_fields)
        if audit
        else 0
    )
    weighted_sources = (
        sum(
            SOURCE_WEIGHTS.get(audit.field_sources.get(field), 0)
            for field in required_fields
        )
        if audit
        else 0
    )
    source_component = round(
        weighted_sources / len(required_fields) * 25,
        2,
    )
    report_component = 0.0
    if audit:
        report_component += 5
        if audit.financial_report_name or audit.activity_report_name:
            report_component += 5
    period_component = (
        5.0 if audit and audit.period_months in (3, 6, 9, 12) else 0.0
    )
    validation_penalty = min(
        5.0,
        len(validation.errors) * 5 + len(validation.warnings) * 1.5,
    )
    validation_component = round(5.0 - validation_penalty, 2)
    total = round(
        completeness_component
        + source_component
        + report_component
        + period_component
        + validation_component,
        2,
    )

    reasons: list[str] = []
    if audit is None:
        reasons.append("Kayıt için doğrulanabilir veri kaynağı geçmişi bulunmuyor.")
    elif sourced_required < len(required_fields):
        reasons.append(
            f"Sektör için gerekli {len(required_fields)} göstergenin "
            f"{sourced_required} tanesinin kaynağı izlenebiliyor."
        )
    if audit and audit.period_months not in (3, 6, 9, 12):
        reasons.append("Finansal rapor dönemi doğrulanmamış.")
    if validation.missing_fields:
        reasons.append(
            f"{len(validation.missing_fields)} zorunlu sektör göstergesi eksik."
        )
    if validation.errors:
        reasons.append("Kritik veri doğrulama hatası bulunuyor.")
    elif validation.warnings:
        reasons.append(
            f"{len(validation.warnings)} veri kontrol uyarısı bulunuyor."
        )
    if not reasons:
        reasons.append("Zorunlu göstergeler ve veri kaynakları doğrulanabilir durumda.")

    return AnalysisConfidence(
        total=total,
        status=_status(total),
        decision=_gated_decision(score, total, bool(validation.errors)),
        completeness_component=completeness_component,
        source_component=source_component,
        report_component=report_component,
        period_component=period_component,
        validation_component=validation_component,
        reasons=reasons,
    )
