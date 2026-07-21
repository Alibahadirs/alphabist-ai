import streamlit as st

from app.core.settings import settings
from app.database.repository import init_db, seed_demo_data
from app.ui.pages import (
    render_comparison,
    render_company_form,
    render_company_list,
    render_dashboard,
    render_data_quality,
    render_data_backup,
    render_pdf_analysis,
    render_market_data_check,
    render_portfolio,
    render_report_trends,
    render_scanner,
    render_watchlist,
)


st.set_page_config(
    page_title=settings.app_name,
    page_icon=":material/query_stats:",
    layout="wide",
)

init_db()
seed_demo_data()

st.sidebar.title(settings.app_name)
st.sidebar.caption(f"Sürüm {settings.app_version}")

page = st.sidebar.radio(
    "Menü",
    [
        "Genel bakış",
        "Veri kalite merkezi",
        "Rapor trendleri",
        "Hisse tarayıcı",
        "Piyasa veri kontrolü",
        "Şirket karşılaştırma",
        "Takip listesi",
        "Portföy",
        "Veri yedekleme",
        "PDF analizi",
        "Şirket ekle veya güncelle",
        "Kayıtlı şirketler",
    ],
)

if page == "Genel bakış":
    render_dashboard()
elif page == "Veri kalite merkezi":
    render_data_quality()
elif page == "Rapor trendleri":
    render_report_trends()
elif page == "Hisse tarayıcı":
    render_scanner()
elif page == "Piyasa veri kontrolü":
    render_market_data_check()
elif page == "Şirket karşılaştırma":
    render_comparison()
elif page == "Takip listesi":
    render_watchlist()
elif page == "Portföy":
    render_portfolio()
elif page == "Veri yedekleme":
    render_data_backup()
elif page == "PDF analizi":
    render_pdf_analysis()
elif page == "Şirket ekle veya güncelle":
    render_company_form()
else:
    render_company_list()
