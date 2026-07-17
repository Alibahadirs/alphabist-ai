from math import isclose

from app.audit.models import (
    CALCULATION_FORMULAS,
    CalculationCheck,
    CompanyDataAudit,
    MetricSourceType,
    SOURCE_VALUE_LABELS,
)
from app.core.settings import settings
from app.parser.converter import to_financial_metrics
from app.parser.models import FinancialReportDraft


def verify_audit_calculations(
    audit: CompanyDataAudit,
) -> list[CalculationCheck]:
    if (
        audit.methodology_version != settings.scoring_methodology_version
        or not audit.source_values
        or not audit.metric_values
    ):
        return []

    draft = FinancialReportDraft(
        symbol=audit.symbol,
        company_name=str(
            audit.metric_values.get("company_name") or audit.symbol
        ),
        company_profile=audit.company_profile,
        period_months=audit.period_months or 12,
        report_period_end=audit.report_period_end,
        **{
            field: audit.source_values.get(field)
            for field in SOURCE_VALUE_LABELS
        },
    )
    recalculated = to_financial_metrics(draft)
    verified_sources = {
        MetricSourceType.FINANCIAL_REPORT,
        MetricSourceType.SOURCE_CORRECTION,
    }
    checks: list[CalculationCheck] = []

    for field, formula in CALCULATION_FORMULAS.items():
        if audit.field_sources.get(field) not in verified_sources:
            continue
        stored = audit.metric_values.get(field)
        if isinstance(stored, str):
            continue
        calculated = getattr(recalculated, field)
        matches = (
            stored is None
            and calculated is None
            or stored is not None
            and calculated is not None
            and isclose(
                float(stored),
                float(calculated),
                rel_tol=1e-6,
                abs_tol=1e-6,
            )
        )
        checks.append(
            CalculationCheck(
                field=field,
                formula=formula,
                stored_value=stored,
                recalculated_value=calculated,
                matches=matches,
            )
        )

    return checks
