from collections.abc import Mapping, Sequence

from app.audit.models import CompanyDataAudit
from app.audit.service import verify_audit_calculations
from app.core.settings import settings
from app.data_quality.models import DataQualityRow, DataQualitySummary
from app.scoring.models import FinancialMetrics
from app.sector.profiles import CompanyProfile
from app.validation.service import validate_financial_metrics


FIELD_LABELS = {
    "revenue_growth": "Gelir büyümesi",
    "net_profit_growth": "Net kâr büyümesi",
    "net_margin": "Net kâr marjı",
    "roe": "ROE",
    "debt_to_equity": "Borç / özkaynak",
    "current_ratio": "Cari oran",
    "operating_cash_flow": "Operasyonel nakit akışı",
    "free_cash_flow": "Serbest nakit akışı",
    "asset_turnover": "Aktif devir hızı",
    "capital_adequacy_ratio": "Sermaye yeterliliği",
    "npl_ratio": "Takipteki kredi / alacak oranı",
    "loan_to_deposit_ratio": "Kredi / mevduat oranı",
    "net_interest_margin": "Net faiz marjı",
    "cost_income_ratio": "Maliyet / gelir oranı",
    "premium_growth": "Prim büyümesi",
    "combined_ratio": "Bileşik oran",
    "solvency_ratio": "Ödeme gücü / sermaye yeterliliği",
    "nav_discount": "Net aktif değer iskontosu",
    "occupancy_rate": "Doluluk oranı",
}


def _status(completeness: float, errors: list[str], warnings: list[str]) -> str:
    if errors:
        return "Hatalı"
    if completeness < 70:
        return "Eksik veri"
    if completeness < 100 or warnings:
        return "Kontrol gerekli"
    return "Doğrulandı"


def _calculation_check(
    audit: CompanyDataAudit | None,
) -> tuple[str, list[str], list[str]]:
    if audit is None:
        return "Kayıt yok", [], []
    if audit.methodology_version != settings.scoring_methodology_version:
        return "Eski metodoloji", [], []
    if not audit.source_values or not audit.metric_values:
        return "Kaynak izi yok", [], []

    checks = verify_audit_calculations(audit)
    if not checks:
        return "Uygulanamaz", [], []

    mismatches = [check for check in checks if not check.matches]
    if not mismatches:
        return "Doğrulandı", [], []

    fields = [FIELD_LABELS.get(check.field, check.field) for check in mismatches]
    errors = [
        f"{label}, ham tutarlardan yeniden hesaplanan değerle eşleşmiyor."
        for label in fields
    ]
    return "Uyuşmazlık", fields, errors


def build_data_quality_summary(
    companies: Sequence[FinancialMetrics],
    latest_audits: Mapping[str, CompanyDataAudit] | None = None,
) -> DataQualitySummary:
    audits = {
        symbol.upper(): audit for symbol, audit in (latest_audits or {}).items()
    }
    rows: list[DataQualityRow] = []
    for company in companies:
        report = validate_financial_metrics(company)
        calculation_status, mismatch_fields, calculation_errors = (
            _calculation_check(audits.get(company.symbol.upper()))
        )
        errors = [*report.errors, *calculation_errors]
        rows.append(
            DataQualityRow(
                symbol=company.symbol,
                company_name=company.company_name,
                company_profile=CompanyProfile(company.company_profile),
                completeness=report.completeness,
                status=_status(report.completeness, errors, report.warnings),
                missing_fields=[FIELD_LABELS.get(field, field) for field in report.missing_fields],
                warnings=report.warnings,
                errors=errors,
                calculation_check_status=calculation_status,
                calculation_mismatch_fields=mismatch_fields,
            )
        )

    priority = {"Hatalı": 0, "Eksik veri": 1, "Kontrol gerekli": 2, "Doğrulandı": 3}
    rows.sort(key=lambda row: (priority[row.status], row.completeness, row.symbol))
    return DataQualitySummary(
        rows=rows,
        total_companies=len(rows),
        verified_count=sum(row.status == "Doğrulandı" for row in rows),
        review_count=sum(row.status == "Kontrol gerekli" for row in rows),
        critical_count=sum(row.status in ("Hatalı", "Eksik veri") for row in rows),
        average_completeness=(round(sum(row.completeness for row in rows) / len(rows), 1) if rows else 0),
    )
