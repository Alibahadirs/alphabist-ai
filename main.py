import streamlit as st

from app.core.settings import settings
from app.database.repository import init_db, seed_demo_data
from app.ui.pages import render_company_form, render_company_list, render_dashboard


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
    ["Genel bakış", "Şirket ekle veya güncelle", "Kayıtlı şirketler"],
)

if page == "Genel bakış":
    render_dashboard()
elif page == "Şirket ekle veya güncelle":
    render_company_form()
else:
    render_company_list()
