"""Uygulamanın tanıdığı varlık kataloğu: BIST hisseleri, kıymetli madenler ve döviz kurları."""

from dataclasses import dataclass
from typing import Literal

GRAMS_PER_TROY_OUNCE = 31.1034768

Category = Literal["Hisse (BIST)", "Kıymetli Maden", "Döviz"]
Kind = Literal["simple", "gram_try"]


@dataclass(frozen=True)
class Instrument:
    code: str
    label: str
    category: Category
    kind: Kind
    ticker: str | None = None
    metal_ticker: str | None = None
    fx_ticker: str | None = None

    @property
    def display(self) -> str:
        return f"{self.label} ({self.category})"


def bist_instrument(kod: str) -> Instrument:
    kod_norm = kod.strip().upper()
    return Instrument(
        code=kod_norm,
        label=kod_norm,
        category="Hisse (BIST)",
        kind="simple",
        ticker=f"{kod_norm}.IS",
    )


DEFAULT_BIST_CODES: tuple[str, ...] = (
    "THYAO",
    "GARAN",
    "ASELS",
    "SISE",
    "KCHOL",
    "EREGL",
    "BIMAS",
    "TUPRS",
    "AKBNK",
    "SASA",
)

DEFAULT_BIST_INSTRUMENTS: tuple[Instrument, ...] = tuple(
    bist_instrument(kod) for kod in DEFAULT_BIST_CODES
)

PRECIOUS_METAL_INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument(
        code="XAUUSD",
        label="Altın (Ons/USD)",
        category="Kıymetli Maden",
        kind="simple",
        ticker="GC=F",
    ),
    Instrument(
        code="XAGUSD",
        label="Gümüş (Ons/USD)",
        category="Kıymetli Maden",
        kind="simple",
        ticker="SI=F",
    ),
    Instrument(
        code="GRAMALTIN",
        label="Gram Altın (TL)",
        category="Kıymetli Maden",
        kind="gram_try",
        metal_ticker="GC=F",
        fx_ticker="USDTRY=X",
    ),
    Instrument(
        code="GRAMGUMUS",
        label="Gram Gümüş (TL)",
        category="Kıymetli Maden",
        kind="gram_try",
        metal_ticker="SI=F",
        fx_ticker="USDTRY=X",
    ),
)

CURRENCY_INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument(code="USDTRY", label="USD/TRY", category="Döviz", kind="simple", ticker="USDTRY=X"),
    Instrument(code="EURTRY", label="EUR/TRY", category="Döviz", kind="simple", ticker="EURTRY=X"),
    Instrument(code="GBPTRY", label="GBP/TRY", category="Döviz", kind="simple", ticker="GBPTRY=X"),
    Instrument(code="EURUSD", label="EUR/USD", category="Döviz", kind="simple", ticker="EURUSD=X"),
)

DEFAULT_INSTRUMENTS: tuple[Instrument, ...] = (
    DEFAULT_BIST_INSTRUMENTS + PRECIOUS_METAL_INSTRUMENTS + CURRENCY_INSTRUMENTS
)

CATALOG_BY_CODE: dict[str, Instrument] = {inst.code: inst for inst in DEFAULT_INSTRUMENTS}


def resolve_instrument(code: str) -> Instrument:
    """Katalogdaki hazır kodu ya da serbest girilen bir BIST kodunu Instrument'a çevirir."""

    code_norm = code.strip().upper()
    if code_norm in CATALOG_BY_CODE:
        return CATALOG_BY_CODE[code_norm]
    return bist_instrument(code_norm)
