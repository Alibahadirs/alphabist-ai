from pm.core.symbols import (
    CATALOG_BY_CODE,
    CURRENCY_INSTRUMENTS,
    DEFAULT_BIST_INSTRUMENTS,
    PRECIOUS_METAL_INSTRUMENTS,
    bist_instrument,
    resolve_instrument,
)


def test_bist_instrument_adds_is_suffix():
    inst = bist_instrument("thyao")
    assert inst.ticker == "THYAO.IS"
    assert inst.code == "THYAO"
    assert inst.category == "Hisse (BIST)"


def test_resolve_known_catalog_code_returns_catalog_entry():
    inst = resolve_instrument("usdtry")
    assert inst is CATALOG_BY_CODE["USDTRY"]
    assert inst.ticker == "USDTRY=X"


def test_resolve_unknown_code_falls_back_to_bist():
    inst = resolve_instrument("ZZZZ")
    assert inst.category == "Hisse (BIST)"
    assert inst.ticker == "ZZZZ.IS"


def test_gram_gold_is_composite():
    gram_altin = next(i for i in PRECIOUS_METAL_INSTRUMENTS if i.code == "GRAMALTIN")
    assert gram_altin.kind == "gram_try"
    assert gram_altin.metal_ticker == "GC=F"
    assert gram_altin.fx_ticker == "USDTRY=X"


def test_default_catalog_covers_all_categories():
    categories = {i.category for i in DEFAULT_BIST_INSTRUMENTS + PRECIOUS_METAL_INSTRUMENTS + CURRENCY_INSTRUMENTS}
    assert categories == {"Hisse (BIST)", "Kıymetli Maden", "Döviz"}
