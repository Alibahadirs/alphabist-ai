import pandas as pd
import streamlit as st
from pydantic import ValidationError

from app.comparison.service import build_comparison
from app.core.constants import CATEGORY_MAX_POINTS
from app.core.exceptions import PdfParsingError, ValidationError as AppValidationError
from app.database.repository import get_company, list_companies, upsert_company
from app.market_data.provider import get_history, get_quote
from app.parser.converter import to_financial_metrics
from app.parser.extractor import extract_financial_report
from app.parser.models import FinancialReportDraft, PdfExtractionResult
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.technical.engine import calculate_combined_score, calculate_technical_score
from app.technical.models import TechnicalScoreBreakdown


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
def _parse_pdf(file_bytes: bytes) -> PdfExtractionResult:
    return extract_financial_report(file_bytes)


@st.cache_data(ttl="15m", max_entries=50, show_spinner=False)
def _load_market_data(symbol: str):
    return get_quote(symbol), get_history(symbol)


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
    score_col, grade_col, decision_col, company_col = st.columns(4)
    score_col.metric("Alpha Score", f"{score.total:.1f}/100")
    grade_col.metric("Not", score.grade)
    decision_col.metric("Karar", score.decision)
    company_col.metric("Hisse", company.symbol)

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


def render_company_form() -> None:
    st.title("Şirket ekle veya güncelle")
    st.caption("Finansal verileri yüzde değerleriyle girin ve puanı hesaplayın.")

    with st.form("company_form"):
        symbol = st.text_input("Hisse kodu", "ASELS")
        company_name = st.text_input(
            "Şirket adı",
            "Aselsan Elektronik Sanayi ve Ticaret A.Ş.",
        )

        left, right = st.columns(2)
        with left:
            revenue_growth = st.number_input("Ciro büyümesi (%)", value=10.0)
            net_profit_growth = st.number_input(
                "Net kâr büyümesi (%)",
                value=10.0,
            )
            net_margin = st.number_input("Net kâr marjı (%)", value=10.0)
            roe = st.number_input("ROE (%)", value=15.0)
            debt_to_equity = st.number_input(
                "Borç / özkaynak",
                value=0.5,
                min_value=0.0,
            )
            current_ratio = st.number_input(
                "Cari oran",
                value=1.5,
                min_value=0.0,
            )

        with right:
            operating_cash_flow = st.number_input(
                "Operasyonel nakit akışı",
                value=1_000_000.0,
            )
            free_cash_flow = st.number_input(
                "Serbest nakit akışı",
                value=500_000.0,
            )
            asset_turnover = st.number_input(
                "Aktif devir hızı",
                value=0.7,
                min_value=0.0,
            )
            valuation = st.slider("Değerleme girdisi", 0, 100, 70)
            management = st.slider("Yönetim girdisi", 0, 100, 75)
            risk = st.slider("Risk dayanıklılığı", 0, 100, 65)

        submitted = st.form_submit_button(
            "Hesapla ve kaydet",
            type="primary",
            icon=":material/save:",
        )

    if not submitted:
        return

    try:
        metrics = FinancialMetrics(
            symbol=symbol.upper().strip(),
            company_name=company_name.strip(),
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
        )
    except ValidationError as exc:
        st.error(f"Girilen bilgiler geçerli değil: {exc}")
        return

    upsert_company(metrics)
    score = calculate_alpha_score(metrics)
    st.success(
        f"{metrics.symbol} kaydedildi. Alpha Score: {score.total:.1f}/100"
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
            result = _parse_pdf(file_bytes)
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
        symbol = st.text_input("Hisse kodu")
        company_name = st.text_input("Şirket adı")
        period_months = st.selectbox(
            "Rapor dönemi",
            [3, 6, 9, 12],
            format_func=lambda value: f"{value} aylık",
        )

        st.subheader("Gelir ve kârlılık")
        left, right = st.columns(2)
        with left:
            revenue = st.number_input("Hasılat", value=float(draft.revenue))
            net_profit = st.number_input(
                "Net dönem kârı",
                value=float(draft.net_profit),
            )
        with right:
            previous_revenue = st.number_input(
                "Önceki dönem hasılat",
                value=float(draft.previous_revenue),
            )
            previous_net_profit = st.number_input(
                "Önceki dönem net kâr",
                value=float(draft.previous_net_profit),
            )

        st.subheader("Bilanço")
        left, right = st.columns(2)
        with left:
            equity = st.number_input("Özkaynak", value=float(draft.equity))
            total_debt = st.number_input(
                "Finansal borç",
                value=float(draft.total_debt),
            )
            cash = st.number_input("Nakit", value=float(draft.cash))
            total_assets = st.number_input(
                "Toplam varlık",
                value=float(draft.total_assets),
            )
        with right:
            current_assets = st.number_input(
                "Dönen varlık",
                value=float(draft.current_assets),
            )
            current_liabilities = st.number_input(
                "Kısa vadeli yükümlülük",
                value=float(draft.current_liabilities),
            )
            operating_cash_flow = st.number_input(
                "Operasyonel nakit akışı",
                value=float(draft.operating_cash_flow),
            )
            capital_expenditures = st.number_input(
                "Yatırım harcaması",
                value=float(draft.capital_expenditures),
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
    st.success(
        f"{metrics.symbol} kaydedildi. Alpha Score: {score.total:.1f}/100"
    )

    with st.container(border=True):
        st.metric("Alpha Score", f"{score.total:.1f}/100")
        st.caption(f"Not: {score.grade} | Karar: {score.decision}")
        st.dataframe(_score_table(score), hide_index=True, width="stretch")


def render_company_list() -> None:
    st.title("Kayıtlı şirketler")

    rows = []
    for company in list_companies():
        score = calculate_alpha_score(company)
        rows.append(
            {
                "Hisse": company.symbol,
                "Şirket": company.company_name,
                "Alpha Score": score.total,
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
