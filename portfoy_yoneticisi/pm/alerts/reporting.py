"""Günlük tarama sonucundan HTML e-posta gövdesi ve CSV eki üretimi."""

from __future__ import annotations

import html as html_lib

import pandas as pd

from ..export import dataframe_to_csv_bytes
from .service import DailyScanResult

_SIGNAL_COLOR = {"Al": "#1b5e20", "Sat": "#8e0000"}


def build_rows(result: DailyScanResult) -> list[dict]:
    rows = []
    for row in result.actionable:
        rec = row.recommendation
        rows.append(
            {
                "Enstrüman": row.instrument.label,
                "Kategori": row.instrument.category,
                "Fiyat": round(rec.price, 2),
                "Sinyal": rec.signal.value,
                "Skor": round(rec.score, 2),
                "Güven": rec.confidence,
            }
        )
    return rows


def build_dataframe(result: DailyScanResult) -> pd.DataFrame:
    return pd.DataFrame(build_rows(result))


def build_csv(result: DailyScanResult) -> bytes:
    if not result.actionable:
        return b""
    return dataframe_to_csv_bytes(build_dataframe(result))


def build_html(result: DailyScanResult) -> str:
    date_str = result.generated_at.strftime("%d.%m.%Y %H:%M")

    if not result.actionable:
        body = "<p>Bugün Al/Sat eşiğini aşan bir sinyal bulunmadı.</p>"
    else:
        rows_html = ""
        for row in result.actionable:
            rec = row.recommendation
            color = _SIGNAL_COLOR.get(rec.signal.value, "#444")
            rows_html += (
                "<tr>"
                f"<td>{html_lib.escape(row.instrument.label)}</td>"
                f"<td>{html_lib.escape(row.instrument.category)}</td>"
                f"<td>{rec.price:.2f}</td>"
                f"<td style='background:{color};color:white;font-weight:600;'>"
                f"{rec.signal.value}</td>"
                f"<td>{rec.score:+.2f}</td>"
                f"<td>{html_lib.escape(rec.confidence)}</td>"
                "</tr>"
            )
        body = (
            "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
            "<tr><th>Enstrüman</th><th>Kategori</th><th>Fiyat</th><th>Sinyal</th>"
            "<th>Skor</th><th>Güven</th></tr>"
            f"{rows_html}"
            "</table>"
        )

    errors_html = ""
    if result.errors:
        items = "".join(f"<li>{html_lib.escape(e)}</li>" for e in result.errors)
        errors_html = f"<p>Veri alınamayanlar:</p><ul>{items}</ul>"

    return (
        f"<h2>Portföy Yöneticisi — Günlük Sinyal Uyarısı ({date_str})</h2>"
        f"<p>{result.evaluated}/{result.requested} enstrüman değerlendirildi.</p>"
        f"{body}"
        f"{errors_html}"
        "<p style='color:#888;font-size:12px;'>Bu e-posta mekanik gösterge tabanlı bir "
        "karar-destek aracından üretilmiştir; yatırım tavsiyesi değildir.</p>"
    )
