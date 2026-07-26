from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import requests


KAP_BIST_COMPANIES_URL = "https://kap.org.tr/tr/bist-sirketler"
_SYMBOL = re.compile(r"^[A-Z0-9]{3,6}$")


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


def fetch_bist_symbols(timeout_seconds: int = 30) -> list[str]:
    response = requests.get(KAP_BIST_COMPANIES_URL, timeout=timeout_seconds)
    response.raise_for_status()
    symbols = set(re.findall(r'\\?"stockCode\\?"\s*:\s*\\?"([A-Z0-9 ]{3,20})\\?"', response.text))
    parsed_symbols = {token for value in symbols for token in value.split() if _SYMBOL.fullmatch(token)}
    if len(parsed_symbols) < 100:
        parser = _KapCompanyParser()
        parser.feed(response.text)
        parsed_symbols.update(parser.symbols)
    if len(parsed_symbols) < 100:
        raise RuntimeError("KAP BIST şirket listesi beklenenden az sembol içeriyor.")
    return sorted(parsed_symbols)


def _global_borsa_api_path() -> str:
    npm = shutil.which("npm")
    node = shutil.which("node")
    if npm is None or node is None:
        raise RuntimeError("Node.js ve borsa-api kurulumu gerekiyor.")
    result = subprocess.run(
        [npm, "root", "-g"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
        shell=False,
    )
    module_path = Path(result.stdout.strip()) / "borsa-api"
    if result.returncode != 0 or not module_path.exists():
        raise RuntimeError("Global borsa-api paketi bulunamadı.")
    return str(module_path)


def load_histories(
    symbols: list[str],
    *,
    period: str = "1y",
    timeout_seconds: int = 1800,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    if not symbols:
        return {}, {}
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js bulunamadı.")
    bridge = Path(__file__).with_name("borsa_history_bridge.cjs")
    result = subprocess.run(
        [node, str(bridge), _global_borsa_api_path(), ",".join(symbols), period],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
        shell=False,
    )
    histories: dict[str, pd.DataFrame] = {}
    failures: dict[str, str] = {}
    for line in result.stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        symbol = str(payload.get("symbol") or "").upper()
        if not payload.get("ok"):
            failures[symbol] = str(payload.get("error") or "Bilinmeyen veri hatası")
            continue
        quotes = payload.get("quotes") or []
        frame = pd.DataFrame(quotes)
        if frame.empty:
            failures[symbol] = "Tarihsel veri boş."
            continue
        frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.tz_convert(None)
        frame = frame.set_index("date").rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
        histories[symbol] = frame[["Open", "High", "Low", "Close", "Volume"]]
    if result.returncode != 0 and not histories:
        raise RuntimeError(result.stderr.strip() or "Tarihsel veri köprüsü çalışmadı.")
    for symbol in symbols:
        if symbol not in histories and symbol not in failures:
            failures[symbol] = "Veri sağlayıcısından yanıt alınamadı."
    return histories, failures
