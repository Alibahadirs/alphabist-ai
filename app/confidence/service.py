from app.audit.models import CompanyDataAudit, MetricSourceType
from app.audit.calculations import verify_audit_calculations
from app.confidence.models import AnalysisConfidence
from app.core.settings import settings
from app.reporting.models import ReportFreshnessStatus
from app.reporting.service import assess_report_period
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.validation.service import (
    get_profile_requirements,
    validate_financial_metrics,
    validation_warning_confirmation_matches,
)


SOURCE_WEIGHTS = {
    MetricSourceType.FINANCIAL_REPORT: 1.0,
    MetricSourceType.ACTIVITY_REPORT: 1.0,
    MetricSourceType.SOURCE_CORRECTION: 0.95,
    MetricSourceType.CORRECTION: 0.9,
    MetricSourceType.MANUAL: 0.7,
}

CALCULATION_FIELD_LABELS = {
    "revenue_growth": "Gelir büyümesi",
    "net_profit_growth": "Net kâr büyümesi",
    "net_margin": "Net kâr marjı",
    "roe": "ROE",
    "debt_to_equity": "Borç / özkaynak",
    "current_ratio": "Cari oran",
    "operating_cash_flow": "Operasyonel nakit akışı",
    "free_cash_flow": "Serbest nakit akışı",
    "asset_turnover": "Aktif devir hızı",
    "premium_growth": "Prim büyümesi",
}


def _calculation_integrity(
    audit: CompanyDataAudit | None,
) -> tuple[str, list[str]]:
    if audit is None:
        return "Kayıt yok", []
    if audit.methodology_version != settings.scoring_methodology_version:
        return "Eski metodoloji", []
    if not audit.source_values or not audit.metric_values:
        return "Kaynak izi yok", []

    checks = verify_audit_calculations(audit)
    if not checks:
        return "Uygulanamaz", []

    mismatches = [
        CALCULATION_FIELD_LABELS.get(check.field, check.field)
        for check in checks
        if not check.matches
    ]
    return ("Uyuşmazlık", mismatches) if mismatches else ("Doğrulandı", [])


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
    required_fields = get_profile_requirements(metrics)

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
            report_component += 2
        if audit.financial_report_hash or audit.activity_report_hash:
            report_component += 2
        if audit.comparison_period_confirmed:
            report_component += 1
    period_assessment = assess_report_period(
        audit.report_period_end if audit else None,
        audit.period_months if audit else None,
    )
    period_component = period_assessment.confidence_points
    warnings_confirmed = bool(
        audit
        and validation_warning_confirmation_matches(
            validation.warnings,
            audit.validation_warnings,
            audit.validation_warnings_confirmed,
            audit.methodology_version,
            settings.scoring_methodology_version,
        )
    )
    warning_penalty = len(validation.warnings) * (
        0.5 if warnings_confirmed else 1.5
    )
    validation_penalty = min(
        5.0,
        len(validation.errors) * 5 + warning_penalty,
    )
    validation_component = round(5.0 - validation_penalty, 2)
    calculation_status, calculation_mismatches = _calculation_integrity(audit)
    if calculation_mismatches:
        validation_component = 0.0
    total = round(
        completeness_component
        + source_component
        + report_component
        + period_component
        + validation_component,
        2,
    )
    if period_assessment.blocks_decision:
        total = min(total, 69.0)
    if calculation_mismatches:
        total = min(total, 69.0)
    has_blocking_error = (
        bool(validation.errors)
        or period_assessment.blocks_decision
        or bool(calculation_mismatches)
    )
    decision_ready = not has_blocking_error and total >= 85

    reasons: list[str] = []
    if audit is None:
        reasons.append("Kayıt için doğrulanabilir veri kaynağı geçmişi bulunmuyor.")
    elif sourced_required < len(required_fields):
        reasons.append(
            f"Sektör için gerekli {len(required_fields)} göstergenin "
            f"{sourced_required} tanesinin kaynağı izlenebiliyor."
        )
    if audit and period_assessment.status != ReportFreshnessStatus.CURRENT:
        reasons.append(period_assessment.message)
    if (
        audit
        and (audit.financial_report_name or audit.activity_report_name)
        and not (audit.financial_report_hash or audit.activity_report_hash)
    ):
        reasons.append(
            "Rapor adı kayıtlı ancak dosya içeriğini doğrulayan belge kimliği yok."
        )
    if audit and audit.source_type.value == "pdf" and not audit.comparison_period_confirmed:
        reasons.append(
            "Büyüme oranlarının karşılaştırma dönemi doğrulanmamış."
        )
    if validation.missing_fields:
        reasons.append(
            f"{len(validation.missing_fields)} zorunlu sektör göstergesi eksik."
        )
    if validation.errors:
        reasons.append("Kritik veri doğrulama hatası bulunuyor.")
    elif validation.warnings:
        if warnings_confirmed:
            reasons.append(
                f"{len(validation.warnings)} veri kontrol uyarısı resmi "
                "raporlarla onaylanmış."
            )
        else:
            reasons.append(
                f"{len(validation.warnings)} veri kontrol uyarısı bulunuyor."
            )
    if calculation_mismatches:
        reasons.append(
            "Ham tutarlardan yeniden hesaplanan göstergeler kayıtlı değerlerle "
            f"eşleşmiyor: {', '.join(calculation_mismatches)}."
        )
    if not reasons:
        reasons.append("Zorunlu göstergeler ve veri kaynakları doğrulanabilir durumda.")

    return AnalysisConfidence(
        total=total,
        status=_status(total),
        decision=_gated_decision(
            score,
            total,
            has_blocking_error,
        ),
        decision_ready=decision_ready,
        completeness_component=completeness_component,
        source_component=source_component,
        report_component=report_component,
        period_component=period_component,
        validation_component=validation_component,
        calculation_check_status=calculation_status,
        calculation_mismatch_fields=calculation_mismatches,
        reasons=reasons,
    )
