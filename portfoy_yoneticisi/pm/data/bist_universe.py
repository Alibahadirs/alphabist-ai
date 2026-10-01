"""KAP'tan tüm bilinen BIST hisse kodlarını çekip önbellekleyen yardımcı modül.

Ağ erişimi olmadığında veya KAP sayfası beklenenden az sembol döndürdüğünde,
uygulamanın çalışmaya devam etmesi için küçük bir varsayılan listeye düşülür.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

import requests
import streamlit as st

from ..core.symbols import (
    CURRENCY_INSTRUMENTS,
    DEFAULT_BIST_CODES,
    PRECIOUS_METAL_INSTRUMENTS,
    Instrument,
    bist_instrument,
)

KAP_BIST_COMPANIES_URL = "https://kap.org.tr/tr/bist-sirketler"
_SYMBOL = re.compile(r"^[A-Z0-9]{3,6}$")
_MIN_EXPECTED_SYMBOLS = 100
_CACHE_TTL_SECONDS = 24 * 3600


class _KapCompanyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._parts: list[str] = []
        self.symbols: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        href = attributes.get("href") or ""
        self._capture = tag == "a" and "/tr/sirket-bilgileri/ozet/" in href
        if self._capture:
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture:
            tokens = " ".join(self._parts).upper().split()
            if 1 <= len(tokens) <= 3 and all(_SYMBOL.fullmatch(token) for token in tokens):
                self.symbols.update(tokens)
            self._capture = False

    def handle_data(self, data: str) -> None:
        if not self._capture:
            return
        self._parts.append(data)


@st.cache_data(ttl=_CACHE_TTL_SECONDS, show_spinner=False)
def _fetch_bist_symbols(timeout_seconds: int = 30) -> tuple[str, ...]:
    response = requests.get(KAP_BIST_COMPANIES_URL, timeout=timeout_seconds)
    response.raise_for_status()

    symbols = set(re.findall(r'\\?"stockCode\\?"\s*:\s*\\?"([A-Z0-9 ]{3,20})\\?"', response.text))
    parsed_symbols = {token for value in symbols for token in value.split() if _SYMBOL.fullmatch(token)}

    if len(parsed_symbols) < _MIN_EXPECTED_SYMBOLS:
        parser = _KapCompanyParser()
        parser.feed(response.text)
        parsed_symbols.update(parser.symbols)

    if len(parsed_symbols) < _MIN_EXPECTED_SYMBOLS:
        raise RuntimeError("KAP BIST şirket listesi beklenenden az sembol içeriyor.")

    return tuple(sorted(parsed_symbols))


def all_bist_codes() -> tuple[str, ...]:
    """Tüm bilinen BIST hisse kodlarını döndürür.

    KAP'a erişilemezse veya liste bozuksa, uygulamanın varsayılan küçük
    listesine (DEFAULT_BIST_CODES) düşülür. KAP taraması bazı likit hisseleri
    kaçırabildiği için (ör. sayfa yapısı değişikliği), küratörlü varsayılan
    kodlar her zaman birleştirilerek garanti altına alınır.
    """

    try:
        fetched = _fetch_bist_symbols()
    except Exception:
        return DEFAULT_BIST_CODES
    return tuple(sorted(set(fetched) | set(DEFAULT_BIST_CODES)))


def all_bist_instruments() -> tuple[Instrument, ...]:
    return tuple(bist_instrument(code) for code in all_bist_codes())


def full_instrument_catalog() -> tuple[Instrument, ...]:
    """Tüm BIST hisseleri + kıymetli madenler + döviz kurlarından oluşan tam katalog."""

    return all_bist_instruments() + PRECIOUS_METAL_INSTRUMENTS + CURRENCY_INSTRUMENTS
