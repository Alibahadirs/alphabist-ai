import streamlit as st
from app.database.repository import init_db, seed_demo_data
from app.ui.pages import render_dashboard, render_company_form, render_company_list

st.set_page_config(page_title='AlphaBIST AI', page_icon='📊', layout='wide')
init_db()
seed_demo_data()
st.sidebar.title('AlphaBIST AI')
page = st.sidebar.radio('Menü', ['Dashboard', 'Şirket Ekle / Güncelle', 'Kayıtlı Şirketler'])
if page == 'Dashboard':
    render_dashboard()
elif page == 'Şirket Ekle / Güncelle':
    render_company_form()
else:
    render_company_list()
