import hashlib
from datetime import date

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from app.analysis.service import build_company_analysis
from app.audit.models import (
    AnalysisSnapshotComparison,
    CompanyDataAudit,
    DataSourceType,
    METRIC_SOURCE_LABELS,
    SOURCE_VALUE_LABELS,
    MetricSourceType,
    SOURCE_LABELS,
)
from app.audit.service import (
    attach_analysis_snapshot,
    build_pdf_field_sources,
    build_source_value_snapshot,
    compare_analysis_snapshots,
    document_fingerprint,
    document_identity_conflicts,
    is_duplicate_analysis,
    verify_audit_calculations,
)
from app.comparison.service import build_comparison
from app.confidence.service import calculate_analysis_confidence
from app.core.constants import CATEGORY_MAX_POINTS
from app.core.exceptions import PdfParsingError, ValidationError as AppValidationError
from app.core.settings import settings
from app.database.repository import (
    add_company_data_audit,
    add_score_history,
    add_technical_score_history,
    get_company,
    get_latest_company_data_audit,
    list_companies,
    list_company_data_audits,
    list_document_usages,
    list_latest_company_data_audits,
    list_portfolio_positions,
    list_score_history,
    list_technical_score_history,
    list_watchlist_entries,
    remove_watchlist_entry,
    remove_portfolio_position,
    upsert_company,
    upsert_portfolio_position,
    upsert_watchlist_entry,
)
from app.database.backup import (
    create_database_backup,
    list_safety_backups,
    restore_database_backup,
    validate_database_backup,
)
from app.data_quality.service import FIELD_LABELS, build_data_quality_summary
from app.data_quality.readiness import (
    READINESS_STATUS_OPTIONS,
    build_decision_readiness_summary,
)
from app.market_data.provider import get_history, get_quote
from app.market_data.freshness import assess_price_freshness
from app.market_data.validation import validate_quote_history_alignment
from app.parser.converter import to_financial_metrics
from app.parser.extractor import (
    extract_activity_report,
    extract_financial_report,
    parse_turkish_number,
    rescale_monetary_values,
)
from app.parser.identity import company_names_match, validate_report_identity
from app.parser.models import (
    ActivityReportExtractionResult,
    FinancialReportDraft,
    PdfExtractionResult,
)
from app.portfolio.models import PortfolioMarketPrice, PortfolioPosition
from app.portfolio.service import build_portfolio_summary
from app.reporting.models import REPORT_FRESHNESS_LABELS, ReportFreshnessStatus
from app.reporting.service import assess_report_period, report_period_regresses
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.sector.profiles import CompanyProfile, PROFILE_LABELS
from app.scanner.models import ScannerFilters
from app.scanner.service import scan_companies
from app.technical.engine import calculate_combined_score, calculate_technical_score
from app.technical.models import (
    TechnicalRefreshSummary,
    TechnicalScoreBreakdown,
)
from app.technical.quality import (
    TECHNICAL_STATUS_OPTIONS,
    build_technical_quality_summary,
    select_technical_refresh_candidates,
)
from app.technical.refresh import (
    MAX_TECHNICAL_REFRESH_BATCH,
    refresh_technical_scores,
)
from app.watchlist.models import WatchlistEntry
from app.watchlist.service import build_watchlist_summary
from app.validation.service import (
    PROFILE_REQUIREMENTS,
    validate_financial_draft,
    validate_financial_metrics,
)


CATEGORY_LABELS = {
    "profitability": "Karlılık",
    "growth": "Büyüme",
    "leverage": "Borçluluk",
    "liquidity": "Likidite",
    "cash_flow": "Nakit akışı",
    "efficiency": "Verimlilik",
    "valuation": "Değerleme",
    "risk": "Risk dayanıklılığı",
    "management": "Yönetim",
}

TECHNICAL_LABELS = {
    "trend": ("Trend", 20),
    "moving_averages": ("Hareketli ortalamalar", 20),
    "rsi": ("RSI", 15),
    "macd": ("MACD", 15),
    "volume": ("Hacim", 15),
    "support_resistance": ("Destek / direnç", 15),
}

SCORE_INPUT_LABELS = {
    "valuation_score_input": "Değerleme girdisi",
    "management_score_input": "Yönetim girdisi",
    "risk_score_input": "Risk dayanıklılığı",
}

AMOUNT_METRIC_FIELDS = {
    "operating_cash_flow",
    "free_cash_flow",
}

PERCENT_METRIC_FIELDS = {
    "revenue_growth",
    "net_profit_growth",
    "net_margin",
    "roe",
    "capital_adequacy_ratio",
    "npl_ratio",
    "loan_to_deposit_ratio",
    "net_interest_margin",
    "cost_income_ratio",
    "premium_growth",
    "combined_ratio",
    "solvency_ratio",
    "nav_discount",
    "occupancy_rate",
}


@st.cache_data(show_spinner=False, max_entries=10)
def _parse_pdf(
    file_bytes: bytes,
    file_name: str = "",
    company_profile_override: CompanyProfile | None = None,
) -> PdfExtractionResult:
    return extract_financial_report(
        file_bytes,
        file_name,
        company_profile_override,
    )


@st.cache_data(show_spinner=False, max_entries=10)
def _parse_activity_pdf(
    file_bytes: bytes,
    file_name: str = "",
) -> ActivityReportExtractionResult:
    return extract_activity_report(file_bytes, file_name)


@st.cache_data(ttl="15m", max_entries=50, show_spinner=False)
def _load_market_data(symbol: str):
    return get_quote(symbol), get_history(symbol)


def _render_technical_refresh_summary(
    refresh_summary: TechnicalRefreshSummary,
) -> None:
    with st.container(horizontal=True):
        st.metric("Kaydedildi", refresh_summary.saved, border=True)
        st.metric("Değişmedi", refresh_summary.unchanged, border=True)
        st.metric("Reddedildi", refresh_summary.rejected, border=True)
        st.metric("Hata", refresh_summary.failed, border=True)
    with st.expander("Teknik güncelleme ayrıntıları"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Hisse": item.symbol,
                        "Durum": item.status,
                        "Fiyat tarihi": item.price_date,
                        "Teknik puan": item.technical_score,
                        "Açıklama": item.detail,
                    }
                    for item in refresh_summary.items
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Fiyat tarihi": st.column_config.DateColumn(
                    "Fiyat tarihi",
                    format="DD.MM.YYYY",
                ),
                "Teknik puan": st.column_config.NumberColumn(
                    format="%.1f"
                ),
            },
        )


@st.cache_data(ttl="15m", max_entries=100, show_spinner=False)
def _load_quote(symbol: str):
    return get_quote(symbol)


def _quote_date(quote: dict) -> date | None:
    value = quote.get("as_of_date")
    return date.fromisoformat(str(value)) if value else None


def _score_table(score: ScoreBreakdown) -> pd.DataFrame:
    rows = []
    for category, maximum in CATEGORY_MAX_POINTS.items():
        rows.append(
            {
                "Kategori": CATEGORY_LABELS[category],
                "Puan": getattr(score, category),
                "Maksimum": maximum,
            }
        )
    return pd.DataFrame(rows)


def _analysis_table(company: FinancialMetrics, score: ScoreBreakdown) -> pd.DataFrame:
    analysis = build_company_analysis(company, score)
    return pd.DataFrame(
        [
            {
                "Gösterge": item.label,
                "Değer": (
                    "Eksik"
                    if item.value is None
                    else f"{item.value:,.2f} {item.unit}".replace(",", "X").replace(".", ",").replace("X", ".")
                ),
                "Durum": item.status,
                "Açıklama": item.interpretation,
            }
            for item in analysis.indicators
        ]
    )


def _technical_score_table(score: TechnicalScoreBreakdown) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Kriter": label,
                "Puan": getattr(score, field),
                "Maksimum": maximum,
            }
            for field, (label, maximum) in TECHNICAL_LABELS.items()
        ]
    )


def _format_turkish_amount(value: float | None) -> str:
    if value is None:
        return "-"
    decimals = 0 if float(value).is_integer() else 2
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_metric_snapshot_value(
    field: str,
    value: float | str | None,
) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    if field in AMOUNT_METRIC_FIELDS:
        return f"{_format_turkish_amount(value)} TL"
    formatted = (
        f"{float(value):,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )
    if field in PERCENT_METRIC_FIELDS:
        return f"%{formatted}"
    if field in SCORE_INPUT_LABELS:
        return f"{float(value):.0f}/100"
    return formatted


def _amount_input(label: str, value: float | None, key: str) -> str:
    return st.text_input(
        f"{label} (TL)",
        value="" if value is None else _format_turkish_amount(value),
        key=key,
        help="Tutarı TL olarak girin. Binlik ayırıcı olarak nokta kullanabilirsiniz.",
    )


def _parse_amount_input(label: str, raw_value: str) -> float | None:
    if not raw_value.strip():
        return None
    try:
        return parse_turkish_number(raw_value)
    except ValueError as exc:
        raise AppValidationError(f"{label} geçerli bir TL tutarı değil.") from exc


PDF_SOURCE_FIELD_LABELS = SOURCE_VALUE_LABELS

BASE_PDF_SOURCE_FIELDS = (
    "revenue",
    "previous_revenue",
    "net_profit",
    "previous_net_profit",
    "equity",
    "previous_equity",
    "cash",
    "total_assets",
    "previous_total_assets",
)

OPERATING_PDF_SOURCE_FIELDS = (
    "total_debt",
    "current_assets",
    "current_liabilities",
    "operating_cash_flow",
    "capital_expenditures",
)


def _pdf_source_fields(profile: CompanyProfile) -> tuple[str, ...]:
    fields = list(BASE_PDF_SOURCE_FIELDS)
    if profile in (
        CompanyProfile.STANDARD,
        CompanyProfile.REIT,
        CompanyProfile.FINANCIAL_SERVICES,
    ):
        fields.extend(OPERATING_PDF_SOURCE_FIELDS)
    if profile == CompanyProfile.INSURANCE:
        fields.extend(("premium_revenue", "previous_premium_revenue"))
    return tuple(fields)


def _render_pdf_source_editor(
    draft: FinancialReportDraft,
    profile: CompanyProfile,
) -> tuple[FinancialReportDraft, set[str], list[str]]:
    fields = _pdf_source_fields(profile)
    corrected_fields: set[str] = set()
    input_errors: list[str] = []
    updates: dict[str, float | None] = {}

    with st.expander("PDF kaynak tutarlarını kontrol et ve düzelt"):
        st.caption(
            "Tutarlar TL biçimindedir. Yanlış okunan değeri düzelttiğinizde "
            "oranlar otomatik olarak yeniden hesaplanır."
        )
        left, right = st.columns(2)
        for index, field in enumerate(fields):
            label = PDF_SOURCE_FIELD_LABELS[field]
            original_value = getattr(draft, field)
            target = left if index % 2 == 0 else right
            with target:
                raw_value = _amount_input(
                    label,
                    original_value,
                    key=f"pdf_source_{field}",
                )
            try:
                parsed_value = _parse_amount_input(label, raw_value)
            except AppValidationError as exc:
                input_errors.append(str(exc))
                parsed_value = original_value
            updates[field] = parsed_value
            if parsed_value != original_value:
                corrected_fields.add(field)

        if corrected_fields:
            corrected_labels = ", ".join(
                PDF_SOURCE_FIELD_LABELS[field]
                for field in fields
                if field in corrected_fields
            )
            st.info(f"Kullanıcı tarafından düzeltilen kalemler: {corrected_labels}")

    return draft.model_copy(update=updates), corrected_fields, input_errors


def _profile_select(label: str, value: CompanyProfile, key: str) -> CompanyProfile:
    profiles = list(CompanyProfile)
    return st.selectbox(
        label,
        profiles,
        index=profiles.index(CompanyProfile(value)),
        format_func=lambda item: PROFILE_LABELS[item],
        key=key,
        help="PDF'den otomatik algılanır; rapor yapısı farklıysa değiştirebilirsiniz.",
    )


def _sector_inputs(profile: CompanyProfile, key_prefix: str, defaults: FinancialMetrics | None = None) -> dict[str, float | None]:
    def default(name: str, fallback: float) -> float | None:
        value = getattr(defaults, name, None) if defaults else None
        if defaults is not None and value is None:
            return None
        return float(fallback if value is None else value)

    if profile == CompanyProfile.BANK:
        st.subheader("Bankaya özgü göstergeler")
        left, right = st.columns(2)
        with left:
            capital = st.number_input("Sermaye yeterliliği (%)", value=default("capital_adequacy_ratio", 15), step=0.1, key=f"{key_prefix}_car")
            npl = st.number_input("Takipteki kredi oranı (%)", value=default("npl_ratio", 3), min_value=0.0, step=0.1, key=f"{key_prefix}_npl")
            loan_deposit = st.number_input("Kredi / mevduat (%)", value=default("loan_to_deposit_ratio", 100), min_value=0.0, step=0.1, key=f"{key_prefix}_ldr")
        with right:
            margin = st.number_input("Net faiz marjı (%)", value=default("net_interest_margin", 4), step=0.1, key=f"{key_prefix}_nim")
            cost_income = st.number_input("Maliyet / gelir (%)", value=default("cost_income_ratio", 50), min_value=0.0, step=0.1, key=f"{key_prefix}_cir")
        return {"capital_adequacy_ratio": capital, "npl_ratio": npl, "loan_to_deposit_ratio": loan_deposit, "net_interest_margin": margin, "cost_income_ratio": cost_income}
    if profile == CompanyProfile.INSURANCE:
        st.subheader("Sigortaya özgü göstergeler")
        left, right = st.columns(2)
        with left:
            premium = st.number_input("Prim büyümesi (%)", value=default("premium_growth", 10), step=0.1, key=f"{key_prefix}_premium")
            combined = st.number_input("Bileşik oran (%)", value=default("combined_ratio", 100), min_value=0.0, step=0.1, key=f"{key_prefix}_combined")
        with right:
            solvency = st.number_input("Sermaye yeterliliği / ödeme gücü (%)", value=default("solvency_ratio", 130), min_value=0.0, step=0.1, key=f"{key_prefix}_solvency")
        return {"premium_growth": premium, "combined_ratio": combined, "solvency_ratio": solvency}
    if profile == CompanyProfile.REIT:
        st.subheader("GYO'ya özgü göstergeler")
        left, right = st.columns(2)
        with left:
            nav = st.number_input("Net aktif değer iskontosu (%)", value=default("nav_discount", 0), step=0.1, key=f"{key_prefix}_nav")
        with right:
            occupancy = st.number_input("Doluluk oranı (%)", value=default("occupancy_rate", 0), min_value=0.0, max_value=100.0, step=0.1, key=f"{key_prefix}_occupancy")
        return {"nav_discount": nav, "occupancy_rate": occupancy}
    if profile == CompanyProfile.FINANCIAL_SERVICES:
        st.subheader("Finansal hizmet göstergeleri")
        left, right = st.columns(2)
        with left:
            capital = st.number_input("Sermaye yeterliliği (%)", value=default("capital_adequacy_ratio", 15), step=0.1, key=f"{key_prefix}_car")
            npl = st.number_input("Takipteki alacak oranı (%)", value=default("npl_ratio", 3), min_value=0.0, step=0.1, key=f"{key_prefix}_npl")
        with right:
            cost_income = st.number_input("Maliyet / gelir (%)", value=default("cost_income_ratio", 50), min_value=0.0, step=0.1, key=f"{key_prefix}_cir")
        return {"capital_adequacy_ratio": capital, "npl_ratio": npl, "cost_income_ratio": cost_income}
    return {}


def _audit_source_label(audit: CompanyDataAudit | None) -> str:
    if audit is None:
        return SOURCE_LABELS[DataSourceType.LEGACY]
    return SOURCE_LABELS[audit.source_type]


def _audit_period_label(audit: CompanyDataAudit | None) -> str:
    if audit is None or audit.period_months is None:
        return "Belirtilmemiş"
    label = f"{audit.period_months} aylık"
    if audit.report_period_end:
        label = f"{audit.report_period_end:%d.%m.%Y} · {label}"
    return label


def _audit_date(audit: CompanyDataAudit | None):
    return audit.created_at if audit else None


def _monetary_scale_label(scale: float) -> str:
    labels = {
        1.0: "TL",
        1_000.0: "bin TL",
        1_000_000.0: "milyon TL",
    }
    return labels.get(scale, f"{scale:g} × TL")


def _render_data_source_caption(audit: CompanyDataAudit | None) -> None:
    if audit is None:
        st.caption("Veri kaynağı: belirtilmemiş (eski kayıt)")
        return

    details = [
        f"Veri kaynağı: {SOURCE_LABELS[audit.source_type]}",
        f"Rapor dönemi: {_audit_period_label(audit)}",
    ]
    if audit.created_at:
        details.append(f"Kayıt: {audit.created_at:%d.%m.%Y %H:%M}")
    st.caption(" | ".join(details))

    reports = [
        name
        for name in (audit.financial_report_name, audit.activity_report_name)
        if name
    ]
    if reports:
        st.caption("Raporlar: " + " | ".join(reports))

    document_ids = []
    if audit.financial_report_hash:
        document_ids.append(
            f"Finansal belge: {audit.financial_report_hash[:10]}"
        )
    if audit.activity_report_hash:
        document_ids.append(
            f"Faaliyet belgesi: {audit.activity_report_hash[:10]}"
        )
    if document_ids:
        st.caption("Belge kimlikleri: " + " | ".join(document_ids))
    if audit.financial_report_name:
        st.caption(
            "Finansal rapor sunum birimi: "
            + _monetary_scale_label(audit.financial_report_scale)
        )
        comparison_label = (
            f"{audit.comparison_period_end:%d.%m.%Y}"
            if audit.comparison_period_end
            else "kullanıcı tarafından kontrol edildi"
            if audit.comparison_period_confirmed
            else "doğrulanmadı"
        )
        st.caption("Büyüme karşılaştırma dönemi: " + comparison_label)

    if audit.field_sources:
        with st.expander("Son puanın gösterge kaynakları"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Gösterge": FIELD_LABELS.get(
                                field, SCORE_INPUT_LABELS.get(field, field)
                            ),
                            "Değer": _format_metric_snapshot_value(
                                field,
                                audit.metric_values.get(field),
                            ),
                            "Kaynak": METRIC_SOURCE_LABELS[source],
                        }
                        for field, source in audit.field_sources.items()
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    if audit.source_values:
        with st.expander("Hesaplamada kullanılan ham finansal tutarlar"):
            st.caption(
                "Bu değerler analiz kaydedildiği anda dondurulmuştur. Oranlar "
                "ve büyüme hesapları bu kaynak tutarlardan üretilmiştir."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Finansal kalem": label,
                            "Tutar (TL)": _format_turkish_amount(
                                audit.source_values[field]
                            ),
                        }
                        for field, label in SOURCE_VALUE_LABELS.items()
                        if field in audit.source_values
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    calculation_checks = verify_audit_calculations(audit)
    if calculation_checks:
        with st.expander("Finansal hesaplama doğrulaması"):
            if all(check.matches for check in calculation_checks):
                st.success(
                    "Kaydedilmiş göstergeler ham tutarlardan yeniden "
                    "hesaplandığında aynı sonuçlar elde edildi."
                )
            else:
                st.warning(
                    "Bazı göstergeler güncel formülle yeniden hesaplandığında "
                    "kaydedilmiş değerle eşleşmiyor."
                )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Gösterge": FIELD_LABELS.get(
                                check.field,
                                check.field,
                            ),
                            "Formül": check.formula,
                            "Kaydedilen": _format_metric_snapshot_value(
                                check.field,
                                check.stored_value,
                            ),
                            "Yeniden hesaplanan": _format_metric_snapshot_value(
                                check.field,
                                check.recalculated_value,
                            ),
                            "Durum": (
                                "Eşleşiyor"
                                if check.matches
                                else "Kontrol gerekli"
                            ),
                        }
                        for check in calculation_checks
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    elif (
        audit.source_values
        and audit.metric_values
        and audit.methodology_version != settings.scoring_methodology_version
    ):
        st.caption(
            "Hesaplama doğrulaması bu kaydın eski metodoloji sürümüne ait "
            "olması nedeniyle uygulanmadı."
        )


def _render_snapshot_comparison(
    comparison: AnalysisSnapshotComparison,
    previous: CompanyDataAudit,
    current: CompanyDataAudit,
) -> None:
    with st.container(border=True):
        st.subheader("Son analize göre değişim")
        with st.container(horizontal=True):
            st.metric(
                "Alpha Score",
                f"{comparison.current_score:.1f}/100",
                f"{comparison.score_delta:+.1f}",
                border=True,
            )
            st.metric(
                "Analiz güveni",
                (
                    f"{comparison.current_confidence:.1f}/100"
                    if comparison.current_confidence is not None
                    else "-"
                ),
                (
                    f"{comparison.confidence_delta:+.1f}"
                    if comparison.confidence_delta is not None
                    else None
                ),
                border=True,
            )
            st.metric(
                "Not",
                comparison.current_grade or "-",
                (
                    f"Önceki: {comparison.previous_grade or '-'}"
                    if comparison.current_grade != comparison.previous_grade
                    else "Değişmedi"
                ),
                delta_color="off",
                border=True,
            )
            st.metric(
                "Karar",
                comparison.current_decision or "-",
                (
                    f"Önceki: {comparison.previous_decision or '-'}"
                    if comparison.current_decision != comparison.previous_decision
                    else "Değişmedi"
                ),
                delta_color="off",
                border=True,
            )

        if comparison.methodology_changed:
            st.warning(
                "Puanlama metodolojisi değişmiş: "
                f"{comparison.previous_methodology} → "
                f"{comparison.current_methodology}. Puan farkının bir bölümü "
                "metodoloji değişikliğinden kaynaklanabilir."
            )

        if comparison.category_deltas:
            rows = []
            for category in CATEGORY_MAX_POINTS:
                if category not in comparison.category_deltas:
                    continue
                delta = comparison.category_deltas[category]
                rows.append(
                    {
                        "Kategori": CATEGORY_LABELS[category],
                        "Önceki": previous.score_breakdown[category],
                        "Güncel": current.score_breakdown[category],
                        "Değişim": delta,
                        "Yön": (
                            "Arttı"
                            if delta > 0
                            else "Azaldı" if delta < 0 else "Değişmedi"
                        ),
                    }
                )
            st.dataframe(
                pd.DataFrame(rows),
                hide_index=True,
                width="stretch",
                column_config={
                    "Önceki": st.column_config.NumberColumn(format="%.2f"),
                    "Güncel": st.column_config.NumberColumn(format="%.2f"),
                    "Değişim": st.column_config.NumberColumn(format="%+.2f"),
                },
            )
        else:
            st.caption(
                "Eski analizde kategori kırılımı bulunmadığı için yalnız toplam "
                "puan ve güven değişimi karşılaştırıldı."
            )


def render_dashboard() -> None:
    st.title("Genel bakış")
    st.caption("Finansal kalite puanı ve gecikmeli piyasa görünümü")

    companies = list_companies()
    if not companies:
        st.info("Analize başlamak için önce bir şirket ekleyin.")
        return

    symbol = st.selectbox(
        "Şirket seç",
        [company.symbol for company in companies],
    )
    company = get_company(symbol)
    if company is None:
        st.error("Seçilen şirket kaydı bulunamadı.")
        return

    score = calculate_alpha_score(company)
    latest_audit = get_latest_company_data_audit(symbol)
    confidence = calculate_analysis_confidence(company, score, latest_audit)
    audit_history = list_company_data_audits(symbol)
    score_history = list_score_history(symbol)
    snapshot_comparison = None
    if len(audit_history) >= 2:
        snapshot_comparison = compare_analysis_snapshots(
            audit_history[-2],
            audit_history[-1],
        )
    score_delta = None
    if snapshot_comparison is not None:
        score_delta = snapshot_comparison.score_delta
    elif len(score_history) >= 2:
        score_delta = score_history[-1].total_score - score_history[-2].total_score

    with st.container(horizontal=True):
        st.metric(
            "Alpha Score",
            f"{score.total:.1f}/100",
            f"{score_delta:+.1f}" if score_delta is not None else None,
            border=True,
            chart_data=[entry.total_score for entry in score_history] or None,
            chart_type="line",
        )
        st.metric("Not", score.grade, border=True)
        st.metric("Karar", confidence.decision, border=True)
        st.metric(
            f"Analiz güveni · {confidence.status}",
            f"{confidence.total:.1f}/100",
            border=True,
        )
        st.metric("Hisse", company.symbol, border=True)

    st.caption(
        f"Profil: {PROFILE_LABELS[CompanyProfile(company.company_profile)]} | "
        f"Veri yeterliliği: %{score.data_completeness:.0f} | "
        f"Karar hazırlığı: "
        f"{'Hazır' if confidence.decision_ready else 'Doğrulama gerekli'}"
    )
    _render_data_source_caption(latest_audit)
    with st.expander("Analiz güveni ayrıntıları"):
        st.caption(
            f"Hesap kontrolü: {confidence.calculation_check_status}"
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {"Bileşen": "Zorunlu veri yeterliliği", "Puan": confidence.completeness_component, "Maksimum": 55},
                    {"Bileşen": "Gösterge kaynak kapsamı", "Puan": confidence.source_component, "Maksimum": 25},
                    {"Bileşen": "Rapor / kayıt kanıtı", "Puan": confidence.report_component, "Maksimum": 10},
                    {"Bileşen": "Rapor dönemi", "Puan": confidence.period_component, "Maksimum": 5},
                    {"Bileşen": "Doğrulama sağlığı", "Puan": confidence.validation_component, "Maksimum": 5},
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Puan": st.column_config.NumberColumn(format="%.1f"),
                "Maksimum": st.column_config.NumberColumn(format="%.0f"),
            },
        )
        for reason in confidence.reasons:
            st.markdown(f"- {reason}")
    if snapshot_comparison is not None:
        _render_snapshot_comparison(
            snapshot_comparison,
            audit_history[-2],
            audit_history[-1],
        )
    for warning in score.validation_warnings:
        st.warning(warning)

    with st.container(border=True):
        st.subheader(company.company_name)
        st.dataframe(
            _score_table(score),
            hide_index=True,
            width="stretch",
            column_config={
                "Puan": st.column_config.ProgressColumn(
                    "Puan",
                    min_value=0,
                    max_value=15,
                    format="%.2f",
                ),
                "Maksimum": st.column_config.NumberColumn(format="%.0f"),
            },
        )

    if audit_history:
        with st.expander("Veri kaynağı ve puan geçmişi"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Tarih": audit.created_at,
                            "Kaynak": SOURCE_LABELS[audit.source_type],
                            "Dönem": _audit_period_label(audit),
                            "Dönem sonu": audit.report_period_end,
                            "Finansal rapor": audit.financial_report_name or "-",
                            "Faaliyet raporu": audit.activity_report_name or "-",
                            "Finansal belge kimliği": (
                                audit.financial_report_hash[:10]
                                if audit.financial_report_hash
                                else "-"
                            ),
                            "Faaliyet belge kimliği": (
                                audit.activity_report_hash[:10]
                                if audit.activity_report_hash
                                else "-"
                            ),
                            "Rapor sunum birimi": _monetary_scale_label(
                                audit.financial_report_scale
                            ),
                            "Karşılaştırma dönemi": audit.comparison_period_end,
                            "Karşılaştırma doğrulandı": (
                                audit.comparison_period_confirmed
                            ),
                            "Yeterlilik (%)": audit.completeness,
                            "Alpha Score": audit.alpha_score,
                            "Not": audit.grade or "-",
                            "Karar": audit.decision or "-",
                            "Analiz güveni (%)": audit.confidence_score,
                            "Güven durumu": audit.confidence_status or "-",
                            "Metodoloji": audit.methodology_version,
                            "Analiz kimliği": (
                                audit.input_fingerprint[:10]
                                if audit.input_fingerprint
                                else "-"
                            ),
                            **{
                                CATEGORY_LABELS[category]: audit.score_breakdown.get(
                                    category
                                )
                                for category in CATEGORY_MAX_POINTS
                            },
                        }
                        for audit in reversed(audit_history)
                    ]
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    "Tarih": st.column_config.DatetimeColumn(
                        "Tarih", format="DD.MM.YYYY HH:mm"
                    ),
                    "Dönem sonu": st.column_config.DateColumn(
                        "Dönem sonu", format="DD.MM.YYYY"
                    ),
                    "Yeterlilik (%)": st.column_config.ProgressColumn(
                        "Yeterlilik (%)", min_value=0, max_value=100, format="%.1f"
                    ),
                    "Alpha Score": st.column_config.NumberColumn(format="%.1f"),
                    "Analiz güveni (%)": st.column_config.ProgressColumn(
                        "Analiz güveni (%)", min_value=0, max_value=100, format="%.1f"
                    ),
                },
            )

    analysis = build_company_analysis(company, score)
    with st.container(border=True):
        st.subheader("Analiz ve doğrulama")
        st.write(analysis.summary)
        st.dataframe(
            _analysis_table(company, score),
            hide_index=True,
            width="stretch",
            column_config={
                "Gösterge": st.column_config.TextColumn(pinned=True),
                "Durum": st.column_config.TextColumn(width="small"),
            },
        )
        strengths_col, risks_col = st.columns(2)
        with strengths_col:
            st.markdown("**Güçlü yönler**")
            if analysis.strengths:
                for item in analysis.strengths:
                    st.markdown(f"- {item}")
            else:
                st.caption("Doğrulanmış güçlü gösterge bulunamadı.")
        with risks_col:
            st.markdown("**Riskler ve eksikler**")
            if analysis.risks:
                for item in analysis.risks:
                    st.markdown(f"- {item}")
            else:
                st.caption("Belirgin risk veya eksik gösterge bulunamadı.")

    if score_history:
        with st.container(border=True):
            st.subheader("Alpha Score geçmişi")
            history_frame = pd.DataFrame(
                [
                    {
                        "Tarih": entry.created_at,
                        "Alpha Score": entry.total_score,
                    }
                    for entry in score_history
                ]
            )
            st.line_chart(
                history_frame,
                x="Tarih",
                y="Alpha Score",
                y_label="Puan",
            )
            st.caption(f"Son {len(score_history)} kayıt gösteriliyor.")

    st.subheader("Piyasa görünümü")
    try:
        with st.spinner("Piyasa verisi ve teknik göstergeler hesaplanıyor..."):
            quote, history = _load_market_data(symbol)
            quote_date = _quote_date(quote)
            quote_freshness = assess_price_freshness(quote_date)
            market_alignment = validate_quote_history_alignment(
                quote,
                history,
            )
            market_data_ready = (
                quote_freshness.current and market_alignment.valid
            )
            technical_score = calculate_technical_score(history)
            if market_data_ready and quote_date is not None:
                add_technical_score_history(
                    symbol=symbol,
                    price_date=quote_date,
                    source=str(quote.get("source") or "Bilinmiyor"),
                    score=technical_score,
                    alignment_status=market_alignment.status,
                    methodology_version=(
                        settings.technical_methodology_version
                    ),
                )
            combined_score = calculate_combined_score(
                score.total,
                technical_score.total,
            )

        with st.container(horizontal=True):
            st.metric(
                "Son fiyat",
                f"{quote['last']:,.2f} TRY",
                f"{quote['change_percent'] or 0:.2f}%",
                border=True,
            )
            st.metric(
                "Teknik puan",
                f"{technical_score.total:.1f}/100",
                (
                    technical_score.signal
                    if market_data_ready
                    else "Veri doğrulanmalı"
                ),
                border=True,
            )
            st.metric(
                "Birleşik AI puanı",
                f"{combined_score:.1f}/100",
                (
                    "Temel %70 + teknik %30"
                    if market_data_ready
                    else "Doğrulama gerekli"
                ),
                border=True,
            )
            st.metric(
                "ATR oynaklığı",
                f"%{technical_score.atr_percent:.2f}",
                border=True,
            )
        st.caption(
            f"Kaynak: {quote.get('source') or 'Bilinmiyor'} | "
            "Fiyat tarihi: "
            f"{quote_date.strftime('%d.%m.%Y') if quote_date else '-'} | "
            f"Durum: {quote_freshness.status} | "
            f"Fiyat-grafik kontrolü: {market_alignment.status}"
        )
        if not market_data_ready:
            st.warning(
                "Teknik puan ve birleşik AI puanı güncelliği veya grafik "
                "uyumu doğrulanamayan piyasa verisine dayanıyor."
            )

        st.line_chart(history[["Close", "EMA_20", "EMA_50", "EMA_200"]])
        latest = history.iloc[-1]
        indicator_col, macd_col, signal_col = st.columns(3)
        indicator_col.metric("RSI 14", f"{float(latest['RSI_14']):.2f}")
        macd_col.metric("MACD", f"{float(latest['MACD']):.4f}")
        signal_col.metric(
            "MACD sinyal",
            f"{float(latest['MACD_SIGNAL']):.4f}",
        )

        with st.container(border=True):
            st.subheader("Teknik puan kırılımı")
            st.dataframe(
                _technical_score_table(technical_score),
                hide_index=True,
                width="stretch",
                column_config={
                    "Puan": st.column_config.ProgressColumn(
                        "Puan",
                        min_value=0,
                        max_value=20,
                        format="%.2f",
                    ),
                    "Maksimum": st.column_config.NumberColumn(format="%.0f"),
                },
            )

        technical_history = list_technical_score_history(symbol)
        if technical_history:
            history_frame = pd.DataFrame(
                [
                    {
                        "Fiyat tarihi": entry.price_date,
                        "Teknik puan": entry.total_score,
                        "Sinyal": entry.signal,
                        "RSI": entry.rsi_value,
                        "ATR (%)": entry.atr_percent,
                        "Kaynak": entry.source,
                        "Veri kontrolü": entry.alignment_status,
                        "Metodoloji": entry.methodology_version,
                    }
                    for entry in technical_history
                ]
            )
            with st.container(border=True):
                st.subheader("Doğrulanmış teknik puan geçmişi")
                st.line_chart(
                    history_frame,
                    x="Fiyat tarihi",
                    y="Teknik puan",
                    y_label="Puan",
                )
                st.dataframe(
                    history_frame,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Fiyat tarihi": st.column_config.DateColumn(
                            "Fiyat tarihi",
                            format="DD.MM.YYYY",
                        ),
                        "Teknik puan": st.column_config.ProgressColumn(
                            "Teknik puan",
                            min_value=0,
                            max_value=100,
                            format="%.1f",
                        ),
                        "RSI": st.column_config.NumberColumn(
                            format="%.2f"
                        ),
                        "ATR (%)": st.column_config.NumberColumn(
                            format="%.2f"
                        ),
                    },
                )
    except Exception as exc:
        st.warning(f"Piyasa verisi alınamadı: {exc}")


def _render_quality_correction_form() -> None:
    companies = {company.symbol: company for company in list_companies()}
    if not companies:
        return
    st.subheader("Eksik veya hatalı veriyi düzelt")
    symbol = st.selectbox("Düzeltilecek şirket", list(companies), key="quality_symbol")
    company = companies[symbol]
    profile = _profile_select(
        "Doğru sektör profili",
        CompanyProfile(company.company_profile),
        f"quality_profile_{symbol}",
    )
    required_fields = PROFILE_REQUIREMENTS[profile]
    amount_fields = {"operating_cash_flow", "free_cash_flow"}
    nonnegative_fields = {
        "debt_to_equity", "current_ratio", "asset_turnover",
        "capital_adequacy_ratio", "npl_ratio", "loan_to_deposit_ratio",
        "cost_income_ratio", "combined_ratio", "solvency_ratio", "occupancy_rate",
    }

    with st.form(f"quality_correction_{symbol}_{profile.value}", border=True):
        st.caption(
            f"{PROFILE_LABELS[profile]} puanlamasında kullanılan göstergeler. "
            "Değerleri resmi rapordan doğrulayarak girin."
        )
        columns = st.columns(2)
        raw_values: dict[str, float | str | None] = {}
        for index, field in enumerate(required_fields):
            current = getattr(company, field)
            label = FIELD_LABELS.get(field, field)
            with columns[index % 2]:
                if field in amount_fields:
                    raw_values[field] = _amount_input(
                        label, current, key=f"quality_{symbol}_{field}"
                    )
                else:
                    kwargs = {
                        "label": f"{label} ({'oran' if field in {'debt_to_equity', 'current_ratio', 'asset_turnover'} else '%'})",
                        "value": float(current) if current is not None else None,
                        "step": 0.1,
                        "format": "%.2f",
                        "key": f"quality_{symbol}_{field}",
                    }
                    if field in nonnegative_fields:
                        kwargs["min_value"] = 0.0
                    if field == "occupancy_rate":
                        kwargs["max_value"] = 100.0
                    raw_values[field] = st.number_input(**kwargs)
        submitted = st.form_submit_button(
            "Doğrula ve kaydet",
            type="primary",
            icon=":material/fact_check:",
        )

    if not submitted:
        return
    updates: dict[str, float | None | CompanyProfile] = {"company_profile": profile}
    try:
        for field, value in raw_values.items():
            if field in amount_fields:
                updates[field] = _parse_amount_input(FIELD_LABELS[field], str(value))
            else:
                updates[field] = value
    except AppValidationError as exc:
        st.error(str(exc))
        return

    corrected = company.model_copy(update=updates)
    validation = validate_financial_metrics(corrected)
    if validation.errors:
        for error in validation.errors:
            st.error(error)
        return
    previous_audit = get_latest_company_data_audit(corrected.symbol)
    previous_period_end = (
        previous_audit.report_period_end if previous_audit else None
    )
    if is_duplicate_analysis(previous_audit, corrected, previous_period_end):
        st.info(
            "Bu dönem ve finansal girdiler son analizle aynı. Puan geçmişine "
            "yinelenen kayıt eklenmedi."
        )
        return
    upsert_company(corrected)
    score = calculate_alpha_score(corrected)
    add_score_history(corrected.symbol, score)
    corrected_sources = dict(previous_audit.field_sources) if previous_audit else {}
    corrected_sources.update(
        {field: MetricSourceType.CORRECTION for field in required_fields}
    )
    audit = CompanyDataAudit(
        symbol=corrected.symbol,
        source_type=DataSourceType.CORRECTION,
        company_profile=profile,
        period_months=previous_audit.period_months if previous_audit else None,
        report_period_end=(
            previous_audit.report_period_end if previous_audit else None
        ),
        financial_report_name=(
            previous_audit.financial_report_name if previous_audit else ""
        ),
        activity_report_name=(
            previous_audit.activity_report_name if previous_audit else ""
        ),
        financial_report_hash=(
            previous_audit.financial_report_hash if previous_audit else ""
        ),
        activity_report_hash=(
            previous_audit.activity_report_hash if previous_audit else ""
        ),
        financial_report_scale=(
            previous_audit.financial_report_scale if previous_audit else 1
        ),
        comparison_period_end=(
            previous_audit.comparison_period_end if previous_audit else None
        ),
        comparison_period_confirmed=(
            previous_audit.comparison_period_confirmed
            if previous_audit
            else False
        ),
        completeness=validation.completeness,
        alpha_score=score.total,
        field_sources=corrected_sources,
        source_values=(
            dict(previous_audit.source_values)
            if previous_audit
            else {}
        ),
    )
    confidence = calculate_analysis_confidence(corrected, score, audit)
    add_company_data_audit(
        attach_analysis_snapshot(audit, corrected, score, confidence)
    )
    for warning in validation.warnings:
        st.warning(warning)
    st.success(
        f"{corrected.symbol} doğrulandı ve kaydedildi. Veri yeterliliği "
        f"%{validation.completeness:.1f}, Alpha Score {score.total:.1f}/100."
    )


def render_data_quality() -> None:
    st.title("Veri kalite merkezi")
    st.caption(
        "Puanların dayandığı finansal göstergelerin sektör bazında yeterliliğini "
        "ve doğrulama durumunu izleyin."
    )
    companies = list_companies()
    latest_audits = {
        audit.symbol: audit for audit in list_latest_company_data_audits()
    }
    summary = build_data_quality_summary(companies, latest_audits)
    technical_quality = build_technical_quality_summary(
        [company.symbol for company in companies],
        {
            company.symbol: list_technical_score_history(company.symbol)
            for company in companies
        },
    )
    technical_by_symbol = {
        row.symbol: row for row in technical_quality.rows
    }
    confidences = {
        company.symbol: calculate_analysis_confidence(
            company,
            calculate_alpha_score(company),
            latest_audits.get(company.symbol),
        )
        for company in companies
    }
    readiness_summary = build_decision_readiness_summary(
        companies,
        confidences,
        technical_quality,
    )
    readiness_by_symbol = {
        row.symbol: row for row in readiness_summary.rows
    }
    freshness = {
        company.symbol: assess_report_period(
            latest_audits[company.symbol].report_period_end,
            latest_audits[company.symbol].period_months,
        )
        if company.symbol in latest_audits
        else assess_report_period(None, None)
        for company in companies
    }
    if not summary.rows:
        st.info("Kontrol edilecek şirket kaydı bulunmuyor.")
        return

    with st.container(horizontal=True):
        st.metric("Toplam şirket", summary.total_companies, border=True)
        st.metric("Doğrulandı", summary.verified_count, border=True)
        st.metric("Kontrol gerekli", summary.review_count, border=True)
        st.metric("Kritik / eksik", summary.critical_count, border=True)
        st.metric("Ortalama yeterlilik", f"%{summary.average_completeness:.1f}", border=True)

    with st.container(horizontal=True):
        st.metric(
            "Güncel rapor",
            sum(
                item.status == ReportFreshnessStatus.CURRENT
                for item in freshness.values()
            ),
            border=True,
        )
        st.metric(
            "Eskimekte",
            sum(
                item.status == ReportFreshnessStatus.AGING
                for item in freshness.values()
            ),
            border=True,
        )
        st.metric(
            "Güncelleme gerekli",
            sum(item.blocks_decision for item in freshness.values()),
            border=True,
        )
        st.metric(
            "Tarih eksik",
            sum(
                item.status == ReportFreshnessStatus.UNKNOWN
                for item in freshness.values()
            ),
            border=True,
        )
        st.metric(
            "Hesap uyuşmazlığı",
            sum(bool(row.calculation_mismatch_fields) for row in summary.rows),
            border=True,
        )

    with st.container(horizontal=True):
        st.metric(
            "Güncel teknik",
            technical_quality.current_count,
            border=True,
        )
        st.metric(
            "Eski teknik",
            technical_quality.stale_count,
            border=True,
        )
        st.metric(
            "Teknik kayıt yok",
            technical_quality.missing_count,
            border=True,
        )
        st.metric(
            "Teknik tarih hatası",
            technical_quality.date_error_count,
            border=True,
        )

    with st.container(horizontal=True):
        st.metric(
            "Karara hazır",
            readiness_summary.ready_count,
            border=True,
        )
        st.metric(
            "Finansal doğrulama",
            readiness_summary.financial_only_count,
            border=True,
        )
        st.metric(
            "Teknik yenileme",
            readiness_summary.technical_only_count,
            border=True,
        )
        st.metric(
            "İki alanda doğrulama",
            readiness_summary.combined_issue_count,
            border=True,
        )

    default_refresh_symbols = select_technical_refresh_candidates(
        technical_quality
    )
    with st.container(border=True):
        st.subheader("Teknik veri sorunlarını düzelt")
        st.caption(
            "Eski, eksik veya tarih hatalı kayıtlar önceliklendirilir. "
            "Yalnız güncel ve fiyat-grafik uyumu doğrulanan sonuçlar kaydedilir."
        )
        refresh_symbols = st.multiselect(
            "Yenilenecek hisseler",
            [company.symbol for company in companies],
            default=default_refresh_symbols,
            max_selections=MAX_TECHNICAL_REFRESH_BATCH,
            key="quality_technical_refresh_symbols",
            help=(
                "Veri sağlayıcı yükünü sınırlamak için tek seferde en fazla "
                f"{MAX_TECHNICAL_REFRESH_BATCH} hisse yenilenir."
            ),
        )
        if st.button(
            "Seçilen teknik kayıtları yenile",
            icon=":material/sync:",
            disabled=not refresh_symbols,
            key="quality_technical_refresh_button",
        ):
            with st.spinner("Teknik veriler doğrulanıp kaydediliyor..."):
                st.session_state["quality_technical_refresh_result"] = (
                    refresh_technical_scores(
                        refresh_symbols,
                        _load_market_data,
                        add_technical_score_history,
                        settings.technical_methodology_version,
                    )
                )
            st.rerun()

        refresh_result = st.session_state.get(
            "quality_technical_refresh_result"
        )
        if isinstance(refresh_result, TechnicalRefreshSummary):
            _render_technical_refresh_summary(refresh_result)

    profile_options = ["Tümü"] + [PROFILE_LABELS[item] for item in CompanyProfile]
    status_options = ["Doğrulandı", "Kontrol gerekli", "Eksik veri", "Hatalı"]
    freshness_options = list(REPORT_FRESHNESS_LABELS.values())
    filter_left, filter_middle, filter_right = st.columns(3)
    with filter_left:
        selected_profile = st.selectbox("Sektör profili", profile_options)
    with filter_middle:
        selected_statuses = st.multiselect(
            "Doğrulama durumu", status_options, default=status_options
        )
    with filter_right:
        selected_freshness = st.multiselect(
            "Rapor güncelliği",
            freshness_options,
            default=freshness_options,
        )
    filter_technical, filter_readiness = st.columns(2)
    with filter_technical:
        selected_technical_statuses = st.multiselect(
            "Teknik kayıt durumu",
            TECHNICAL_STATUS_OPTIONS,
            default=TECHNICAL_STATUS_OPTIONS,
        )
    with filter_readiness:
        selected_readiness_statuses = st.multiselect(
            "Karara hazırlık",
            READINESS_STATUS_OPTIONS,
            default=READINESS_STATUS_OPTIONS,
        )

    filtered = [
        row for row in summary.rows
        if row.status in selected_statuses
        and REPORT_FRESHNESS_LABELS[freshness[row.symbol].status]
        in selected_freshness
        and technical_by_symbol[row.symbol].status
        in selected_technical_statuses
        and readiness_by_symbol[row.symbol].status
        in selected_readiness_statuses
        and (
            selected_profile == "Tümü"
            or PROFILE_LABELS[row.company_profile] == selected_profile
        )
    ]
    table = pd.DataFrame(
        [
            {
                "Hisse": row.symbol,
                "Şirket": row.company_name,
                "Profil": PROFILE_LABELS[row.company_profile],
                "Veri kaynağı": _audit_source_label(latest_audits.get(row.symbol)),
                "Rapor dönemi": _audit_period_label(latest_audits.get(row.symbol)),
                "Rapor güncelliği": REPORT_FRESHNESS_LABELS[
                    freshness[row.symbol].status
                ],
                "Rapor yaşı (gün)": freshness[row.symbol].age_days,
                "Dönem kontrolü": freshness[row.symbol].message,
                "Son doğrulama": _audit_date(latest_audits.get(row.symbol)),
                "Analiz güveni (%)": confidences[row.symbol].total,
                "Güven durumu": confidences[row.symbol].status,
                "Yeterlilik (%)": row.completeness,
                "Teknik puan": technical_by_symbol[row.symbol].technical_score,
                "Teknik sinyal": (
                    technical_by_symbol[row.symbol].signal
                    if technical_by_symbol[row.symbol].current
                    else "-"
                ),
                "Teknik fiyat tarihi": technical_by_symbol[row.symbol].price_date,
                "Teknik kayıt yaşı (gün)": technical_by_symbol[row.symbol].age_days,
                "Teknik kayıt durumu": technical_by_symbol[row.symbol].status,
                "Teknik kaynak": technical_by_symbol[row.symbol].source or "-",
                "Teknik metodoloji": (
                    technical_by_symbol[row.symbol].methodology_version or "-"
                ),
                "Karara hazırlık": readiness_by_symbol[row.symbol].status,
                "Önerilen işlem": (
                    readiness_by_symbol[row.symbol].recommended_action
                ),
                "Karar engelleri": (
                    " | ".join(readiness_by_symbol[row.symbol].blockers)
                    or "Yok"
                ),
                "Durum": row.status,
                "Hesap kontrolü": row.calculation_check_status,
                "Uyuşmayan göstergeler": (
                    ", ".join(row.calculation_mismatch_fields) or "Yok"
                ),
                "Eksik göstergeler": ", ".join(row.missing_fields) or "Yok",
                "Uyarı / hata": " | ".join(row.errors + row.warnings) or "Yok",
            }
            for row in filtered
        ]
    )
    with st.container(border=True):
        st.subheader("Doğrulama listesi")
        if table.empty:
            st.info("Seçilen filtrelere uyan şirket bulunamadı.")
        else:
            st.dataframe(
                table,
                hide_index=True,
                width="stretch",
                column_config={
                    "Hisse": st.column_config.TextColumn(pinned=True),
                    "Son doğrulama": st.column_config.DatetimeColumn(
                        "Son doğrulama", format="DD.MM.YYYY HH:mm"
                    ),
                    "Rapor yaşı (gün)": st.column_config.NumberColumn(
                        "Rapor yaşı (gün)", format="%d"
                    ),
                    "Analiz güveni (%)": st.column_config.ProgressColumn(
                        "Analiz güveni (%)", min_value=0, max_value=100, format="%.1f"
                    ),
                    "Yeterlilik (%)": st.column_config.ProgressColumn(
                        "Yeterlilik (%)", min_value=0, max_value=100, format="%.1f"
                    ),
                    "Teknik puan": st.column_config.ProgressColumn(
                        "Teknik puan", min_value=0, max_value=100, format="%.1f"
                    ),
                    "Teknik fiyat tarihi": st.column_config.DateColumn(
                        "Teknik fiyat tarihi", format="DD.MM.YYYY"
                    ),
                    "Teknik kayıt yaşı (gün)": st.column_config.NumberColumn(
                        "Teknik kayıt yaşı (gün)", format="%d"
                    ),
                },
            )

    _render_quality_correction_form()


def render_scanner() -> None:
    st.title("Hisse tarayıcı")

    companies = list_companies()
    if not companies:
        st.info("Tarama için önce şirket verisi kaydedin.")
        return
    latest_audits = {
        audit.symbol: audit for audit in list_latest_company_data_audits()
    }

    company_symbols = [company.symbol for company in companies]
    priority_symbols = list(
        dict.fromkeys(
            [
                entry.symbol for entry in list_watchlist_entries()
            ]
            + [
                position.symbol
                for position in list_portfolio_positions()
            ]
        )
    )
    default_refresh_symbols = [
        symbol
        for symbol in priority_symbols
        if symbol in company_symbols
    ][:MAX_TECHNICAL_REFRESH_BATCH]
    if not default_refresh_symbols:
        default_refresh_symbols = company_symbols[
            : min(10, len(company_symbols))
        ]
    refresh_symbols = st.multiselect(
        "Teknik verisi güncellenecek hisseler",
        company_symbols,
        default=default_refresh_symbols,
        max_selections=MAX_TECHNICAL_REFRESH_BATCH,
        help=(
            "Veri sağlayıcı yükünü sınırlamak için tek seferde en fazla "
            f"{MAX_TECHNICAL_REFRESH_BATCH} hisse güncellenir. Takip "
            "listesi ve portföy hisseleri öncelikli seçilir."
        ),
    )
    if st.button(
        "Teknik kayıtları güncelle",
        icon=":material/sync:",
        disabled=not refresh_symbols,
        help=(
            "Seçilen şirketlerin gecikmeli piyasa verisini doğrular ve "
            "yalnız güncel, fiyat-grafik uyumlu teknik puanları kaydeder."
        ),
    ):
        with st.spinner("Teknik veriler doğrulanıp kaydediliyor..."):
            refresh_summary = refresh_technical_scores(
                refresh_symbols,
                _load_market_data,
                add_technical_score_history,
                settings.technical_methodology_version,
            )
        _render_technical_refresh_summary(refresh_summary)

    with st.form("scanner_filters", border=True):
        st.subheader("Filtreler")
        st.caption(
            "Ciro, marj, borç ve nakit filtreleri standart şirketler ile GYO'lara "
            "uygulanır. Banka, sigorta ve finansal hizmetler kendi sektör puanlarıyla taranır."
        )
        left, right = st.columns(2)
        with left:
            minimum_alpha = st.slider("Minimum Alpha Score", 0, 100, 70)
            minimum_revenue_growth = st.number_input(
                "Minimum ciro büyümesi (%)",
                value=0.0,
                step=1.0,
                format="%.2f",
            )
            minimum_net_margin = st.number_input(
                "Minimum net kâr marjı (%)",
                value=0.0,
                step=1.0,
                format="%.2f",
            )
            minimum_technical = st.slider(
                "Minimum güncel teknik puan",
                0,
                100,
                0,
                help=(
                    "0 seçildiğinde teknik puan eşiği uygulanmaz. "
                    "Daha yüksek bir eşik yalnız güncel ve doğrulanmış "
                    "teknik kayıtları kabul eder."
                ),
            )
        with right:
            maximum_debt_to_equity = st.number_input(
                "Maksimum borç / özkaynak",
                min_value=0.0,
                value=3.0,
                step=0.1,
                format="%.2f",
            )
            positive_cash_flow = st.toggle(
                "Yalnızca pozitif operasyonel nakit akışı",
                value=True,
            )
            decision_ready_only = st.toggle(
                "Yalnızca karara hazır şirketler",
                value=False,
                help=(
                    "Güncel raporu, yeterli güveni ve hesap tutarlılığı "
                    "bulunan şirketleri gösterir."
                ),
            )
            current_technical_only = st.toggle(
                "Yalnızca güncel teknik kaydı olanlar",
                value=False,
            )
            technical_strengthening_only = st.toggle(
                "Yalnızca teknik puanı yükselenler",
                value=False,
            )
        st.form_submit_button(
            "Filtrele",
            type="primary",
            icon=":material/filter_alt:",
        )

    technical_histories = {
        company.symbol: list_technical_score_history(company.symbol)
        for company in companies
    }
    summary = scan_companies(
        companies,
        ScannerFilters(
            minimum_alpha_score=minimum_alpha,
            minimum_revenue_growth=minimum_revenue_growth,
            minimum_net_margin=minimum_net_margin,
            maximum_debt_to_equity=maximum_debt_to_equity,
            positive_operating_cash_flow_only=positive_cash_flow,
            decision_ready_only=decision_ready_only,
            minimum_technical_score=(
                float(minimum_technical)
                if minimum_technical > 0
                else None
            ),
            current_technical_only=current_technical_only,
            technical_strengthening_only=(
                technical_strengthening_only
            ),
        ),
        latest_audits,
        technical_histories,
    )

    with st.container(horizontal=True):
        st.metric("Taranan", summary.total_scanned, border=True)
        st.metric("Eşleşen", summary.matched_count, border=True)
        st.metric(
            "Ortalama Alpha",
            f"{summary.average_alpha_score:.1f}/100",
            border=True,
        )
        st.metric(
            "Lider",
            summary.rows[0].symbol if summary.rows else "-",
            border=True,
        )
        st.metric(
            "Güncel teknik kayıt",
            summary.current_technical_count,
            border=True,
        )

    if not summary.rows:
        st.info("Seçilen ölçütlere uyan şirket bulunamadı.")
        return

    rows = [
        {
            "Sıra": index,
            "Hisse": row.symbol,
            "Şirket": row.company_name,
            "Alpha": row.alpha_score,
            "Not": row.grade,
            "Karar": row.decision,
            "Analiz güveni (%)": row.confidence_score,
            "Güven durumu": row.confidence_status,
            "Hesap kontrolü": row.calculation_check_status,
            "Karar hazırlığı": (
                "Hazır" if row.decision_ready else "Doğrulama gerekli"
            ),
            "Ciro büyümesi (%)": row.revenue_growth,
            "Net marj (%)": row.net_margin,
            "ROE (%)": row.roe,
            "Borç / özkaynak": row.debt_to_equity,
            "Cari oran": row.current_ratio,
            "Operasyonel nakit (TL)": row.operating_cash_flow,
            "Teknik puan": row.technical_score,
            "Teknik değişim": row.technical_delta,
            "Teknik sinyal": (
                row.technical_signal if row.technical_current else "-"
            ),
            "Teknik fiyat tarihi": row.technical_price_date,
            "Teknik kayıt durumu": row.technical_status,
        }
        for index, row in enumerate(summary.rows, start=1)
    ]
    result_frame = pd.DataFrame(rows)
    with st.container(border=True):
        st.subheader("Tarama sonuçları")
        st.dataframe(
            result_frame,
            hide_index=True,
            width="stretch",
            column_config={
                "Alpha": st.column_config.ProgressColumn(
                    "Alpha", min_value=0, max_value=100, format="%.1f"
                ),
                "Analiz güveni (%)": st.column_config.ProgressColumn(
                    "Analiz güveni (%)",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Ciro büyümesi (%)": st.column_config.NumberColumn(format="%.2f"),
                "Net marj (%)": st.column_config.NumberColumn(format="%.2f"),
                "ROE (%)": st.column_config.NumberColumn(format="%.2f"),
                "Borç / özkaynak": st.column_config.NumberColumn(format="%.4f"),
                "Cari oran": st.column_config.NumberColumn(format="%.2f"),
                "Operasyonel nakit (TL)": st.column_config.NumberColumn(
                    format="localized"
                ),
                "Teknik puan": st.column_config.ProgressColumn(
                    "Teknik puan",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Teknik değişim": st.column_config.NumberColumn(
                    format="%+.1f"
                ),
                "Teknik fiyat tarihi": st.column_config.DateColumn(
                    "Teknik fiyat tarihi",
                    format="DD.MM.YYYY",
                ),
            },
        )

    with st.container(border=True):
        st.subheader("Alpha sıralaması")
        st.bar_chart(result_frame.set_index("Hisse")[["Alpha"]])


def render_company_form() -> None:
    st.title("Şirket ekle veya güncelle")
    st.caption("Raporlardan otomatik doldurun veya finansal oranları elle girin.")

    pdf_tab, manual_tab = st.tabs(["PDF ile otomatik doldur", "Manuel giriş"])
    with pdf_tab:
        _render_pdf_company_form()
    with manual_tab:
        _render_manual_company_form()


def _render_pdf_company_form() -> None:
    upload_left, upload_right = st.columns(2)
    with upload_left:
        financial_file = st.file_uploader(
            "Finansal rapor",
            type=["pdf"],
            key="company_financial_pdf",
            help="SPK/KAP finansal tablo ve dipnot PDF'ini yükleyin.",
        )
    with upload_right:
        activity_file = st.file_uploader(
            "Faaliyet raporu",
            type=["pdf"],
            key="company_activity_pdf",
            help="Şirket adı, hisse kodu ve dönem bilgisini tamamlar.",
        )

    if financial_file is None:
        st.info("Otomatik doldurma için önce finansal raporu yükleyin.")
        return

    financial_bytes = financial_file.getvalue()
    activity_bytes = activity_file.getvalue() if activity_file else b""
    financial_report_hash = document_fingerprint(financial_bytes)
    activity_report_hash = document_fingerprint(activity_bytes)
    document_token = hashlib.sha256(financial_bytes + activity_bytes).hexdigest()
    if st.session_state.get("company_pdf_token") != document_token:
        for key in list(st.session_state):
            if (
                key.startswith("pdf_field_")
                or key.startswith("pdf_source_")
                or key
                in {
                    "pdf_period",
                    "pdf_period_end",
                    "pdf_monetary_scale",
                    "pdf_comparison_confirmed",
                    "pdf_company_profile",
                }
            ):
                del st.session_state[key]
        st.session_state["company_pdf_token"] = document_token

    try:
        with st.spinner("Raporlar okunuyor ve finansal oranlar hazırlanıyor..."):
            financial_result = _parse_pdf(financial_bytes, financial_file.name)
            activity_result = (
                _parse_activity_pdf(activity_bytes, activity_file.name)
                if activity_file
                else None
            )
    except PdfParsingError as exc:
        st.error(str(exc))
        return

    suggested_profile = financial_result.draft.company_profile
    if (
        activity_result
        and activity_result.metadata.company_profile
        != CompanyProfile.STANDARD
    ):
        suggested_profile = activity_result.metadata.company_profile
    company_profile = _profile_select(
        "Şirket türü / sektör profili",
        suggested_profile,
        "pdf_company_profile",
    )
    if company_profile != financial_result.draft.company_profile:
        financial_result = _parse_pdf(
            financial_bytes,
            financial_file.name,
            company_profile,
        )

    scale_options = {
        1.0: "TL",
        1_000.0: "bin TL",
        1_000_000.0: "milyon TL",
    }
    selected_scale = st.selectbox(
        "Finansal rapor sunum birimi",
        list(scale_options),
        index=list(scale_options).index(financial_result.monetary_scale),
        format_func=scale_options.get,
        key="pdf_monetary_scale",
        help=(
            "Rapor kapağındaki sunum birimini doğrulayın. Bu seçim yalnızca "
            "parasal tutarları etkiler; yüzdeler ve oranlar değişmez."
        ),
    )
    draft = rescale_monetary_values(
        financial_result.draft,
        financial_result.monetary_scale,
        selected_scale,
    )
    if selected_scale != financial_result.monetary_scale:
        st.warning(
            "Otomatik bulunan sunum birimi kullanıcı seçimine göre değiştirildi. "
            "Parasal tutarlar yeni ölçeğe göre yeniden hesaplandı."
        )
    if activity_result:
        metadata = activity_result.metadata
        report_identity_errors = validate_report_identity(
            submitted_symbol=draft.symbol or metadata.symbol,
            submitted_company_name=draft.company_name or metadata.company_name,
            financial_symbol=draft.symbol,
            financial_company_name=draft.company_name,
            activity_symbol=metadata.symbol,
            activity_company_name=metadata.company_name,
        )
        if report_identity_errors:
            st.error(
                "Yüklenen finansal rapor ile faaliyet raporu aynı şirkete ait "
                "görünmüyor. Kayıt formu güvenlik amacıyla açılmadı."
            )
            for identity_error in report_identity_errors:
                st.warning(identity_error)
            return
        period_conflict = (
            draft.report_period_end is not None
            and metadata.report_period_end is not None
            and draft.report_period_end != metadata.report_period_end
        )
        effective_period_end = (
            draft.report_period_end or metadata.report_period_end
        )
        activity_updates = dict(activity_result.sector_metrics)
        activity_updates.update(
            {
                "symbol": metadata.symbol or draft.symbol,
                "company_name": metadata.company_name or draft.company_name,
                "period_months": (
                    effective_period_end.month
                    if effective_period_end
                    else metadata.period_months or draft.period_months
                ),
                "report_period_end": effective_period_end,
                "company_profile": (
                    company_profile
                ),
            }
        )
        draft = draft.model_copy(
            update=activity_updates
        )
        if period_conflict:
            st.warning(
                "Finansal rapor ile faaliyet raporunun dönem sonları farklı. "
                f"Finansal rapordaki {financial_result.draft.report_period_end:%d.%m.%Y} "
                "tarihi kullanıldı; kaydetmeden önce doğrulayın."
            )

    with st.container(horizontal=True):
        st.metric(
            "Bulunan finansal kalem",
            len(financial_result.extracted_fields),
            border=True,
        )
        st.metric("Finansal rapor", f"{financial_result.page_count} sayfa", border=True)
        st.metric(
            "Tutar ölçeği",
            financial_result.monetary_unit_label,
            border=True,
        )
        if activity_result:
            st.metric("Faaliyet raporu", f"{activity_result.page_count} sayfa", border=True)

    for warning in financial_result.warnings:
        st.warning(warning)
    if activity_result:
        for warning in activity_result.warnings:
            st.warning(warning)

    source_context = f"{company_profile.value}:{selected_scale:g}"
    if st.session_state.get("pdf_source_context") != source_context:
        for key in list(st.session_state):
            if key.startswith("pdf_source_"):
                del st.session_state[key]
        st.session_state["pdf_source_context"] = source_context

    draft, corrected_source_fields, source_input_errors = (
        _render_pdf_source_editor(draft, company_profile)
    )
    for source_input_error in source_input_errors:
        st.error(source_input_error)

    source_token = hashlib.sha256(
        repr(
            tuple(
                (field, getattr(draft, field))
                for field in _pdf_source_fields(company_profile)
            )
        ).encode("utf-8")
    ).hexdigest()
    if st.session_state.get("pdf_source_token") != source_token:
        for key in list(st.session_state):
            if key.startswith("pdf_field_") and key not in {
                "pdf_field_symbol",
                "pdf_field_company_name",
            }:
                del st.session_state[key]
        st.session_state["pdf_source_token"] = source_token

    period_options = [3, 6, 9, 12]
    period_default = draft.period_months if draft.period_months in period_options else 3
    period_months = st.selectbox(
        "Rapor dönemi",
        period_options,
        index=period_options.index(period_default),
        format_func=lambda value: f"{value} aylık",
        key="pdf_period",
    )
    report_period_end = st.date_input(
        "Rapor dönem sonu",
        value=draft.report_period_end,
        format="DD.MM.YYYY",
        key="pdf_period_end",
        help="PDF'den bulunan tarihi resmi rapor kapağıyla doğrulayın.",
    )
    calculation_draft = draft.model_copy(
        update={
            "symbol": draft.symbol or "TEMP",
            "company_name": draft.company_name or "Geçici şirket",
            "period_months": period_months,
            "report_period_end": report_period_end,
            "company_profile": company_profile,
        }
    )
    defaults = to_financial_metrics(calculation_draft)
    source_validation = validate_financial_draft(calculation_draft)
    for error in source_validation.errors:
        st.error(error)
    for warning in source_validation.warnings:
        st.warning(warning)
    if abs(defaults.roe or 0) > 100:
        st.warning(
            f"Yıllıklandırılmış ROE %{defaults.roe:,.1f}. Tek seferlik gelirler veya "
            "düşük özkaynak nedeniyle yüksek olabilir; kaydetmeden önce kontrol edin."
        )
    if (defaults.debt_to_equity or 0) > 10:
        st.warning(
            "Borç / özkaynak oranı olağan dışı yüksek. PDF kaynak değerlerini "
            "kontrol edin."
        )

    st.caption(
        "Otomatik bulunan değerleri resmi tablolardan kontrol edin; eksik veya yanlış "
        "alanları kaydetmeden önce düzeltebilirsiniz."
    )
    with st.form("pdf_company_form", border=True):
        st.subheader("Otomatik doldurulan şirket bilgileri")
        if financial_result.comparison_period_validated:
            comparison_confirmed = True
            st.caption(
                "Büyüme karşılaştırma dönemi doğrulandı: "
                f"{financial_result.comparison_period_end:%d.%m.%Y}"
            )
        else:
            comparison_confirmed = st.checkbox(
                "Cari ve önceki dönem sütunlarını resmi gelir tablosundan "
                "kontrol ettim",
                key="pdf_comparison_confirmed",
            )
        symbol = st.text_input(
            "Hisse kodu",
            value=draft.symbol,
            key="pdf_field_symbol",
        )
        company_name = st.text_input(
            "Şirket adı",
            value=draft.company_name,
            key="pdf_field_company_name",
        )

        sector_metrics = _sector_inputs(
            company_profile,
            "pdf_sector",
            defaults,
        )

        left, right = st.columns(2)
        with left:
            revenue_growth = st.number_input(
                "Ciro büyümesi (%)",
                value=defaults.revenue_growth,
                step=0.1,
                format="%.2f",
                key="pdf_field_revenue_growth",
            )
            net_profit_growth = st.number_input(
                "Net kâr büyümesi (%)",
                value=defaults.net_profit_growth,
                step=0.1,
                format="%.2f",
                key="pdf_field_profit_growth",
            )
            net_margin = st.number_input(
                "Net kâr marjı (%)",
                value=defaults.net_margin,
                step=0.1,
                format="%.2f",
                key="pdf_field_net_margin",
            )
            roe = st.number_input(
                "ROE (%)",
                value=defaults.roe,
                step=0.1,
                format="%.2f",
                key="pdf_field_roe",
            )
            debt_to_equity = st.number_input(
                "Borç / özkaynak",
                value=defaults.debt_to_equity,
                min_value=0.0,
                step=0.01,
                format="%.4f",
                key="pdf_field_debt_to_equity",
            )
            current_ratio = st.number_input(
                "Cari oran",
                value=defaults.current_ratio,
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key="pdf_field_current_ratio",
            )
        with right:
            operating_cash_flow_input = _amount_input(
                "Operasyonel nakit akışı",
                defaults.operating_cash_flow,
                key="pdf_field_operating_cash_flow",
            )
            free_cash_flow_input = _amount_input(
                "Serbest nakit akışı",
                defaults.free_cash_flow,
                key="pdf_field_free_cash_flow",
            )
            asset_turnover = st.number_input(
                "Aktif devir hızı",
                value=defaults.asset_turnover,
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key="pdf_field_asset_turnover",
            )
            valuation = st.slider(
                "Değerleme girdisi", 0, 100, 50, key="pdf_field_valuation"
            )
            management = st.slider(
                "Yönetim girdisi", 0, 100, 70, key="pdf_field_management"
            )
            risk = st.slider(
                "Risk dayanıklılığı", 0, 100, 50, key="pdf_field_risk"
            )
        submitted = st.form_submit_button(
            "Kontrol et ve kaydet",
            type="primary",
            icon=":material/save:",
        )

    if not submitted:
        return
    if source_input_errors:
        st.error("Kaynak tutarlardaki biçim hatalarını düzeltmeden kayıt yapılamaz.")
        return
    if source_validation.errors:
        st.error(
            "PDF'den çıkarılan kaynak tutarlarda kritik tutarsızlık bulundu. "
            "Rapor birimini veya PDF eşleşmesini düzeltmeden kayıt yapılamaz."
        )
        return
    if not comparison_confirmed:
        st.error(
            "Karşılaştırma dönemi otomatik doğrulanamadı. Büyüme oranlarını "
            "kaydetmek için cari ve önceki dönem sütunlarını doğrulayın."
        )
        return
    identity_errors = validate_report_identity(
        submitted_symbol=symbol,
        submitted_company_name=company_name,
        financial_symbol=financial_result.draft.symbol,
        financial_company_name=financial_result.draft.company_name,
        activity_symbol=(
            activity_result.metadata.symbol if activity_result else ""
        ),
        activity_company_name=(
            activity_result.metadata.company_name if activity_result else ""
        ),
    )
    if identity_errors:
        st.error(
            "Hisse kodu veya şirket unvanı yüklenen raporlarla uyuşmuyor. "
            "Kayıt yapılmadı."
        )
        for identity_error in identity_errors:
            st.warning(identity_error)
        return
    try:
        operating_cash_flow = _parse_amount_input(
            "Operasyonel nakit akışı",
            operating_cash_flow_input,
        )
        free_cash_flow = _parse_amount_input(
            "Serbest nakit akışı",
            free_cash_flow_input,
        )
    except AppValidationError as exc:
        st.error(str(exc))
        return
    _validate_and_save_company(
        symbol=symbol,
        company_name=company_name,
        revenue_growth=revenue_growth,
        net_profit_growth=net_profit_growth,
        net_margin=net_margin,
        roe=roe,
        debt_to_equity=debt_to_equity,
        current_ratio=current_ratio,
        operating_cash_flow=operating_cash_flow,
        free_cash_flow=free_cash_flow,
        asset_turnover=asset_turnover,
        valuation=valuation,
        management=management,
        risk=risk,
        company_profile=company_profile,
        sector_metrics=sector_metrics,
        source_type=DataSourceType.PDF,
        period_months=period_months,
        report_period_end=report_period_end,
        financial_report_name=financial_file.name,
        activity_report_name=activity_file.name if activity_file else "",
        financial_report_hash=financial_report_hash,
        activity_report_hash=activity_report_hash,
        financial_report_scale=selected_scale,
        comparison_period_end=financial_result.comparison_period_end,
        comparison_period_confirmed=comparison_confirmed,
        field_sources=build_pdf_field_sources(
            financial_result,
            activity_result,
            defaults,
            {
                "revenue_growth": revenue_growth,
                "net_profit_growth": net_profit_growth,
                "net_margin": net_margin,
                "roe": roe,
                "debt_to_equity": debt_to_equity,
                "current_ratio": current_ratio,
                "operating_cash_flow": operating_cash_flow,
                "free_cash_flow": free_cash_flow,
                "asset_turnover": asset_turnover,
                "valuation_score_input": valuation,
                "management_score_input": management,
                "risk_score_input": risk,
                **sector_metrics,
            },
            corrected_source_fields=corrected_source_fields,
        ),
        source_values=build_source_value_snapshot(draft),
    )


def _render_manual_company_form() -> None:
    company_profile = _profile_select(
        "Şirket türü / sektör profili",
        CompanyProfile.STANDARD,
        "manual_company_profile",
    )
    st.caption("Finansal oranları elle girin ve Alpha puanını hesaplayın.")

    with st.form("company_form"):
        symbol = st.text_input("Hisse kodu", "ASELS")
        company_name = st.text_input(
            "Şirket adı",
            "Aselsan Elektronik Sanayi ve Ticaret A.Ş.",
        )
        period_left, period_right = st.columns(2)
        with period_left:
            period_months = st.selectbox(
                "Rapor dönemi",
                [3, 6, 9, 12],
                format_func=lambda value: f"{value} aylık",
                key="manual_period",
            )
        with period_right:
            report_period_end = st.date_input(
                "Rapor dönem sonu",
                value=None,
                format="DD.MM.YYYY",
                key="manual_period_end",
            )

        left, right = st.columns(2)
        with left:
            revenue_growth = st.number_input(
                "Ciro büyümesi (%)", value=10.0, step=0.1, format="%.2f"
            )
            net_profit_growth = st.number_input(
                "Net kâr büyümesi (%)",
                value=10.0,
                step=0.1,
                format="%.2f",
            )
            net_margin = st.number_input(
                "Net kâr marjı (%)", value=10.0, step=0.1, format="%.2f"
            )
            roe = st.number_input(
                "ROE (%)", value=15.0, step=0.1, format="%.2f"
            )
            debt_to_equity = st.number_input(
                "Borç / özkaynak",
                value=0.5,
                min_value=0.0,
                step=0.01,
                format="%.4f",
            )
            current_ratio = st.number_input(
                "Cari oran",
                value=1.5,
                min_value=0.0,
                step=0.01,
                format="%.2f",
            )

        with right:
            operating_cash_flow_input = _amount_input(
                "Operasyonel nakit akışı",
                1_000_000.0,
                key="manual_operating_cash_flow",
            )
            free_cash_flow_input = _amount_input(
                "Serbest nakit akışı",
                500_000.0,
                key="manual_free_cash_flow",
            )
            asset_turnover = st.number_input(
                "Aktif devir hızı",
                value=0.7,
                min_value=0.0,
                step=0.01,
                format="%.2f",
            )
            valuation = st.slider("Değerleme girdisi", 0, 100, 70)
            management = st.slider("Yönetim girdisi", 0, 100, 75)
            risk = st.slider("Risk dayanıklılığı", 0, 100, 65)

        sector_metrics = _sector_inputs(company_profile, "manual_sector")

        submitted = st.form_submit_button(
            "Hesapla ve kaydet",
            type="primary",
            icon=":material/save:",
        )

    if not submitted:
        return

    try:
        operating_cash_flow = _parse_amount_input(
            "Operasyonel nakit akışı",
            operating_cash_flow_input,
        )
        free_cash_flow = _parse_amount_input(
            "Serbest nakit akışı",
            free_cash_flow_input,
        )
    except AppValidationError as exc:
        st.error(str(exc))
        return

    _validate_and_save_company(
        symbol=symbol,
        company_name=company_name,
        revenue_growth=revenue_growth,
        net_profit_growth=net_profit_growth,
        net_margin=net_margin,
        roe=roe,
        debt_to_equity=debt_to_equity,
        current_ratio=current_ratio,
        operating_cash_flow=operating_cash_flow,
        free_cash_flow=free_cash_flow,
        asset_turnover=asset_turnover,
        valuation=valuation,
        management=management,
        risk=risk,
        company_profile=company_profile,
        sector_metrics=sector_metrics,
        period_months=period_months,
        report_period_end=report_period_end,
    )


def _validate_and_save_company(
    *,
    symbol: str,
    company_name: str,
    revenue_growth: float | None,
    net_profit_growth: float | None,
    net_margin: float | None,
    roe: float | None,
    debt_to_equity: float | None,
    current_ratio: float | None,
    operating_cash_flow: float | None,
    free_cash_flow: float | None,
    asset_turnover: float | None,
    valuation: float,
    management: float,
    risk: float,
    company_profile: CompanyProfile = CompanyProfile.STANDARD,
    sector_metrics: dict[str, float | None] | None = None,
    source_type: DataSourceType = DataSourceType.MANUAL,
    period_months: int | None = None,
    report_period_end: date | None = None,
    financial_report_name: str = "",
    activity_report_name: str = "",
    financial_report_hash: str = "",
    activity_report_hash: str = "",
    financial_report_scale: float = 1,
    comparison_period_end: date | None = None,
    comparison_period_confirmed: bool = False,
    field_sources: dict[str, MetricSourceType] | None = None,
    source_values: dict[str, float | None] | None = None,
) -> None:
    sector_metrics = sector_metrics or {}
    period_assessment = assess_report_period(report_period_end, period_months)
    if period_assessment.blocks_decision:
        st.error(period_assessment.message)
        return
    if period_assessment.status != ReportFreshnessStatus.CURRENT:
        st.warning(period_assessment.message)
    try:
        metrics = FinancialMetrics(
            symbol=symbol.upper().strip(),
            company_name=company_name.strip(),
            company_profile=company_profile,
            revenue_growth=revenue_growth,
            net_profit_growth=net_profit_growth,
            net_margin=net_margin,
            roe=roe,
            debt_to_equity=debt_to_equity,
            current_ratio=current_ratio,
            operating_cash_flow=operating_cash_flow,
            free_cash_flow=free_cash_flow,
            asset_turnover=asset_turnover,
            valuation_score_input=valuation,
            management_score_input=management,
            risk_score_input=risk,
            **sector_metrics,
        )
    except ValidationError as exc:
        st.error(f"Girilen bilgiler geçerli değil: {exc}")
        return

    latest_audit = get_latest_company_data_audit(metrics.symbol)
    existing_company = get_company(metrics.symbol)
    if existing_company and not company_names_match(
        existing_company.company_name,
        metrics.company_name,
    ):
        st.error(
            f"{metrics.symbol} kodu veritabanında "
            f"'{existing_company.company_name}' unvanıyla kayıtlı. Farklı bir "
            "şirket unvanıyla üzerine yazma işlemi durduruldu."
        )
        return
    if report_period_regresses(
        report_period_end,
        latest_audit.report_period_end if latest_audit else None,
    ):
        st.error(
            "Rapor dönemi mevcut son kayıttan daha eski. Önceki dönemleri "
            "yanlışlıkla güncel analiz üzerine yazmamak için kayıt durduruldu."
        )
        return
    document_usages = {
        audit.id: audit
        for document_hash in (
            financial_report_hash,
            activity_report_hash,
        )
        if document_hash
        for audit in list_document_usages(document_hash)
    }
    document_conflicts = document_identity_conflicts(
        list(document_usages.values()),
        symbol=metrics.symbol,
        report_period_end=report_period_end,
        financial_report_hash=financial_report_hash,
        activity_report_hash=activity_report_hash,
    )
    if document_conflicts:
        st.error(
            "Kaynak belge başka bir şirket veya dönemle eşleşiyor. "
            "Yanlış raporla kayıt yapılmasını önlemek için işlem durduruldu."
        )
        for conflict in document_conflicts:
            st.warning(conflict)
        return
    if is_duplicate_analysis(latest_audit, metrics, report_period_end):
        st.info(
            "Bu dönem ve finansal girdiler son analizle aynı. Puan geçmişine "
            "yinelenen kayıt eklenmedi."
        )
        return

    validation = validate_financial_metrics(metrics)
    if validation.errors:
        for error in validation.errors:
            st.error(error)
        return
    for warning in validation.warnings:
        st.warning(warning)

    upsert_company(metrics)
    score = calculate_alpha_score(metrics)
    add_score_history(metrics.symbol, score)
    if field_sources is None:
        excluded = {"symbol", "company_name", "company_profile"}
        field_sources = {
            field: MetricSourceType.MANUAL
            for field, value in metrics.model_dump().items()
            if field not in excluded and value is not None
        }
    audit = CompanyDataAudit(
        symbol=metrics.symbol,
        source_type=source_type,
        company_profile=CompanyProfile(metrics.company_profile),
        period_months=period_months,
        report_period_end=report_period_end,
        financial_report_name=financial_report_name,
        activity_report_name=activity_report_name,
        financial_report_hash=financial_report_hash,
        activity_report_hash=activity_report_hash,
        financial_report_scale=financial_report_scale,
        comparison_period_end=comparison_period_end,
        comparison_period_confirmed=comparison_period_confirmed,
        completeness=score.data_completeness,
        alpha_score=score.total,
        field_sources=field_sources,
        source_values=source_values or {},
    )
    confidence = calculate_analysis_confidence(metrics, score, audit)
    add_company_data_audit(
        attach_analysis_snapshot(audit, metrics, score, confidence)
    )
    st.success(
        f"{metrics.symbol} kaydedildi. Alpha Score: {score.total:.1f}/100"
    )
    st.caption(
        f"Profil: {PROFILE_LABELS[CompanyProfile(metrics.company_profile)]} | "
        f"Veri yeterliliği: %{score.data_completeness:.0f}"
    )


def render_pdf_analysis() -> None:
    st.title("PDF analizi")
    st.caption(
        "Finansal ve faaliyet raporlarını birlikte okuyun; sektör profilini ve "
        "çıkarılan göstergeleri doğruladıktan sonra kaydedin."
    )
    _render_pdf_company_form()


def render_company_list() -> None:
    st.title("Kayıtlı şirketler")

    companies = list_companies()
    latest_audits = {
        audit.symbol: audit for audit in list_latest_company_data_audits()
    }
    rows = []
    for company in companies:
        score = calculate_alpha_score(company)
        confidence = calculate_analysis_confidence(
            company, score, latest_audits.get(company.symbol)
        )
        rows.append(
            {
                "Hisse": company.symbol,
                "Profil": PROFILE_LABELS[CompanyProfile(company.company_profile)],
                "Şirket": company.company_name,
                "Alpha Score": score.total,
                "Veri yeterliliği (%)": score.data_completeness,
                "Not": score.grade,
                "Karar": confidence.decision,
                "Karar hazırlığı": (
                    "Hazır"
                    if confidence.decision_ready
                    else "Doğrulama gerekli"
                ),
                "Analiz güveni (%)": confidence.total,
                "Güven durumu": confidence.status,
                "Hesap kontrolü": confidence.calculation_check_status,
            }
        )

    if not rows:
        st.info("Henüz kayıtlı şirket bulunmuyor.")
        return

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={
            "Alpha Score": st.column_config.ProgressColumn(
                "Alpha Score",
                min_value=0,
                max_value=100,
                format="%.2f",
            ),
            "Analiz güveni (%)": st.column_config.ProgressColumn(
                "Analiz güveni (%)",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
        },
    )


def render_comparison() -> None:
    st.title("Şirket karşılaştırma")
    st.caption("Temel kaliteyi ve isteğe bağlı teknik zamanlamayı yan yana inceleyin.")

    companies = list_companies()
    if len(companies) < 2:
        st.info("Karşılaştırma için en az iki kayıtlı şirket gerekir.")
        return

    company_by_symbol = {company.symbol: company for company in companies}
    symbols = list(company_by_symbol)
    with st.form("comparison_form"):
        selected_symbols = st.multiselect(
            "Karşılaştırılacak şirketler",
            symbols,
            default=symbols[: min(2, len(symbols))],
            max_selections=5,
            help="En az 2, en fazla 5 şirket seçin.",
        )
        include_technical = st.toggle(
            "Teknik zamanlama puanlarını dahil et",
            value=False,
            help="Gecikmeli piyasa verisi alınacağı için ilk hesaplama biraz sürebilir.",
        )
        submitted = st.form_submit_button(
            "Karşılaştır",
            type="primary",
            icon=":material/compare_arrows:",
        )

    if not submitted:
        st.info("Şirketleri seçip karşılaştırmayı başlatın.")
        return
    if len(selected_symbols) < 2:
        st.warning("En az iki şirket seçin.")
        return

    selected_companies = [company_by_symbol[symbol] for symbol in selected_symbols]
    technical_scores = {}
    failed_symbols = []
    market_data_statuses: dict[str, str] = {}
    if include_technical:
        with st.spinner("Teknik puanlar hesaplanıyor..."):
            for symbol in selected_symbols:
                try:
                    quote, history = _load_market_data(symbol)
                    freshness = assess_price_freshness(
                        _quote_date(quote)
                    )
                    alignment = validate_quote_history_alignment(
                        quote,
                        history,
                    )
                    if freshness.current and alignment.valid:
                        technical_scores[symbol] = (
                            calculate_technical_score(history)
                        )
                        market_data_statuses[symbol] = "Doğrulandı"
                    else:
                        market_data_statuses[symbol] = (
                            f"{freshness.status}; {alignment.status}"
                        )
                except Exception:
                    failed_symbols.append(symbol)
                    market_data_statuses[symbol] = "Veri alınamadı"

        if failed_symbols:
            st.warning(
                "Piyasa verisi alınamayan şirketler yalnızca temel puanla "
                f"karşılaştırıldı: {', '.join(failed_symbols)}"
            )
        unverified_symbols = [
            symbol
            for symbol, status in market_data_statuses.items()
            if status != "Doğrulandı" and symbol not in failed_symbols
        ]
        if unverified_symbols:
            st.warning(
                "Piyasa verisi doğrulanamayan şirketlerin birleşik puanı "
                "hesaplanmadı: "
                + ", ".join(unverified_symbols)
            )

    latest_audits = {
        audit.symbol: audit for audit in list_latest_company_data_audits()
    }
    summary = build_comparison(
        selected_companies,
        technical_scores,
        latest_audits,
        market_data_statuses,
    )
    with st.container(horizontal=True):
        st.metric("Lider", summary.leader_symbol, border=True)
        st.metric(
            "Ortalama Alpha",
            f"{summary.average_alpha_score:.1f}/100",
            border=True,
        )
        if summary.average_combined_score is not None:
            st.metric(
                "Ortalama birleşik",
                f"{summary.average_combined_score:.1f}/100",
                border=True,
            )
        st.metric("Karşılaştırılan", len(summary.rows), border=True)
        st.metric(
            "Karara hazır",
            summary.decision_ready_count,
            border=True,
        )
        if include_technical:
            st.metric(
                "Teknik doğrulanan",
                f"{summary.technical_ready_count}/{len(summary.rows)}",
                border=True,
            )

    rows = []
    for rank, row in enumerate(summary.rows, start=1):
        rows.append(
            {
                "Sıra": rank,
                "Hisse": row.symbol,
                "Şirket": row.company_name,
                "Alpha": row.alpha_score,
                "Teknik": row.technical_score,
                "Birleşik": row.combined_score,
                "Not": row.grade,
                "Temel karar": row.decision,
                "Analiz güveni (%)": row.confidence_score,
                "Güven durumu": row.confidence_status,
                "Hesap kontrolü": row.calculation_check_status,
                "Karar hazırlığı": (
                    "Hazır" if row.decision_ready else "Doğrulama gerekli"
                ),
                "Teknik sinyal": row.technical_signal,
                "ATR (%)": row.atr_percent,
                "Piyasa veri kontrolü": (
                    row.market_data_status or "Dahil edilmedi"
                ),
            }
        )

    comparison_frame = pd.DataFrame(rows)
    with st.container(border=True):
        st.subheader("Puan sıralaması")
        st.dataframe(
            comparison_frame,
            hide_index=True,
            width="stretch",
            column_config={
                "Alpha": st.column_config.ProgressColumn(
                    "Alpha", min_value=0, max_value=100, format="%.1f"
                ),
                "Analiz güveni (%)": st.column_config.ProgressColumn(
                    "Analiz güveni (%)",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Teknik": st.column_config.NumberColumn(format="%.1f"),
                "Birleşik": st.column_config.NumberColumn(format="%.1f"),
                "ATR (%)": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    chart_columns = ["Alpha"]
    if technical_scores:
        chart_columns.extend(["Teknik", "Birleşik"])
    chart_frame = comparison_frame.set_index("Hisse")[chart_columns]
    with st.container(border=True):
        st.subheader("Puan görünümü")
        st.bar_chart(chart_frame)


def render_watchlist() -> None:
    st.title("Takip listesi")
    st.caption("Önem verdiğiniz şirketleri hedef Alpha puanlarıyla izleyin.")

    companies = list_companies()
    if not companies:
        st.info("Takip listesine eklemek için önce bir şirket kaydedin.")
        return

    company_by_symbol = {company.symbol: company for company in companies}
    with st.form("watchlist_add_form", border=True):
        st.subheader("Şirket ekle veya güncelle")
        symbol = st.selectbox("Hisse", list(company_by_symbol))
        target = st.slider("Hedef Alpha puanı", 0, 100, 80)
        note = st.text_input(
            "Kısa not",
            max_chars=200,
            placeholder="Örnek: Yeni bilanço sonrası yeniden değerlendir",
        )
        submitted = st.form_submit_button(
            "Takip listesine kaydet",
            type="primary",
            icon=":material/bookmark_add:",
        )

    if submitted:
        upsert_watchlist_entry(
            WatchlistEntry(
                symbol=symbol,
                note=note.strip(),
                target_alpha_score=target,
            )
        )
        st.success(f"{symbol} takip listesine kaydedildi.")

    entries = list_watchlist_entries()
    latest_audits = {
        audit.symbol: audit for audit in list_latest_company_data_audits()
    }
    technical_histories = {
        entry.symbol: list_technical_score_history(entry.symbol)
        for entry in entries
    }
    summary = build_watchlist_summary(
        entries,
        company_by_symbol,
        latest_audits,
        technical_histories,
    )
    if not summary.rows:
        st.info("Takip listeniz henüz boş.")
        return

    watchlist_quotes: dict[str, tuple[dict | None, object]] = {}
    with st.spinner("Takip listesi fiyatları doğrulanıyor..."):
        for row in summary.rows:
            try:
                quote = _load_quote(row.symbol)
                freshness = assess_price_freshness(_quote_date(quote))
                watchlist_quotes[row.symbol] = (quote, freshness)
            except Exception:
                watchlist_quotes[row.symbol] = (
                    None,
                    assess_price_freshness(None),
                )
    current_quote_count = sum(
        freshness.current
        for _, freshness in watchlist_quotes.values()
    )

    with st.container(horizontal=True):
        st.metric("Takip edilen", len(summary.rows), border=True)
        st.metric(
            "Ortalama Alpha",
            f"{summary.average_alpha_score:.1f}/100",
            border=True,
        )
        st.metric("Hedefe ulaşan", summary.targets_reached, border=True)
        st.metric(
            "Karara hazır",
            summary.decision_ready_count,
            border=True,
        )
        st.metric(
            "Güncel fiyat",
            f"{current_quote_count}/{len(summary.rows)}",
            border=True,
        )
        st.metric(
            "Güncel teknik kayıt",
            f"{summary.current_technical_count}/{len(summary.rows)}",
            border=True,
        )
        st.metric(
            "Teknik güçlenen",
            summary.technical_strengthening_count,
            border=True,
        )

    rows = [
        {
            "Hisse": row.symbol,
            "Şirket": row.company_name,
            "Alpha": row.alpha_score,
            "Hedef": row.target_alpha_score,
            "Son fiyat (TL)": (
                watchlist_quotes[row.symbol][0]["last"]
                if watchlist_quotes[row.symbol][0]
                else None
            ),
            "Fiyat tarihi": (
                _quote_date(watchlist_quotes[row.symbol][0])
                if watchlist_quotes[row.symbol][0]
                else None
            ),
            "Fiyat kaynağı": (
                watchlist_quotes[row.symbol][0].get("source") or "-"
                if watchlist_quotes[row.symbol][0]
                else "-"
            ),
            "Fiyat durumu": watchlist_quotes[row.symbol][1].status,
            "Teknik puan": row.technical_score,
            "Teknik değişim": row.technical_delta,
            "Teknik sinyal": (
                row.technical_signal if row.technical_current else "-"
            ),
            "Teknik fiyat tarihi": row.technical_price_date,
            "Teknik kayıt durumu": row.technical_status,
            "Durum": "Hedefte" if row.target_reached else "Hedef altında",
            "Not": row.grade,
            "Karar": row.decision,
            "Analiz güveni (%)": row.confidence_score,
            "Güven durumu": row.confidence_status,
            "Hesap kontrolü": row.calculation_check_status,
            "Karar hazırlığı": (
                "Hazır" if row.decision_ready else "Doğrulama gerekli"
            ),
            "Kullanıcı notu": row.note,
        }
        for row in summary.rows
    ]
    with st.container(border=True):
        st.subheader("İzlenen şirketler")
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            width="stretch",
            column_config={
                "Alpha": st.column_config.ProgressColumn(
                    "Alpha", min_value=0, max_value=100, format="%.1f"
                ),
                "Analiz güveni (%)": st.column_config.ProgressColumn(
                    "Analiz güveni (%)",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Hedef": st.column_config.NumberColumn(format="%.0f"),
                "Son fiyat (TL)": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "Fiyat tarihi": st.column_config.DateColumn(
                    "Fiyat tarihi",
                    format="DD.MM.YYYY",
                ),
                "Teknik puan": st.column_config.ProgressColumn(
                    "Teknik puan",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Teknik değişim": st.column_config.NumberColumn(
                    "Teknik değişim",
                    format="%+.1f",
                ),
                "Teknik fiyat tarihi": st.column_config.DateColumn(
                    "Teknik fiyat tarihi",
                    format="DD.MM.YYYY",
                ),
            },
        )

    with st.form("watchlist_remove_form"):
        remove_symbol = st.selectbox(
            "Listeden çıkarılacak hisse",
            [row.symbol for row in summary.rows],
        )
        remove_submitted = st.form_submit_button(
            "Listeden çıkar",
            icon=":material/bookmark_remove:",
        )
    if remove_submitted:
        remove_watchlist_entry(remove_symbol)
        st.success(f"{remove_symbol} takip listesinden çıkarıldı.")
        st.rerun()


def render_portfolio() -> None:
    st.title("Portföy")
    st.caption("Pozisyonlarınızın değerini, getirisini ve ağırlıklı Alpha Score'unu izleyin.")

    companies = list_companies()
    if not companies:
        st.info("Portföye eklemek için önce bir şirket kaydedin.")
        return

    company_by_symbol = {company.symbol: company for company in companies}
    with st.form("portfolio_position_form", border=True):
        st.subheader("Pozisyon ekle veya güncelle")
        symbol = st.selectbox("Hisse", list(company_by_symbol))
        quantity = st.number_input(
            "Lot",
            min_value=1.0,
            value=1.0,
            step=1.0,
            format="%.0f",
        )
        average_cost = st.number_input(
            "Ortalama maliyet (TL/lot)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.2f",
        )
        submitted = st.form_submit_button(
            "Portföye kaydet",
            type="primary",
            icon=":material/add_chart:",
        )

    if submitted:
        upsert_portfolio_position(
            PortfolioPosition(
                symbol=symbol,
                quantity=quantity,
                average_cost=average_cost,
            )
        )
        st.success(f"{symbol} pozisyonu portföye kaydedildi.")

    positions = list_portfolio_positions()
    if not positions:
        st.info("Portföyünüz henüz boş.")
        return

    prices: dict[str, PortfolioMarketPrice] = {}
    failed_symbols: list[str] = []
    with st.spinner("Gecikmeli fiyatlar alınıyor..."):
        for position in positions:
            try:
                quote = _load_quote(position.symbol)
                quote_date = (
                    date.fromisoformat(str(quote["as_of_date"]))
                    if quote.get("as_of_date")
                    else None
                )
                prices[position.symbol] = PortfolioMarketPrice(
                    value=float(quote["last"]),
                    as_of_date=quote_date,
                    source=str(quote.get("source") or ""),
                )
            except Exception:
                prices[position.symbol] = PortfolioMarketPrice(value=None)
                failed_symbols.append(position.symbol)

    latest_audits = {
        audit.symbol: audit for audit in list_latest_company_data_audits()
    }
    technical_histories = {
        position.symbol: list_technical_score_history(position.symbol)
        for position in positions
    }
    summary = build_portfolio_summary(
        positions,
        company_by_symbol,
        prices,
        latest_audits,
        technical_histories,
    )
    if failed_symbols:
        st.warning(
            "Fiyat alınamayan hisselerde güncel değer yerine maliyet kullanıldı: "
            + ", ".join(failed_symbols)
        )
    stale_symbols = [
        row.symbol
        for row in summary.rows
        if row.price_available and not row.price_current
    ]
    if stale_symbols:
        st.warning(
            "Fiyat tarihi güncel doğrulanamayan pozisyonlar var: "
            + ", ".join(stale_symbols)
        )

    with st.container(horizontal=True):
        st.metric(
            "Toplam maliyet",
            f"{_format_turkish_amount(summary.total_cost)} TL",
            border=True,
        )
        st.metric(
            "Güncel değer",
            f"{_format_turkish_amount(summary.total_market_value)} TL",
            border=True,
        )
        st.metric(
            "Kâr / zarar",
            f"{_format_turkish_amount(summary.total_profit_loss)} TL",
            f"%{summary.total_return_percent:+.2f}",
            border=True,
        )
        st.metric(
            "Ağırlıklı Alpha",
            f"{summary.weighted_alpha_score:.1f}/100",
            border=True,
        )
        st.metric(
            "Ağırlıklı teknik",
            (
                f"{summary.weighted_technical_score:.1f}/100"
                if summary.weighted_technical_score is not None
                else "-"
            ),
            border=True,
        )
        st.metric(
            "Birleşik portföy puanı",
            (
                f"{summary.weighted_combined_score:.1f}/100"
                if summary.weighted_combined_score is not None
                else "Doğrulama gerekli"
            ),
            border=True,
        )
        st.metric(
            "Ağırlıklı güven",
            (
                f"{summary.weighted_confidence_score:.1f}/100"
                if summary.weighted_confidence_score is not None
                else "-"
            ),
            border=True,
        )
        st.metric(
            "Karara hazır değer",
            f"%{summary.decision_ready_value_percent:.1f}",
            border=True,
        )
        st.metric(
            "En büyük pozisyon",
            summary.largest_position_symbol or "-",
            (
                f"%{summary.largest_position_percent:.1f}"
                if summary.largest_position_symbol
                else None
            ),
            border=True,
        )
        st.metric(
            "Çeşitlendirme",
            summary.diversification_status,
            border=True,
        )
        st.metric(
            "Etkin pozisyon",
            f"{summary.effective_position_count:.1f}",
            border=True,
        )
        st.metric(
            "Güncel fiyat",
            f"{summary.current_price_count}/{len(summary.rows)}",
            border=True,
        )
        st.metric(
            "Güncel fiyat kapsamı",
            f"%{summary.current_price_value_percent:.1f}",
            border=True,
        )
        st.metric(
            "Güncel teknik kapsamı",
            f"%{summary.current_technical_value_percent:.1f}",
            border=True,
        )

    if not summary.portfolio_score_ready:
        st.warning(
            "Birleşik portföy puanı için güncel fiyat, güncel teknik "
            "kayıt ve finansal karar kapsamlarının her biri en az %90 "
            "olmalıdır."
        )
        if summary.score_readiness_issues:
            with st.container(border=True):
                st.subheader("Birleşik puan doğrulama listesi")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Hisse": issue.symbol,
                                "Portföy ağırlığı (%)": (
                                    issue.weight_percent
                                ),
                                "Fiyat": issue.price_status,
                                "Teknik kayıt": (
                                    issue.technical_status
                                ),
                                "Finansal analiz": (
                                    issue.financial_status
                                ),
                            }
                            for issue in summary.score_readiness_issues
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Portföy ağırlığı (%)": (
                            st.column_config.ProgressColumn(
                                "Portföy ağırlığı (%)",
                                min_value=0,
                                max_value=100,
                                format="%.1f",
                            )
                        ),
                    },
                )

    st.caption(
        "Ağırlık bazlı yoğunlaşma endeksi: "
        f"{summary.concentration_index:.1f}/100"
    )

    if summary.verification_required_count:
        pending_symbols = [
            row.symbol for row in summary.rows if not row.decision_ready
        ]
        st.warning(
            f"{summary.verification_required_count} pozisyon doğrulama "
            "gerektiriyor: "
            + ", ".join(pending_symbols)
        )
    for warning in summary.concentration_warnings:
        st.warning(warning)

    rows = [
        {
            "Hisse": row.symbol,
            "Şirket": row.company_name,
            "Lot": row.quantity,
            "Maliyet (TL)": row.average_cost,
            "Son fiyat (TL)": row.last_price,
            "Fiyat tarihi": row.price_as_of_date,
            "Fiyat yaşı (gün)": row.price_age_days,
            "Fiyat kaynağı": row.price_source or "-",
            "Güncel değer (TL)": row.market_value,
            "Kâr / zarar (TL)": row.profit_loss,
            "Getiri (%)": row.return_percent,
            "Alpha": row.alpha_score,
            "Portföy ağırlığı (%)": row.weight_percent,
            "Analiz güveni (%)": row.confidence_score,
            "Güven durumu": row.confidence_status,
            "Karar": row.decision,
            "Karar hazırlığı": (
                "Hazır" if row.decision_ready else "Doğrulama gerekli"
            ),
            "Hesap kontrolü": row.calculation_check_status,
            "Fiyat durumu": row.price_status,
            "Teknik puan": row.technical_score,
            "Teknik sinyal": (
                row.technical_signal if row.technical_current else "-"
            ),
            "Teknik fiyat tarihi": row.technical_price_date,
            "Teknik kayıt durumu": row.technical_status,
        }
        for row in summary.rows
    ]
    with st.container(border=True):
        st.subheader("Pozisyonlar")
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            width="stretch",
            column_config={
                "Lot": st.column_config.NumberColumn(format="%.0f"),
                "Maliyet (TL)": st.column_config.NumberColumn(format="%.2f"),
                "Son fiyat (TL)": st.column_config.NumberColumn(format="%.2f"),
                "Fiyat tarihi": st.column_config.DateColumn(
                    "Fiyat tarihi",
                    format="DD.MM.YYYY",
                ),
                "Fiyat yaşı (gün)": st.column_config.NumberColumn(
                    "Fiyat yaşı (gün)",
                    format="%d",
                ),
                "Güncel değer (TL)": st.column_config.NumberColumn(format="localized"),
                "Kâr / zarar (TL)": st.column_config.NumberColumn(format="localized"),
                "Getiri (%)": st.column_config.NumberColumn(format="%.2f"),
                "Alpha": st.column_config.ProgressColumn(
                    "Alpha", min_value=0, max_value=100, format="%.1f"
                ),
                "Portföy ağırlığı (%)": st.column_config.ProgressColumn(
                    "Portföy ağırlığı (%)",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Analiz güveni (%)": st.column_config.ProgressColumn(
                    "Analiz güveni (%)",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Teknik puan": st.column_config.ProgressColumn(
                    "Teknik puan",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Teknik fiyat tarihi": st.column_config.DateColumn(
                    "Teknik fiyat tarihi",
                    format="DD.MM.YYYY",
                ),
            },
        )

    if summary.profile_exposure:
        exposure_frame = pd.DataFrame(
            [
                {
                    "Profil": PROFILE_LABELS[
                        CompanyProfile(profile)
                    ],
                    "Ağırlık (%)": weight,
                }
                for profile, weight in summary.profile_exposure.items()
            ]
        ).sort_values("Ağırlık (%)", ascending=False)
        with st.container(border=True):
            st.subheader("Şirket profili dağılımı")
            st.bar_chart(
                exposure_frame,
                x="Profil",
                y="Ağırlık (%)",
                horizontal=True,
            )

    if summary.stress_scenarios:
        stress_frame = pd.DataFrame(
            [
                {
                    "Senaryo": scenario.label,
                    "Etkilenen": scenario.affected_scope,
                    "Fiyat şoku (%)": scenario.shock_percent,
                    "Tahmini portföy değeri (TL)": (
                        scenario.projected_market_value
                    ),
                    "Değer değişimi (TL)": scenario.value_change,
                    "Tahmini kâr / zarar (TL)": (
                        scenario.projected_profit_loss
                    ),
                    "Maliyete göre getiri (%)": (
                        scenario.projected_return_percent
                    ),
                }
                for scenario in summary.stress_scenarios
            ]
        )
        with st.container(border=True):
            st.subheader("Basit fiyat stres testi")
            if not summary.stress_test_ready:
                st.warning(
                    "Güncel fiyat kapsamı "
                    f"%{summary.current_price_value_percent:.1f}. "
                    "Stres sonuçları için en az %90 güncel fiyat kapsamı "
                    "gereklidir; aşağıdaki değerleri doğrulama amacıyla "
                    "kullanın."
                )
            st.caption(
                "İlk üç senaryo tüm portföye, yoğunlaşma senaryoları ise "
                "yalnızca belirtilen pozisyon veya şirket profiline "
                "uygulanır. Sonuçlar mekanik senaryodur; korelasyon veya "
                "gelecek fiyat tahmini içermez."
            )
            st.dataframe(
                stress_frame,
                hide_index=True,
                width="stretch",
                column_config={
                    "Fiyat şoku (%)": st.column_config.NumberColumn(
                        "Fiyat şoku (%)",
                        format="%+.1f",
                    ),
                    "Tahmini portföy değeri (TL)": (
                        st.column_config.NumberColumn(format="localized")
                    ),
                    "Değer değişimi (TL)": st.column_config.NumberColumn(
                        format="localized"
                    ),
                    "Tahmini kâr / zarar (TL)": (
                        st.column_config.NumberColumn(format="localized")
                    ),
                    "Maliyete göre getiri (%)": (
                        st.column_config.NumberColumn(format="%+.2f")
                    ),
                },
            )

    with st.form("portfolio_remove_form"):
        remove_symbol = st.selectbox(
            "Portföyden çıkarılacak hisse",
            [row.symbol for row in summary.rows],
        )
        remove_submitted = st.form_submit_button(
            "Portföyden çıkar",
            icon=":material/delete:",
        )
    if remove_submitted:
        remove_portfolio_position(remove_symbol)
        st.success(f"{remove_symbol} portföyden çıkarıldı.")
        st.rerun()


def render_data_backup() -> None:
    st.title("Veri yedekleme")

    with st.container(border=True):
        st.subheader("Yedeği indir")
        try:
            backup_data = create_database_backup()
        except FileNotFoundError as exc:
            st.error(str(exc))
        else:
            st.metric(
                "Yedek boyutu",
                f"{len(backup_data) / 1024:.1f} KB",
                border=True,
            )
            st.download_button(
                "Yedeği indir",
                data=backup_data,
                file_name=(
                    f"alphabist-yedek-{date.today():%Y%m%d}.db"
                ),
                mime="application/x-sqlite3",
                icon=":material/download:",
                type="primary",
                width="stretch",
            )

    with st.container(border=True):
        st.subheader("Yedeği geri yükle")
        uploaded = st.file_uploader(
            "AlphaBIST yedek dosyası",
            type="db",
            max_upload_size=100,
            key="database_restore_upload",
        )
        validation = None
        if uploaded is not None:
            validation = validate_database_backup(uploaded.getvalue())
            if validation.valid:
                st.success(validation.message)
                st.caption(
                    f"Doğrulanan tablo sayısı: {len(validation.tables)}"
                )
            else:
                st.error(validation.message)

        confirmed = st.checkbox(
            "Mevcut kayıtların yedekteki verilerle değiştirileceğini onaylıyorum.",
            disabled=validation is None or not validation.valid,
        )
        restore_submitted = st.button(
            "Yedeği geri yükle",
            icon=":material/restore:",
            type="primary",
            disabled=(
                validation is None
                or not validation.valid
                or not confirmed
            ),
        )
        if restore_submitted and uploaded is not None:
            try:
                safety_backup = restore_database_backup(
                    uploaded.getvalue()
                )
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))
            else:
                st.success("Yedek başarıyla geri yüklendi.")
                if safety_backup is not None:
                    st.caption(
                        "Önceki veriler güvenlik kopyasına alındı: "
                        f"{safety_backup.name}"
                    )

    with st.container(border=True):
        st.subheader("Güvenlik kopyaları")
        safety_backups = list_safety_backups()
        if not safety_backups:
            st.info("Henüz geri yükleme güvenlik kopyası bulunmuyor.")
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Dosya": item.file_name,
                            "Tarih": item.modified_at,
                            "Boyut (KB)": item.size_bytes / 1024,
                            "Bütünlük": (
                                "Doğrulandı"
                                if item.valid
                                else "Geçersiz"
                            ),
                        }
                        for item in safety_backups
                    ]
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    "Tarih": st.column_config.DatetimeColumn(
                        "Tarih",
                        format="DD.MM.YYYY HH:mm:ss",
                    ),
                    "Boyut (KB)": st.column_config.NumberColumn(
                        "Boyut (KB)",
                        format="%.1f",
                    ),
                },
            )
            selected_backup = st.selectbox(
                "İndirilecek güvenlik kopyası",
                safety_backups,
                format_func=lambda item: item.file_name,
            )
            if selected_backup.valid:
                st.download_button(
                    "Güvenlik kopyasını indir",
                    data=selected_backup.path.read_bytes(),
                    file_name=selected_backup.file_name,
                    mime="application/x-sqlite3",
                    icon=":material/download:",
                    width="stretch",
                )
            else:
                st.error(
                    "Seçilen güvenlik kopyası bütünlük kontrolünü geçemedi."
                )
