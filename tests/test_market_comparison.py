from app.market_data.comparison import compare_quotes


def _quote(price, change, quote_date):
    return {
        "last": price,
        "change_percent": change,
        "as_of_date": quote_date,
    }


def test_matching_quotes_are_valid():
    result = compare_quotes(
        _quote(317.50, -3.2012, "2026-07-21"),
        _quote(317.50, -3.2012, "2026-07-21"),
    )

    assert result.valid is True
    assert result.status == "Sağlayıcı verileri uyumlu"
    assert result.price_difference_percent == 0
    assert result.change_difference_points == 0
    assert result.date_gap_days == 0


def test_quote_comparison_explains_each_mismatch():
    result = compare_quotes(
        _quote(320, -1.0, "2026-07-21"),
        _quote(300, -4.0, "2026-07-18"),
    )

    assert result.valid is False
    assert "tarihler 3 gün farklı" in result.status
    assert "fiyatlar %6.25 farklı" in result.status
    assert "günlük değişimler 3.00 puan farklı" in result.status


def test_quote_comparison_rejects_missing_values():
    result = compare_quotes(
        _quote(None, -1.0, "2026-07-21"),
        _quote(300, -1.0, "2026-07-21"),
    )

    assert result.valid is False
    assert "fiyat veya tarih eksik" in result.status
