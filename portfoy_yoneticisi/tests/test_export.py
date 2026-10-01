import io

import pandas as pd

from pm.export import dataframe_to_csv_bytes, dataframe_to_excel_bytes


def _sample_df():
    return pd.DataFrame(
        {
            "Enstrüman": ["THYAO", "GARAN"],
            "Fiyat": [298.5, 133.8],
        }
    )


def test_csv_bytes_contain_utf8_bom_and_data():
    data = dataframe_to_csv_bytes(_sample_df())
    assert data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    assert "THYAO" in text
    assert "298.5" in text


def test_excel_bytes_round_trip():
    df = _sample_df()
    data = dataframe_to_excel_bytes(df, sheet_name="Test")
    assert data[:2] == b"PK"  # xlsx bir zip arşividir
    roundtrip = pd.read_excel(io.BytesIO(data), sheet_name="Test")
    pd.testing.assert_frame_equal(roundtrip, df)
