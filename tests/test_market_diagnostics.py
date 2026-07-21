from datetime import date

from app.market_data.diagnostics import diagnose_market_data


def _quote(source="Yahoo Finance", price=100, quote_date="2026-07-21"):
    return {
        "last": price,
        "previous": 98,
        "change": 2,
        "change_percent": 2.040816,
        "as_of_date": quote_date,
        "source": source,
        "data_mode": "delayed",
        "official": False,
    }


def test_diagnostic_cross_verifies_matching_providers():
    diagnostic = diagnose_market_data(
        "thyao",
        reference_date=date(2026, 7, 21),
        yahoo_loader=lambda symbol: _quote(),
        borsa_loader=lambda symbol: _quote("borsa-api / Yahoo Finance"),
    )

    assert diagnostic.symbol == "THYAO"
    assert diagnostic.primary.eligible is True
    assert diagnostic.secondary.eligible is True
    assert diagnostic.cross_verified is True
    assert "çapraz doğrulandı" in diagnostic.status


def test_diagnostic_preserves_primary_when_secondary_fails():
    def fail(symbol):
        raise RuntimeError("CLI bulunamadı")

    diagnostic = diagnose_market_data(
        "THYAO",
        reference_date=date(2026, 7, 21),
        yahoo_loader=lambda symbol: _quote(),
        borsa_loader=fail,
    )

    assert diagnostic.primary.available is True
    assert diagnostic.secondary.available is False
    assert diagnostic.secondary.error == "CLI bulunamadı"
    assert diagnostic.cross_verified is False
    assert diagnostic.status == "Yalnız bir sağlayıcıdan veri alınabildi"


def test_diagnostic_rejects_stale_or_mismatching_data():
    diagnostic = diagnose_market_data(
        "THYAO",
        reference_date=date(2026, 7, 21),
        yahoo_loader=lambda symbol: _quote(price=100),
        borsa_loader=lambda symbol: _quote(
            "borsa-api / Yahoo Finance",
            price=90,
            quote_date="2026-07-10",
        ),
    )

    assert diagnostic.secondary.eligible is False
    assert diagnostic.cross_verified is False
    assert "uyumsuzluğu" in diagnostic.status


def test_diagnostic_handles_both_failures():
    def fail(symbol):
        raise RuntimeError("kapalı")

    diagnostic = diagnose_market_data(
        "THYAO",
        yahoo_loader=fail,
        borsa_loader=fail,
    )

    assert diagnostic.primary.available is False
    assert diagnostic.secondary.available is False
    assert diagnostic.status == "Hiçbir sağlayıcıdan veri alınamadı"
