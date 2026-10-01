from pm.core.symbols import DEFAULT_BIST_CODES
from pm.data import bist_universe


def test_all_bist_codes_falls_back_when_fetch_fails(monkeypatch):
    def _boom(timeout_seconds=30):
        raise RuntimeError("ağ hatası")

    monkeypatch.setattr(bist_universe, "_fetch_bist_symbols", _boom)
    assert bist_universe.all_bist_codes() == DEFAULT_BIST_CODES


def test_all_bist_instruments_wraps_codes(monkeypatch):
    monkeypatch.setattr(bist_universe, "all_bist_codes", lambda: ("THYAO", "GARAN"))
    instruments = bist_universe.all_bist_instruments()
    assert [i.code for i in instruments] == ["THYAO", "GARAN"]
    assert all(i.ticker and i.ticker.endswith(".IS") for i in instruments)


def test_full_instrument_catalog_includes_metals_and_currencies(monkeypatch):
    monkeypatch.setattr(bist_universe, "all_bist_instruments", lambda: ())
    catalog = bist_universe.full_instrument_catalog()
    categories = {inst.category for inst in catalog}
    assert categories == {"Kıymetli Maden", "Döviz"}
