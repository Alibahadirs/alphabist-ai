"""Streamlit sayfaları: Öneri Tarama, Detaylı Analiz, Portföyüm."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from ..analysis import indicators as ind
from ..analysis.backtest import run_signal_backtest
from ..analysis.performance import compute_range_performance
from ..analysis.recommendation import Recommendation, Signal, build_recommendation
from ..core.settings import settings
from ..core.symbols import DEFAULT_BIST_INSTRUMENTS, Instrument, resolve_instrument
from ..data.bist_universe import full_instrument_catalog
from ..data.market_data import (
    NOT_FOUND_MESSAGE,
    MarketDataError,
    fetch_instrument_history_with_warmup,
    fetch_instruments_history_with_warmup,
)
from ..export import CSV_MIME, EXCEL_MIME, dataframe_to_csv_bytes, dataframe_to_excel_bytes
from ..portfolio.analytics import (
    category_allocation,
    instrument_allocation,
    largest_position_share_pct,
)
from ..portfolio.models import Position
from ..portfolio.store import add_position, delete_position, list_positions

DISCLAIMER = (
    "Bu ekrandaki puanlar ve öneriler geçmiş fiyat verisinden türetilen mekanik "
    "göstergelere dayanır; yatırım tavsiyesi değildir."
)

_SIGNAL_COLORS = {
    Signal.AL.value: "#1b5e20",
    Signal.TUT.value: "#8a6d00",
    Signal.SAT.value: "#8e0000",
}


def _default_date_range() -> tuple[date, date]:
    end = date.today()
    start = end - timedelta(days=180)
    return start, end


def _date_range_input(key_prefix: str) -> tuple[date, date]:
    default_start, default_end = _default_date_range()
    col1, col2 = st.columns(2)
    start = col1.date_input("Başlangıç tarihi", value=default_start, key=f"{key_prefix}_start")
    end = col2.date_input("Bitiş tarihi", value=default_end, key=f"{key_prefix}_end")
    if start > end:
        st.error("Başlangıç tarihi bitiş tarihinden sonra olamaz.")
    return start, end


def _instrument_multiselect(key_prefix: str) -> list[Instrument]:
    catalog = full_instrument_catalog()
    labels = [inst.display for inst in catalog]
    by_label = {inst.display: inst for inst in catalog}
    default_labels = [inst.display for inst in DEFAULT_BIST_INSTRUMENTS[:6] if inst.display in by_label]
    st.caption(f"Seçim listesinde {len(catalog)} enstrüman bulunuyor.")
    selected_labels = st.multiselect(
        "Enstrümanlar", labels, default=default_labels, key=f"{key_prefix}_multiselect"
    )
    selected = [by_label[label] for label in selected_labels]

    extra_raw = st.text_input(
        "Ek BIST kodu ekle (virgülle ayırın, örn. THYAO, GARAN)",
        key=f"{key_prefix}_extra_codes",
    )
    if extra_raw.strip():
        for kod in extra_raw.split(","):
            kod = kod.strip()
            if kod:
                selected.append(resolve_instrument(kod))

    seen = set()
    unique_selected = []
    for inst in selected:
        if inst.code not in seen:
            seen.add(inst.code)
            unique_selected.append(inst)
    return unique_selected


def _signal_style(val: str) -> str:
    color = _SIGNAL_COLORS.get(val)
    if not color:
        return ""
    return f"background-color: {color}; color: white; font-weight: 600;"


def _download_buttons(df: pd.DataFrame, base_filename: str, key_prefix: str) -> None:
    col1, col2 = st.columns(2)
    col1.download_button(
        "CSV indir",
        data=dataframe_to_csv_bytes(df),
        file_name=f"{base_filename}.csv",
        mime=CSV_MIME,
        key=f"{key_prefix}_csv",
    )
    col2.download_button(
        "Excel indir",
        data=dataframe_to_excel_bytes(df),
        file_name=f"{base_filename}.xlsx",
        mime=EXCEL_MIME,
        key=f"{key_prefix}_xlsx",
    )


def render_scan_page() -> None:
    st.header("Öneri Tarama")
    st.caption(DISCLAIMER)

    instruments = _instrument_multiselect("scan")
    start, end = _date_range_input("scan")

    if st.button("Analiz Et", type="primary", key="scan_run"):
        if not instruments:
            st.warning("En az bir enstrüman seçin.")
        elif start > end:
            pass
        else:
            rows = []
            errors = []
            with st.spinner(f"{len(instruments)} enstrüman için tek seferde toplu veri çekiliyor..."):
                history_by_code = fetch_instruments_history_with_warmup(instruments, start, end)

            for inst in instruments:
                fetched = history_by_code.get(inst.code)
                if fetched is None:
                    errors.append(f"{inst.label}: {NOT_FOUND_MESSAGE}")
                    continue
                padded, visible = fetched
                try:
                    rec = build_recommendation(padded)
                    perf = compute_range_performance(visible)
                except ValueError as exc:
                    errors.append(f"{inst.label}: {exc}")
                    continue
                rows.append(
                    {
                        "Enstrüman": inst.label,
                        "Kategori": inst.category,
                        "Güncel Fiyat": rec.price,
                        "Aralık Getirisi %": perf.total_return_pct,
                        "Volatilite %": perf.annualized_volatility_pct,
                        "RSI": rec.rsi_value,
                        "Öneri": rec.signal.value,
                        "Skor": rec.score,
                        "Güven": rec.confidence,
                    }
                )
            # Sonuçlar session_state'e yazılır; indirme düğmelerine tıklamak da bir
            # Streamlit yeniden çalıştırması tetikler ve bu "if" bloğu o anda tekrar
            # girilmez (buton artık "tıklanmış" değildir) — sonuçlar kalıcı olmazsa kaybolur.
            st.session_state["scan_results"] = {"rows": rows, "errors": errors}

    results = st.session_state.get("scan_results")
    if results:
        if results["errors"]:
            st.warning(
                "Bazı enstrümanlar için veri alınamadı:\n"
                + "\n".join(f"- {e}" for e in results["errors"])
            )

        if results["rows"]:
            df = pd.DataFrame(results["rows"])
            styled = df.style.map(_signal_style, subset=["Öneri"]).format(
                {
                    "Güncel Fiyat": "{:.2f}",
                    "Aralık Getirisi %": "{:+.2f}",
                    "Volatilite %": "{:.1f}",
                    "RSI": "{:.1f}",
                    "Skor": "{:+.2f}",
                }
            )
            st.dataframe(styled, width="stretch", hide_index=True)
            _download_buttons(df, "oneri_tarama", "scan")
        else:
            st.info("Gösterilecek sonuç yok.")


def render_detail_page() -> None:
    st.header("Detaylı Analiz")
    st.caption(DISCLAIMER)

    catalog = full_instrument_catalog()
    all_labels = [inst.display for inst in catalog]
    by_label = {inst.display: inst for inst in catalog}
    choice = st.selectbox("Enstrüman", all_labels, key="detail_select")
    custom_code = st.text_input(
        "veya serbest BIST kodu girin (bu alan doluysa yukarıdaki seçim yok sayılır)",
        key="detail_custom_code",
    )

    instrument = resolve_instrument(custom_code) if custom_code.strip() else by_label[choice]
    start, end = _date_range_input("detail")
    holding_days = st.number_input(
        "Backtest tutma süresi (işlem günü)",
        min_value=1,
        max_value=120,
        value=settings.backtest_default_holding_days,
        key="detail_holding_days",
        help="Her sinyalden kaç işlem günü sonraki getirinin değerlendirileceği.",
    )

    if st.button("Analiz Et", type="primary", key="detail_run"):
        if start > end:
            st.session_state.pop("detail_result", None)
        else:
            try:
                padded, visible = fetch_instrument_history_with_warmup(instrument, start, end)
                rec = build_recommendation(padded)
                perf = compute_range_performance(visible)
            except (MarketDataError, ValueError) as exc:
                st.error(str(exc))
                st.session_state.pop("detail_result", None)
            else:
                # İndirme düğmeleri kendi rerun'unu tetiklediği için sonuçlar
                # session_state'te saklanır (bkz. Öneri Tarama'daki aynı desen).
                st.session_state["detail_result"] = {
                    "instrument": instrument,
                    "padded": padded,
                    "visible": visible,
                    "rec": rec,
                    "perf": perf,
                    "holding_days": int(holding_days),
                }

    result = st.session_state.get("detail_result")
    if result:
        instrument = result["instrument"]
        padded = result["padded"]
        visible = result["visible"]
        rec = result["rec"]
        perf = result["perf"]
        holding_days = result["holding_days"]

        signal_color = _SIGNAL_COLORS.get(rec.signal.value, "#444")
        st.markdown(
            f"### {instrument.display} — "
            f"<span style='background-color:{signal_color};color:white;padding:2px 10px;"
            f"border-radius:4px;'>{rec.signal.value}</span> "
            f"(skor {rec.score:+.2f}, güven: {rec.confidence})",
            unsafe_allow_html=True,
        )

        cols = st.columns(4)
        cols[0].metric("Güncel Fiyat", f"{rec.price:.2f}")
        cols[1].metric("Aralık Getirisi", f"%{perf.total_return_pct:+.2f}")
        cols[2].metric("Volatilite (yıllık)", f"%{perf.annualized_volatility_pct:.1f}")
        cols[3].metric("Maks. Düşüş", f"%{perf.max_drawdown_pct:.1f}")

        st.subheader("Fiyat ve hareketli ortalamalar")
        close = visible["Close"]
        chart_df = pd.DataFrame({"Kapanış": close})
        padded_close = padded["Close"]
        chart_df["SMA kısa"] = ind.sma(padded_close, 20).loc[visible.index]
        chart_df["SMA uzun"] = ind.sma(padded_close, 50).loc[visible.index]
        st.line_chart(chart_df)

        st.subheader("Bollinger Bantları")
        _bb_middle, bb_upper, bb_lower = ind.bollinger_bands(
            padded_close, settings.bollinger_window, settings.bollinger_std
        )
        bb_df = pd.DataFrame(
            {
                "Kapanış": close,
                "BB Üst": bb_upper.loc[visible.index],
                "BB Alt": bb_lower.loc[visible.index],
            }
        )
        st.line_chart(bb_df)
        if rec.bollinger_pctb is not None:
            st.caption(f"Güncel %B: {rec.bollinger_pctb:.2f} (0=alt bant, 1=üst bant).")

        st.subheader("RSI")
        rsi_series = ind.rsi(padded_close, 14).loc[visible.index]
        st.line_chart(pd.DataFrame({"RSI": rsi_series}))

        st.subheader("MACD (log fiyat farkı)")
        macd_line, macd_signal, macd_hist = ind.macd(
            np.log(padded_close), settings.macd_fast, settings.macd_slow, settings.macd_signal
        )
        macd_df = pd.DataFrame(
            {
                "MACD": macd_line.loc[visible.index],
                "Sinyal": macd_signal.loc[visible.index],
                "Histogram": macd_hist.loc[visible.index],
            }
        )
        st.line_chart(macd_df)

        st.subheader("Öneri faktör dökümü")
        st.table(pd.DataFrame(rec.factor_table))

        st.subheader("Sinyal doğruluğu (backtest)")
        st.caption(
            "Her gün için sinyal yalnızca o güne kadarki veriyle hesaplanır (ileriye bakmaz); "
            f"'isabet oranı', o sinyalden {holding_days} işlem günü sonra fiyatın beklenen yönde "
            "hareket ettiği günlerin oranıdır. Geçmiş performans gelecek için garanti değildir."
        )
        try:
            backtest = run_signal_backtest(padded, holding_days=int(holding_days))
        except ValueError as exc:
            st.info(str(exc))
        else:
            backtest_rows = [
                {
                    "Sinyal": stats.signal,
                    "Kaç kez üretildi": stats.count,
                    "İsabet oranı %": (
                        "-" if stats.hit_rate_pct is None else f"{stats.hit_rate_pct:.1f}"
                    ),
                    "Ort. ileri getiri %": (
                        "-" if stats.avg_forward_return_pct is None else f"{stats.avg_forward_return_pct:+.2f}"
                    ),
                }
                for stats in (backtest.al, backtest.sat, backtest.tut)
            ]
            backtest_df = pd.DataFrame(backtest_rows)
            st.dataframe(backtest_df, width="stretch", hide_index=True)
            st.caption(
                f"Değerlendirilen dönem: {backtest.start_date.date()} – {backtest.end_date.date()} "
                f"({backtest.evaluated_days} gün)."
            )
            _download_buttons(backtest_df, f"{instrument.code}_backtest", "detail_backtest")

        with st.expander("Aralık performans detayı"):
            st.write(
                {
                    "Başlangıç": str(perf.start_date.date()),
                    "Bitiş": str(perf.end_date.date()),
                    "Başlangıç fiyatı": round(perf.start_price, 2),
                    "Bitiş fiyatı": round(perf.end_price, 2),
                    "En iyi gün %": round(perf.best_day_pct, 2),
                    "En kötü gün %": round(perf.worst_day_pct, 2),
                    "İşlem günü sayısı": perf.trading_days,
                }
            )


def render_portfolio_page() -> None:
    st.header("Portföyüm")
    st.caption("Kişisel pozisyonlarınız bu bilgisayarda yerel olarak saklanır.")

    with st.expander("Yeni pozisyon ekle", expanded=False):
        catalog = full_instrument_catalog()
        all_labels = [inst.display for inst in catalog]
        by_label = {inst.display: inst for inst in catalog}
        choice = st.selectbox("Enstrüman", all_labels, key="pf_add_select")
        custom_code = st.text_input("veya serbest BIST kodu", key="pf_add_custom_code")
        quantity = st.number_input("Miktar / Lot", min_value=0.0, step=1.0, key="pf_add_qty")
        unit_cost = st.number_input("Birim maliyet", min_value=0.0, step=0.01, key="pf_add_cost")
        purchase_date = st.date_input("Alış tarihi", value=date.today(), key="pf_add_date")
        note = st.text_input("Not (opsiyonel)", key="pf_add_note")

        if st.button("Portföye ekle", key="pf_add_button"):
            instrument = resolve_instrument(custom_code) if custom_code.strip() else by_label[choice]
            if quantity <= 0:
                st.warning("Miktar 0'dan büyük olmalı.")
            else:
                add_position(
                    Position(
                        instrument_code=instrument.code,
                        label=instrument.label,
                        category=instrument.category,
                        quantity=quantity,
                        unit_cost=unit_cost,
                        purchase_date=purchase_date,
                        note=note,
                    )
                )
                st.success(f"{instrument.label} portföye eklendi.")
                st.rerun()

    positions = list_positions()
    if not positions:
        st.info("Henüz pozisyon eklenmedi.")
        return

    st.subheader("Mevcut pozisyonlar")
    rows = []
    errors = []
    today = date.today()
    lookback_start = today - timedelta(days=10)
    recommendations: dict[int, Recommendation] = {}

    position_instruments = [resolve_instrument(pos.instrument_code) for pos in positions]
    with st.spinner("Güncel fiyatlar toplu olarak çekiliyor..."):
        history_by_code = fetch_instruments_history_with_warmup(position_instruments, lookback_start, today)

    for pos, instrument in zip(positions, position_instruments):
        current_price = None
        rec = None
        fetched = history_by_code.get(instrument.code)
        if fetched is None:
            errors.append(f"{pos.label}: {NOT_FOUND_MESSAGE}")
        else:
            padded, _visible = fetched
            try:
                rec = build_recommendation(padded)
                current_price = rec.price
                recommendations[pos.id] = rec
            except ValueError as exc:
                errors.append(f"{pos.label}: {exc}")

        market_value = current_price * pos.quantity if current_price is not None else None
        pnl_pct = (
            ((current_price - pos.unit_cost) / pos.unit_cost * 100)
            if current_price is not None and pos.unit_cost > 0
            else None
        )
        rows.append(
            {
                "id": pos.id,
                "Enstrüman": pos.label,
                "Kategori": pos.category,
                "Miktar": pos.quantity,
                "Maliyet": pos.unit_cost,
                "Güncel Fiyat": current_price,
                "Güncel Değer": market_value,
                "Kâr/Zarar %": pnl_pct,
                "Öneri": rec.signal.value if rec else "-",
                "Alış Tarihi": pos.purchase_date.isoformat(),
                "Not": pos.note,
            }
        )

    if errors:
        st.warning("Bazı pozisyonlar için güncel fiyat alınamadı:\n" + "\n".join(f"- {e}" for e in errors))

    df = pd.DataFrame(rows).drop(columns=["id"])
    styled = df.style.map(_signal_style, subset=["Öneri"]).format(
        {
            "Miktar": "{:.2f}",
            "Maliyet": "{:.2f}",
            "Güncel Fiyat": lambda v: "-" if pd.isna(v) else f"{v:.2f}",
            "Güncel Değer": lambda v: "-" if pd.isna(v) else f"{v:,.2f}",
            "Kâr/Zarar %": lambda v: "-" if pd.isna(v) else f"{v:+.2f}",
        }
    )
    st.dataframe(styled, width="stretch", hide_index=True)
    _download_buttons(df, "portfoyum", "portfolio")

    valued_rows = [r for r in rows if r["Güncel Değer"] is not None]
    if valued_rows:
        total_value = sum(r["Güncel Değer"] for r in valued_rows)
        total_cost = sum(r["Miktar"] * r["Maliyet"] for r in valued_rows)
        total_pnl_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0.0
        cols = st.columns(3)
        cols[0].metric("Toplam Değer", f"{total_value:,.2f}")
        cols[1].metric("Toplam Maliyet", f"{total_cost:,.2f}")
        cols[2].metric("Toplam Kâr/Zarar", f"%{total_pnl_pct:+.2f}")

        st.subheader("Portföy Dağılımı")
        dist_col1, dist_col2 = st.columns(2)
        with dist_col1:
            st.caption("Varlık sınıfına göre dağılım")
            st.bar_chart(category_allocation(valued_rows).set_index("Kategori"))
        with dist_col2:
            st.caption("Enstrümana göre dağılım")
            st.bar_chart(instrument_allocation(valued_rows).set_index("Enstrüman"))

        largest_share = largest_position_share_pct(valued_rows)
        if largest_share is not None:
            st.caption(
                f"En büyük tekil enstrüman payı: %{largest_share:.1f} "
                "(yüksek yoğunlaşma, tek bir enstrümana bağımlılığı artırır)."
            )

    st.subheader("Pozisyon sil")
    del_choices = {f"#{r['id']} — {r['Enstrüman']} ({r['Alış Tarihi']})": r["id"] for r in rows}
    to_delete_label = st.selectbox("Silinecek pozisyon", ["-"] + list(del_choices.keys()), key="pf_delete_select")
    if to_delete_label != "-" and st.button("Sil", key="pf_delete_button"):
        delete_position(del_choices[to_delete_label])
        st.success("Pozisyon silindi.")
        st.rerun()
