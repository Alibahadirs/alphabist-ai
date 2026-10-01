"""Tabloları CSV/Excel baytlarına çeviren küçük yardımcılar (indirme düğmeleri için)."""

from __future__ import annotations

import io

import pandas as pd

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV_MIME = "text/csv"


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Excel'de Türkçe karakterlerin doğru görünmesi için UTF-8 BOM'lu CSV üretir."""

    return df.to_csv(index=False).encode("utf-8-sig")


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Sayfa1") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()
