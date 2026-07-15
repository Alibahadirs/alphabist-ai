from math import isclose

from app.audit.models import MetricSourceType
from app.parser.models import (
    ActivityReportExtractionResult,
    PdfExtractionResult,
)
from app.scoring.models import FinancialMetrics


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
