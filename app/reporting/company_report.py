from datetime import datetime, timezone

from app.analysis.service import build_company_analysis
from app.audit.models import CompanyDataAudit
from app.confidence.models import AnalysisConfidence
from app.core.settings import settings
from app.reporting.models import CompanyInvestmentReport
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.sector.profiles import PROFILE_LABELS
from app.technical.engine import calculate_verified_combined_score
from app.technical.models import TechnicalQualityRow


def _combined_decision(score: float | None) -> str:
    if score is None:
        return "Doğrulama gerekli"
    if score >= 85:
        return "Güçlü al adayı"
    if score >= 70:
        return "Al adayı"
    if score >= 55:
        return "İzle"
    if score >= 40:
        return "Bekle"
    return "Kaçın"


def build_company_investment_report(
    company: FinancialMetrics,
    score: ScoreBreakdown,
    confidence: AnalysisConfidence,
    audit: CompanyDataAudit | None,
    technical: TechnicalQualityRow | None,
    *,
    generated_at: datetime | None = None,
) -> CompanyInvestmentReport:
    analysis = build_company_analysis(company, score)
    technical_ready = bool(
        technical
        and technical.current
        and technical.technical_score is not None
    )
    technical_score = (
        technical.technical_score if technical_ready and technical else None
    )
    combined_score = (
        calculate_verified_combined_score(
            score.total,
            technical_score,
            financial_ready=confidence.decision_ready,
            technical_ready=technical_ready,
        )
        if technical_score is not None
        else None
    )
    if not confidence.decision_ready:
        combined_decision = "Finansal doğrulama gerekli"
    elif not technical_ready:
        combined_decision = "Teknik doğrulama gerekli"
    else:
        combined_decision = _combined_decision(combined_score)

    data_quality_notes = list(confidence.reasons)
    if audit:
        data_quality_notes.extend(audit.validation_warnings)
        if audit.methodology_version != settings.scoring_methodology_version:
            data_quality_notes.append(
                "Analiz eski puanlama metodolojisiyle kaydedilmiş."
            )
    else:
        data_quality_notes.append(
            "Analiz kaynağına ait audit kaydı bulunmuyor."
        )
    if technical and not technical.current:
        data_quality_notes.append(
            f"Teknik kayıt kullanılamıyor: {technical.status}."
        )
    elif technical is None:
        data_quality_notes.append("Teknik kalite kaydı bulunmuyor.")

    indicator_rows = [
        {
            "field": indicator.field,
            "label": indicator.label,
            "value": indicator.value,
            "unit": indicator.unit,
            "status": indicator.status,
            "interpretation": indicator.interpretation,
        }
        for indicator in analysis.indicators
    ]
    summary = (
        f"{analysis.summary} Sektör profili "
        f"{PROFILE_LABELS[analysis.company_profile]}. "
        f"Birleşik karar: {combined_decision}."
    )
    return CompanyInvestmentReport(
        symbol=company.symbol,
        company_name=company.company_name,
        company_profile=analysis.company_profile,
        generated_at=generated_at or datetime.now(timezone.utc),
        report_period_end=audit.report_period_end if audit else None,
        alpha_score=score.total,
        alpha_grade=score.grade,
        alpha_decision=score.decision,
        confidence_score=confidence.total,
        confidence_status=confidence.status,
        decision_ready=confidence.decision_ready,
        technical_score=technical_score,
        technical_signal=(
            technical.signal if technical_ready and technical else None
        ),
        technical_price_date=(
            technical.price_date if technical_ready and technical else None
        ),
        combined_score=combined_score,
        combined_decision=combined_decision,
        summary=summary,
        strengths=analysis.strengths,
        risks=analysis.risks,
        data_quality_notes=list(dict.fromkeys(data_quality_notes)),
        category_scores={
            "profitability": score.profitability,
            "growth": score.growth,
            "leverage": score.leverage,
            "liquidity": score.liquidity,
            "cash_flow": score.cash_flow,
            "efficiency": score.efficiency,
            "valuation": score.valuation,
            "risk": score.risk,
            "management": score.management,
        },
        indicators=indicator_rows,
        scoring_methodology_version=settings.scoring_methodology_version,
        technical_methodology_version=(
            settings.technical_methodology_version
        ),
    )
