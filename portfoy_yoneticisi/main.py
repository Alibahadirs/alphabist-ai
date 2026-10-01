import streamlit as st

from pm.core.settings import settings
from pm.portfolio.store import init_db
from pm.ui.pages import render_detail_page, render_portfolio_page, render_scan_page

st.set_page_config(
    page_title=settings.app_name,
    page_icon=":material/finance_mode:",
    layout="wide",
)

init_db()

st.sidebar.title(settings.app_name)
st.sidebar.caption(f"Sürüm {settings.app_version}")
st.sidebar.caption(
    "Hisse, kıymetli maden ve döviz için kişisel karar-destek aracı. "
    "Yatırım tavsiyesi değildir."
)

page = st.sidebar.radio("Menü", ["Öneri Tarama", "Detaylı Analiz", "Portföyüm"])

if page == "Öneri Tarama":
    render_scan_page()
elif page == "Detaylı Analiz":
    render_detail_page()
else:
    render_portfolio_page()
