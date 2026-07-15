import pandas as pd
import streamlit as st
from pydantic import ValidationError

from app.core.constants import CATEGORY_MAX_POINTS
from app.database.repository import get_company, list_companies, upsert_company
from app.market_data.provider import get_history, get_quote
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics, ScoreBreakdown


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
        quote = get_quote(symbol)
        history = get_history(symbol)

        price_col, change_col, source_col = st.columns(3)
        price_col.metric("Son fiyat", f"{quote['last']:,.2f} TRY")
        change_col.metric(
            "Günlük değişim",
            f"{quote['change'] or 0:,.2f}",
            f"{quote['change_percent'] or 0:.2f}%",
        )
        source_col.metric("Veri kaynağı", "Yahoo Finance")
        st.caption("Piyasa verisi gecikmeli olabilir.")

        st.line_chart(history[["Close", "SMA_20", "SMA_50"]])
        latest = history.iloc[-1]
        indicator_col, macd_col, signal_col = st.columns(3)
        indicator_col.metric("RSI 14", f"{float(latest['RSI_14']):.2f}")
        macd_col.metric("MACD", f"{float(latest['MACD']):.4f}")
        signal_col.metric(
            "MACD sinyal",
            f"{float(latest['MACD_SIGNAL']):.4f}",
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
