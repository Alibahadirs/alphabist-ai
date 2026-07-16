import hashlib
import json
from datetime import date
from math import isclose
from typing import Any

from app.audit.models import (
    AnalysisSnapshotComparison,
    CompanyDataAudit,
    MetricSourceType,
)
from app.confidence.models import AnalysisConfidence
from app.core.constants import CATEGORY_MAX_POINTS
from app.core.settings import settings
from app.parser.models import (
    ActivityReportExtractionResult,
    PdfExtractionResult,
)
from app.scoring.models import FinancialMetrics, ScoreBreakdown


FINANCIAL_METRIC_DEPENDENCIES = {
    "revenue_growth": {"revenue", "previous_revenue"},
    "net_profit_growth": {"net_profit", "previous_net_profit"},
    "net_margin": {"net_profit", "revenue"},
    "roe": {"net_profit", "equity"},
    "debt_to_equity": {"total_debt", "equity"},
    "current_ratio": {"current_assets", "current_liabilities"},
    "operating_cash_flow": {"operating_cash_flow"},
    "free_cash_flow": {"operating_cash_flow", "capital_expenditures"},
    "asset_turnover": {"revenue", "total_assets"},
}


def document_fingerprint(file_bytes: bytes) -> str:
    """Return a stable identity for an uploaded source document."""
    return hashlib.sha256(file_bytes).hexdigest() if file_bytes else ""


def document_identity_conflicts(
    existing_audits: list[CompanyDataAudit],
    *,
    symbol: str,
    report_period_end: date | None,
    financial_report_hash: str = "",
    activity_report_hash: str = "",
) -> list[str]:
    """Detect source documents previously assigned to another company or period."""
    normalized_symbol = symbol.upper().strip()
    submitted_hashes = {
        value
        for value in (financial_report_hash, activity_report_hash)
        if value
    }
    conflicts: set[str] = set()

    for audit in existing_audits:
        existing_hashes = {
            value
            for value in (
                audit.financial_report_hash,
                audit.activity_report_hash,
            )
            if value
        }
        if not submitted_hashes.intersection(existing_hashes):
            continue
        if audit.symbol.upper().strip() != normalized_symbol:
            conflicts.add(
                f"Belge daha önce {audit.symbol} şirketi için kullanılmış."
            )
        elif audit.report_period_end != report_period_end:
            previous_period = (
                f"{audit.report_period_end:%d.%m.%Y}"
                if audit.report_period_end
                else "belirtilmemiş dönem"
            )
            conflicts.add(
                f"Belge daha önce {audit.symbol} için {previous_period} "
                "dönemiyle kaydedilmiş."
            )

    return sorted(conflicts)


def _normalize_fingerprint_value(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = round(float(value), 8)
        return 0.0 if number == 0 else number
    return value


def analysis_input_fingerprint(metrics: FinancialMetrics) -> str:
    payload = {
        key: _normalize_fingerprint_value(value)
        for key, value in metrics.model_dump(mode="json").items()
        if key != "company_name"
    }
    payload["methodology_version"] = settings.scoring_methodology_version
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def is_duplicate_analysis(
    latest_audit: CompanyDataAudit | None,
    metrics: FinancialMetrics,
    report_period_end: date | None,
) -> bool:
    if latest_audit is None or not latest_audit.input_fingerprint:
        return False
    return (
        latest_audit.report_period_end == report_period_end
        and latest_audit.input_fingerprint
        == analysis_input_fingerprint(metrics)
    )


def compare_analysis_snapshots(
    previous: CompanyDataAudit,
    current: CompanyDataAudit,
) -> AnalysisSnapshotComparison:
    if previous.symbol.upper().strip() != current.symbol.upper().strip():
        raise ValueError("Yalnızca aynı şirkete ait analizler karşılaştırılabilir.")

    confidence_delta = None
    if previous.confidence_score is not None and current.confidence_score is not None:
        confidence_delta = round(
            current.confidence_score - previous.confidence_score,
            2,
        )

    category_deltas = {
        category: round(
            current.score_breakdown[category]
            - previous.score_breakdown[category],
            2,
        )
        for category in CATEGORY_MAX_POINTS
        if category in previous.score_breakdown
        and category in current.score_breakdown
    }

    return AnalysisSnapshotComparison(
        previous_score=previous.alpha_score,
        current_score=current.alpha_score,
        score_delta=round(current.alpha_score - previous.alpha_score, 2),
        previous_confidence=previous.confidence_score,
        current_confidence=current.confidence_score,
        confidence_delta=confidence_delta,
        previous_grade=previous.grade,
        current_grade=current.grade,
        previous_decision=previous.decision,
        current_decision=current.decision,
        previous_methodology=previous.methodology_version,
        current_methodology=current.methodology_version,
        methodology_changed=(
            previous.methodology_version != current.methodology_version
        ),
        category_deltas=category_deltas,
    )


def attach_analysis_snapshot(
    audit: CompanyDataAudit,
    metrics: FinancialMetrics,
    score: ScoreBreakdown,
    confidence: AnalysisConfidence,
) -> CompanyDataAudit:
    return audit.model_copy(
        update={
            "alpha_score": score.total,
            "grade": score.grade,
            "decision": confidence.decision,
            "confidence_score": confidence.total,
            "confidence_status": confidence.status,
            "methodology_version": settings.scoring_methodology_version,
            "input_fingerprint": analysis_input_fingerprint(metrics),
            "score_breakdown": {
                category: getattr(score, category)
                for category in CATEGORY_MAX_POINTS
            },
        }
    )


def build_pdf_field_sources(
    financial_result: PdfExtractionResult,
    activity_result: ActivityReportExtractionResult | None,
    defaults: FinancialMetrics,
    submitted_values: dict[str, float | None],
) -> dict[str, MetricSourceType]:
    extracted = set(financial_result.extracted_fields)
    activity_fields = set(activity_result.sector_metrics) if activity_result else set()
    sources: dict[str, MetricSourceType] = {}

    for field, value in submitted_values.items():
        if value is None:
            continue
        if field in activity_fields:
            source = MetricSourceType.ACTIVITY_REPORT
        elif field in extracted:
            source = MetricSourceType.FINANCIAL_REPORT
        elif (
            field in FINANCIAL_METRIC_DEPENDENCIES
            and FINANCIAL_METRIC_DEPENDENCIES[field].issubset(extracted)
        ):
            source = MetricSourceType.FINANCIAL_REPORT
        else:
            source = MetricSourceType.MANUAL

        default_value = getattr(defaults, field, None)
        if (
            default_value is None
            or not isclose(float(value), float(default_value), rel_tol=1e-9, abs_tol=1e-6)
        ):
            source = MetricSourceType.MANUAL
        sources[field] = source

    return sources
