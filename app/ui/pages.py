import pandas as pd
import streamlit as st
from app.database.repository import list_companies, get_company, upsert_company
from app.scoring.engine import calculate_alpha_score
from app.scoring.models import FinancialMetrics
from app.market_data.provider import get_quote, get_history

def render_dashboard():
    st.title('📊 AlphaBIST AI Dashboard')
    companies = list_companies()
    symbol = st.selectbox('Şirket seç', [c.symbol for c in companies])
    company = get_company(symbol)
    score = calculate_alpha_score(company)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric('Alpha Score', f'{score.total:.1f}/100')
    c2.metric('Not', score.grade)
    c3.metric('Karar', score.decision)
    c4.metric('Şirket', company.company_name)
    table = pd.DataFrame([
        ['Karlılık',score.profitability,15],['Büyüme',score.growth,15],['Borçluluk',score.leverage,15],
        ['Likidite',score.liquidity,10],['Nakit Akışı',score.cash_flow,15],['Verimlilik',score.efficiency,10],
        ['Değerleme',score.valuation,10],['Risk',score.risk,5],['Yönetim',score.management,5]
    ], columns=['Kategori','Puan','Maksimum'])
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.subheader('Piyasa Verisi')
    try:
        quote = get_quote(symbol)
        history = get_history(symbol)
        q1,q2,q3 = st.columns(3)
        q1.metric('Son Fiyat', f"{quote['last']:,.2f} TRY")
        q2.metric('Günlük Değişim', f"{quote['change'] or 0:,.2f}", f"{quote['change_percent'] or 0:.2f}%")
        q3.metric('Kaynak', 'Yahoo Finance')
        st.caption('Veri gecikmeli olabilir.')
        st.line_chart(history[['Close','SMA_20','SMA_50']])
        latest = history.iloc[-1]
        st.write({'RSI 14': round(float(latest['RSI_14']),2), 'MACD': round(float(latest['MACD']),4), 'MACD Sinyal': round(float(latest['MACD_SIGNAL']),4)})
    except Exception as exc:
        st.warning(f'Piyasa verisi alınamadı: {exc}')

def render_company_form():
    st.title('📝 Şirket Ekle / Güncelle')
    with st.form('company'):
        symbol = st.text_input('Hisse Kodu','ASELS').upper().strip()
        name = st.text_input('Şirket Adı','Aselsan Elektronik Sanayi ve Ticaret A.Ş.')
        left,right = st.columns(2)
        with left:
            rg=st.number_input('Ciro Büyümesi (%)',value=10.0); ng=st.number_input('Net Kâr Büyümesi (%)',value=10.0); nm=st.number_input('Net Kâr Marjı (%)',value=10.0); roe=st.number_input('ROE (%)',value=15.0); de=st.number_input('Borç / Özkaynak',value=.5,min_value=0.0); cr=st.number_input('Cari Oran',value=1.5,min_value=0.0)
        with right:
            ocf=st.number_input('Operasyonel Nakit Akışı',value=1000000.0); fcf=st.number_input('Serbest Nakit Akışı',value=500000.0); at=st.number_input('Aktif Devir Hızı',value=.7,min_value=0.0); val=st.slider('Değerleme Girdisi',0,100,70); man=st.slider('Yönetim Girdisi',0,100,75); risk=st.slider('Risk Dayanıklılığı',0,100,65)
        submitted = st.form_submit_button('Kaydet', type='primary')
    if submitted:
        metrics = FinancialMetrics(symbol=symbol, company_name=name, revenue_growth=rg, net_profit_growth=ng, net_margin=nm, roe=roe, debt_to_equity=de, current_ratio=cr, operating_cash_flow=ocf, free_cash_flow=fcf, asset_turnover=at, valuation_score_input=val, management_score_input=man, risk_score_input=risk)
        upsert_company(metrics)
        st.success(f'{symbol} kaydedildi. Alpha Score: {calculate_alpha_score(metrics).total:.1f}')

def render_company_list():
    st.title('📚 Kayıtlı Şirketler')
    rows=[]
    for company in list_companies():
        score=calculate_alpha_score(company)
        rows.append({'Hisse':company.symbol,'Şirket':company.company_name,'Alpha Score':score.total,'Not':score.grade,'Karar':score.decision})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
