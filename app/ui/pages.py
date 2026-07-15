import hashlib

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from app.analysis.service import build_company_analysis
from app.comparison.service import build_comparison
from app.core.constants import CATEGORY_MAX_POINTS
from app.core.exceptions import PdfParsingError, ValidationError as AppValidationError
from app.database.repository import (
    add_score_history,
    get_company,
    list_companies,
    list_portfolio_positions,
    list_score_history,
    list_watchlist_entries,
    remove_watchlist_entry,
    remove_portfolio_position,
    upsert_company,
    upsert_portfolio_position,
    upsert_watchlist_entry,
)
from app.market_data.provider import get_history, get_quote
from app.parser.converter import to_financial_metrics
from app.parser.extractor import (
    extract_activity_report,
    extract_financial_report,
    parse_turkish_number,
)
from app.parser.models import (
    ActivityReportExtractionResult,
    FinancialReportDraft,
    PdfExtractionResult,
)
from app.portfolio.models import PortfolioPosition
from app.portfolio.service import build_portfolio_summary
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.sector.profiles import CompanyProfile, PROFILE_LABELS
from app.scanner.models import ScannerFilters
from app.scanner.service import scan_companies
from app.technical.engine import calculate_combined_score, calculate_technical_score
from app.technical.models import TechnicalScoreBreakdown
from app.watchlist.models import WatchlistEntry
from app.watchlist.service import build_watchlist_summary
from app.validation.service import validate_financial_metrics


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


@st.cache_data(show_spinner=False, max_entries=10)
def _parse_pdf(file_bytes: bytes, file_name: str = "") -> PdfExtractionResult:
    return extract_financial_report(file_bytes, file_name)


@st.cache_data(show_spinner=False, max_entries=10)
def _parse_activity_pdf(
    file_bytes: bytes,
    file_name: str = "",
) -> ActivityReportExtractionResult:
    return extract_activity_report(file_bytes, file_name)


@st.cache_data(ttl="15m", max_entries=50, show_spinner=False)
def _load_market_data(symbol: str):
    return get_quote(symbol), get_history(symbol)


@st.cache_data(ttl="15m", max_entries=100, show_spinner=False)
def _load_quote(symbol: str):
    return get_quote(symbol)


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


def _format_turkish_amount(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def _amount_input(label: str, value: float, key: str) -> str:
    return st.text_input(
        f"{label} (TL)",
        value=_format_turkish_amount(value),
        key=key,
        help="Tutarı TL olarak girin. Binlik ayırıcı olarak nokta kullanabilirsiniz.",
    )


def _parse_amount_input(label: str, raw_value: str) -> float:
    try:
        return parse_turkish_number(raw_value)
    except ValueError as exc:
        raise AppValidationError(f"{label} geçerli bir TL tutarı değil.") from exc


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
    score_history = list_score_history(symbol)
    score_delta = None
    if len(score_history) >= 2:
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
        st.metric("Karar", score.decision, border=True)
        st.metric("Hisse", company.symbol, border=True)

    st.caption(
        f"Profil: {PROFILE_LABELS[CompanyProfile(company.company_profile)]} | "
        f"Veri yeterliliği: %{score.data_completeness:.0f}"
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
            technical_score = calculate_technical_score(history)
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
                technical_score.signal,
                border=True,
            )
            st.metric(
                "Birleşik AI puanı",
                f"{combined_score:.1f}/100",
                "Temel %70 + teknik %30",
                border=True,
            )
            st.metric(
                "ATR oynaklığı",
                f"%{technical_score.atr_percent:.2f}",
                border=True,
            )
        st.caption("Piyasa verisi gecikmeli olabilir.")

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
    except Exception as exc:
        st.warning(f"Piyasa verisi alınamadı: {exc}")


def render_scanner() -> None:
    st.title("Hisse tarayıcı")

    companies = list_companies()
    if not companies:
        st.info("Tarama için önce şirket verisi kaydedin.")
        return

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
        st.form_submit_button(
            "Filtrele",
            type="primary",
            icon=":material/filter_alt:",
        )

    summary = scan_companies(
        companies,
        ScannerFilters(
            minimum_alpha_score=minimum_alpha,
            minimum_revenue_growth=minimum_revenue_growth,
            minimum_net_margin=minimum_net_margin,
            maximum_debt_to_equity=maximum_debt_to_equity,
            positive_operating_cash_flow_only=positive_cash_flow,
        ),
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
            "Ciro büyümesi (%)": row.revenue_growth,
            "Net marj (%)": row.net_margin,
            "ROE (%)": row.roe,
            "Borç / özkaynak": row.debt_to_equity,
            "Cari oran": row.current_ratio,
            "Operasyonel nakit (TL)": row.operating_cash_flow,
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
                "Ciro büyümesi (%)": st.column_config.NumberColumn(format="%.2f"),
                "Net marj (%)": st.column_config.NumberColumn(format="%.2f"),
                "ROE (%)": st.column_config.NumberColumn(format="%.2f"),
                "Borç / özkaynak": st.column_config.NumberColumn(format="%.4f"),
                "Cari oran": st.column_config.NumberColumn(format="%.2f"),
                "Operasyonel nakit (TL)": st.column_config.NumberColumn(
                    format="localized"
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
    document_token = hashlib.sha256(financial_bytes + activity_bytes).hexdigest()
    if st.session_state.get("company_pdf_token") != document_token:
        for key in list(st.session_state):
            if key.startswith("pdf_field_") or key == "pdf_period":
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

    draft = financial_result.draft
    if activity_result:
        metadata = activity_result.metadata
        activity_updates = dict(activity_result.sector_metrics)
        activity_updates.update(
            {
                "symbol": metadata.symbol or draft.symbol,
                "company_name": metadata.company_name or draft.company_name,
                "period_months": metadata.period_months or draft.period_months,
                "company_profile": (
                    metadata.company_profile
                    if metadata.company_profile != CompanyProfile.STANDARD
                    else draft.company_profile
                ),
            }
        )
        draft = draft.model_copy(
            update=activity_updates
        )

    with st.container(horizontal=True):
        st.metric(
            "Bulunan finansal kalem",
            len(financial_result.extracted_fields),
            border=True,
        )
        st.metric("Finansal rapor", f"{financial_result.page_count} sayfa", border=True)
        if activity_result:
            st.metric("Faaliyet raporu", f"{activity_result.page_count} sayfa", border=True)

    for warning in financial_result.warnings:
        st.warning(warning)
    if activity_result:
        for warning in activity_result.warnings:
            st.warning(warning)

    with st.expander("PDF'den bulunan kaynak değerler"):
        source_rows = [
            ("Hasılat", draft.revenue),
            ("Önceki dönem hasılat", draft.previous_revenue),
            ("Net dönem kârı", draft.net_profit),
            ("Önceki dönem net kârı", draft.previous_net_profit),
            ("Özkaynak", draft.equity),
            ("Finansal borç", draft.total_debt),
            ("Dönen varlık", draft.current_assets),
            ("Kısa vadeli yükümlülük", draft.current_liabilities),
            ("Operasyonel nakit akışı", draft.operating_cash_flow),
            ("Yatırım harcaması", draft.capital_expenditures),
            ("Toplam varlık", draft.total_assets),
        ]
        st.dataframe(
            pd.DataFrame(
                [
                    {"Finansal kalem": label, "Tutar (TL)": _format_turkish_amount(value)}
                    for label, value in source_rows
                ]
            ),
            hide_index=True,
            width="stretch",
        )

    period_options = [3, 6, 9, 12]
    period_default = draft.period_months if draft.period_months in period_options else 3
    period_months = st.selectbox(
        "Rapor dönemi",
        period_options,
        index=period_options.index(period_default),
        format_func=lambda value: f"{value} aylık",
        key="pdf_period",
    )
    company_profile = _profile_select(
        "Şirket türü / sektör profili",
        draft.company_profile,
        "pdf_company_profile",
    )
    calculation_draft = draft.model_copy(
        update={
            "symbol": draft.symbol or "TEMP",
            "company_name": draft.company_name or "Geçici şirket",
            "period_months": period_months,
            "company_profile": company_profile,
        }
    )
    defaults = to_financial_metrics(calculation_draft)
    if abs(defaults.roe) > 100:
        st.warning(
            f"Yıllıklandırılmış ROE %{defaults.roe:,.1f}. Tek seferlik gelirler veya "
            "düşük özkaynak nedeniyle yüksek olabilir; kaydetmeden önce kontrol edin."
        )
    if defaults.debt_to_equity > 10:
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
                value=float(defaults.revenue_growth),
                step=0.1,
                format="%.2f",
                key="pdf_field_revenue_growth",
            )
            net_profit_growth = st.number_input(
                "Net kâr büyümesi (%)",
                value=float(defaults.net_profit_growth),
                step=0.1,
                format="%.2f",
                key="pdf_field_profit_growth",
            )
            net_margin = st.number_input(
                "Net kâr marjı (%)",
                value=float(defaults.net_margin),
                step=0.1,
                format="%.2f",
                key="pdf_field_net_margin",
            )
            roe = st.number_input(
                "ROE (%)",
                value=float(defaults.roe),
                step=0.1,
                format="%.2f",
                key="pdf_field_roe",
            )
            debt_to_equity = st.number_input(
                "Borç / özkaynak",
                value=float(defaults.debt_to_equity),
                min_value=0.0,
                step=0.01,
                format="%.4f",
                key="pdf_field_debt_to_equity",
            )
            current_ratio = st.number_input(
                "Cari oran",
                value=float(defaults.current_ratio),
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
                value=float(defaults.asset_turnover),
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
    )


def _validate_and_save_company(
    *,
    symbol: str,
    company_name: str,
    revenue_growth: float,
    net_profit_growth: float,
    net_margin: float,
    roe: float,
    debt_to_equity: float,
    current_ratio: float,
    operating_cash_flow: float,
    free_cash_flow: float,
    asset_turnover: float,
    valuation: float,
    management: float,
    risk: float,
    company_profile: CompanyProfile = CompanyProfile.STANDARD,
    sector_metrics: dict[str, float | None] | None = None,
) -> None:
    sector_metrics = sector_metrics or {}
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
        "Finansal raporu yükleyin, bulunan rakamları doğrulayın ve puanı kaydedin."
    )

    uploaded_file = st.file_uploader(
        "Finansal rapor",
        type=["pdf"],
        help="Metin katmanı bulunan SPK veya KAP finansal raporlarını kullanın.",
    )
    if uploaded_file is None:
        st.info("Başlamak için bir finansal rapor PDF'i yükleyin.")
        return

    file_bytes = uploaded_file.getvalue()
    try:
        with st.spinner("Finansal kalemler aranıyor..."):
            result = _parse_pdf(file_bytes, uploaded_file.name)
    except PdfParsingError as exc:
        st.error(str(exc))
        return

    detected_col, page_col = st.columns(2)
    detected_col.metric("Bulunan kalem", len(result.extracted_fields))
    page_col.metric("PDF sayfası", result.page_count)
    for warning in result.warnings:
        st.warning(warning)

    draft = result.draft
    with st.form("pdf_verification_form"):
        st.subheader("Şirket ve dönem")
        symbol = st.text_input("Hisse kodu", value=draft.symbol)
        company_name = st.text_input("Şirket adı", value=draft.company_name)
        period_options = [3, 6, 9, 12]
        period_default = (
            draft.period_months if draft.period_months in period_options else 3
        )
        period_months = st.selectbox(
            "Rapor dönemi",
            period_options,
            index=period_options.index(period_default),
            format_func=lambda value: f"{value} aylık",
        )

        st.subheader("Gelir ve kârlılık")
        left, right = st.columns(2)
        with left:
            revenue_input = _amount_input(
                "Hasılat",
                draft.revenue,
                key="verification_revenue",
            )
            net_profit_input = _amount_input(
                "Net dönem kârı",
                draft.net_profit,
                key="verification_net_profit",
            )
        with right:
            previous_revenue_input = _amount_input(
                "Önceki dönem hasılat",
                draft.previous_revenue,
                key="verification_previous_revenue",
            )
            previous_net_profit_input = _amount_input(
                "Önceki dönem net kâr",
                draft.previous_net_profit,
                key="verification_previous_net_profit",
            )

        st.subheader("Bilanço")
        left, right = st.columns(2)
        with left:
            equity_input = _amount_input(
                "Özkaynak", draft.equity, key="verification_equity"
            )
            total_debt_input = _amount_input(
                "Finansal borç",
                draft.total_debt,
                key="verification_total_debt",
            )
            cash_input = _amount_input(
                "Nakit", draft.cash, key="verification_cash"
            )
            total_assets_input = _amount_input(
                "Toplam varlık",
                draft.total_assets,
                key="verification_total_assets",
            )
        with right:
            current_assets_input = _amount_input(
                "Dönen varlık",
                draft.current_assets,
                key="verification_current_assets",
            )
            current_liabilities_input = _amount_input(
                "Kısa vadeli yükümlülük",
                draft.current_liabilities,
                key="verification_current_liabilities",
            )
            operating_cash_flow_input = _amount_input(
                "Operasyonel nakit akışı",
                draft.operating_cash_flow,
                key="verification_operating_cash_flow",
            )
            capital_expenditures_input = _amount_input(
                "Yatırım harcaması",
                draft.capital_expenditures,
                key="verification_capital_expenditures",
            )

        st.subheader("Nitel değerlendirme")
        valuation = st.slider("Değerleme girdisi", 0, 100, 50)
        management = st.slider("Yönetim girdisi", 0, 100, 70)
        risk = st.slider("Risk dayanıklılığı", 0, 100, 50)

        submitted = st.form_submit_button(
            "Doğrula, hesapla ve kaydet",
            type="primary",
            icon=":material/document_scanner:",
        )

    if not submitted:
        return

    try:
        revenue = _parse_amount_input("Hasılat", revenue_input)
        previous_revenue = _parse_amount_input(
            "Önceki dönem hasılat", previous_revenue_input
        )
        net_profit = _parse_amount_input("Net dönem kârı", net_profit_input)
        previous_net_profit = _parse_amount_input(
            "Önceki dönem net kâr", previous_net_profit_input
        )
        equity = _parse_amount_input("Özkaynak", equity_input)
        total_debt = _parse_amount_input("Finansal borç", total_debt_input)
        cash = _parse_amount_input("Nakit", cash_input)
        total_assets = _parse_amount_input("Toplam varlık", total_assets_input)
        current_assets = _parse_amount_input("Dönen varlık", current_assets_input)
        current_liabilities = _parse_amount_input(
            "Kısa vadeli yükümlülük", current_liabilities_input
        )
        operating_cash_flow = _parse_amount_input(
            "Operasyonel nakit akışı", operating_cash_flow_input
        )
        capital_expenditures = _parse_amount_input(
            "Yatırım harcaması", capital_expenditures_input
        )
        verified_draft = FinancialReportDraft(
            symbol=symbol,
            company_name=company_name,
            period_months=period_months,
            revenue=revenue,
            previous_revenue=previous_revenue,
            net_profit=net_profit,
            previous_net_profit=previous_net_profit,
            equity=equity,
            total_debt=total_debt,
            cash=cash,
            current_assets=current_assets,
            current_liabilities=current_liabilities,
            operating_cash_flow=operating_cash_flow,
            capital_expenditures=capital_expenditures,
            total_assets=total_assets,
            valuation_score_input=valuation,
            management_score_input=management,
            risk_score_input=risk,
        )
        metrics = to_financial_metrics(verified_draft)
    except (ValidationError, AppValidationError) as exc:
        st.error(f"Doğrulanan bilgiler geçerli değil: {exc}")
        return

    upsert_company(metrics)
    score = calculate_alpha_score(metrics)
    add_score_history(metrics.symbol, score)
    st.success(
        f"{metrics.symbol} kaydedildi. Alpha Score: {score.total:.1f}/100"
    )

    with st.container(border=True):
        st.metric("Alpha Score", f"{score.total:.1f}/100")
        st.caption(f"Not: {score.grade} | Karar: {score.decision}")
        st.dataframe(_score_table(score), hide_index=True, width="stretch")


def render_pdf_analysis() -> None:
    st.title("PDF analizi")
    st.caption(
        "Finansal ve faaliyet raporlarını birlikte okuyun; sektör profilini ve "
        "çıkarılan göstergeleri doğruladıktan sonra kaydedin."
    )
    _render_pdf_company_form()


def render_company_list() -> None:
    st.title("Kayıtlı şirketler")

    rows = []
    for company in list_companies():
        score = calculate_alpha_score(company)
        rows.append(
            {
                "Hisse": company.symbol,
                "Profil": PROFILE_LABELS[CompanyProfile(company.company_profile)],
                "Şirket": company.company_name,
                "Alpha Score": score.total,
                "Veri yeterliliği (%)": score.data_completeness,
                "Not": score.grade,
                "Karar": score.decision,
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
            )
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
    if include_technical:
        with st.spinner("Teknik puanlar hesaplanıyor..."):
            for symbol in selected_symbols:
                try:
                    _, history = _load_market_data(symbol)
                    technical_scores[symbol] = calculate_technical_score(history)
                except Exception:
                    failed_symbols.append(symbol)

        if failed_symbols:
            technical_scores = {}
            st.warning(
                "Bazı piyasa verileri alınamadığı için karşılaştırma yalnızca "
                f"temel puanlarla hazırlandı: {', '.join(failed_symbols)}"
            )

    summary = build_comparison(selected_companies, technical_scores)
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
                "Teknik sinyal": row.technical_signal,
                "ATR (%)": row.atr_percent,
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
    summary = build_watchlist_summary(entries, company_by_symbol)
    if not summary.rows:
        st.info("Takip listeniz henüz boş.")
        return

    with st.container(horizontal=True):
        st.metric("Takip edilen", len(summary.rows), border=True)
        st.metric(
            "Ortalama Alpha",
            f"{summary.average_alpha_score:.1f}/100",
            border=True,
        )
        st.metric("Hedefe ulaşan", summary.targets_reached, border=True)

    rows = [
        {
            "Hisse": row.symbol,
            "Şirket": row.company_name,
            "Alpha": row.alpha_score,
            "Hedef": row.target_alpha_score,
            "Durum": "Hedefte" if row.target_reached else "Hedef altında",
            "Not": row.grade,
            "Karar": row.decision,
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
                "Hedef": st.column_config.NumberColumn(format="%.0f"),
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

    prices: dict[str, float | None] = {}
    failed_symbols: list[str] = []
    with st.spinner("Gecikmeli fiyatlar alınıyor..."):
        for position in positions:
            try:
                quote = _load_quote(position.symbol)
                prices[position.symbol] = float(quote["last"])
            except Exception:
                prices[position.symbol] = None
                failed_symbols.append(position.symbol)

    summary = build_portfolio_summary(positions, company_by_symbol, prices)
    if failed_symbols:
        st.warning(
            "Fiyat alınamayan hisselerde güncel değer yerine maliyet kullanıldı: "
            + ", ".join(failed_symbols)
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

    rows = [
        {
            "Hisse": row.symbol,
            "Şirket": row.company_name,
            "Lot": row.quantity,
            "Maliyet (TL)": row.average_cost,
            "Son fiyat (TL)": row.last_price,
            "Güncel değer (TL)": row.market_value,
            "Kâr / zarar (TL)": row.profit_loss,
            "Getiri (%)": row.return_percent,
            "Alpha": row.alpha_score,
            "Fiyat durumu": "Güncel" if row.price_available else "Fiyat bekleniyor",
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
                "Güncel değer (TL)": st.column_config.NumberColumn(format="localized"),
                "Kâr / zarar (TL)": st.column_config.NumberColumn(format="localized"),
                "Getiri (%)": st.column_config.NumberColumn(format="%.2f"),
                "Alpha": st.column_config.ProgressColumn(
                    "Alpha", min_value=0, max_value=100, format="%.1f"
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
