import hashlib
import json
from datetime import datetime, timezone

from app.analysis.service import build_company_analysis
from app.audit.models import CompanyDataAudit
from app.confidence.models import AnalysisConfidence
from app.core.settings import settings
from app.reporting.models import CompanyInvestmentReport
from app.scoring.labels import get_category_label
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.sector.profiles import PROFILE_LABELS
from app.technical.engine import calculate_verified_combined_score
from app.technical.models import TechnicalQualityRow


def company_report_fingerprint(
    report: CompanyInvestmentReport,
) -> str:
    payload = report.model_dump(
        mode="json",
        exclude={"generated_at", "report_fingerprint"},
    )
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    report = CompanyInvestmentReport(
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
    return report.model_copy(
        update={"report_fingerprint": company_report_fingerprint(report)}
    )


def _format_decimal(value: float, digits: int = 2) -> str:
    formatted = f"{value:,.{digits}f}"
    return (
        formatted.replace(",", "\0")
        .replace(".", ",")
        .replace("\0", ".")
    )


def _format_indicator_value(
    value: float | None,
    unit: str,
) -> str:
    if value is None:
        return "-"
    formatted = _format_decimal(value)
    if unit == "%":
        return f"%{formatted}"
    if unit == "x":
        return f"{formatted}x"
    return f"{formatted} {unit}".strip()


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def render_company_report_markdown(
    report: CompanyInvestmentReport,
) -> str:
    technical_score = (
        f"{_format_decimal(report.technical_score, 1)}/100"
        if report.technical_score is not None
        else "-"
    )
    combined_score = (
        f"{_format_decimal(report.combined_score, 1)}/100"
        if report.combined_score is not None
        else "-"
    )
    lines = [
        f"# {report.symbol} - {report.company_name}",
        "",
        "## Rapor özeti",
        "",
        "| Alan | Değer |",
        "|---|---|",
        f"| Sektör profili | {PROFILE_LABELS[report.company_profile]} |",
        (
            "| Finansal dönem | "
            f"{report.report_period_end:%d.%m.%Y} |"
            if report.report_period_end
            else "| Finansal dönem | - |"
        ),
        f"| Alpha Score | {_format_decimal(report.alpha_score, 1)}/100 |",
        f"| Alpha notu | {_markdown_cell(report.alpha_grade)} |",
        f"| Temel karar | {_markdown_cell(report.alpha_decision)} |",
        (
            "| Analiz güveni | "
            f"{_format_decimal(report.confidence_score, 1)}/100 "
            f"({report.confidence_status}) |"
        ),
        f"| Teknik puan | {technical_score} |",
        (
            "| Teknik sinyal | "
            f"{_markdown_cell(report.technical_signal or '-')} |"
        ),
        f"| Birleşik puan | {combined_score} |",
        (
            "| Birleşik karar | "
            f"{_markdown_cell(report.combined_decision)} |"
        ),
        "",
        report.summary,
        "",
        "## Kategori puanları",
        "",
        "| Kategori | Puan |",
        "|---|---:|",
    ]
    for category, value in report.category_scores.items():
        lines.append(
            "| "
            f"{get_category_label(report.company_profile, category)} | "
            f"{_format_decimal(value, 1)} |"
        )

    lines.extend(
        [
            "",
            "## Sektör göstergeleri",
            "",
            "| Gösterge | Değer | Durum | Yorum |",
            "|---|---:|---|---|",
        ]
    )
    for indicator in report.indicators:
        lines.append(
            "| "
            f"{_markdown_cell(indicator['label'])} | "
            f"{_format_indicator_value(indicator.get('value'), indicator['unit'])} | "
            f"{_markdown_cell(indicator['status'])} | "
            f"{_markdown_cell(indicator['interpretation'])} |"
        )

    for title, items, empty_message in (
        ("Güçlü yönler", report.strengths, "Doğrulanmış güçlü yön bulunamadı."),
        ("Riskler ve eksikler", report.risks, "Belirgin risk kaydedilmedi."),
        (
            "Veri kalitesi notları",
            report.data_quality_notes,
            "Ek veri kalitesi notu bulunmuyor.",
        ),
    ):
        lines.extend(["", f"## {title}", ""])
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append(empty_message)

    lines.extend(
        [
            "",
            "## Metodoloji",
            "",
            (
                f"- Temel analiz: `{report.scoring_methodology_version}`"
            ),
            (
                f"- Teknik analiz: `{report.technical_methodology_version}`"
            ),
            f"- Oluşturulma zamanı: `{report.generated_at.isoformat()}`",
            "",
            "> Bu rapor yatırım tavsiyesi değildir. Finansal veriler resmi "
            "KAP/SPK kaynaklarıyla doğrulanmalıdır.",
            "",
        ]
    )
    return "\n".join(lines)


def serialize_company_report_markdown(
    report: CompanyInvestmentReport,
) -> bytes:
    return render_company_report_markdown(report).encode("utf-8-sig")
