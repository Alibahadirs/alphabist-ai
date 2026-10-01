"""Günlük sinyal uyarısı için e-posta/izleme listesi ayarlarının saklanması.

Kimlik bilgisi (Gmail uygulama parolası) burada DEĞİL, Windows güvenli kimlik
kasasında (`mailer.save_app_password`) tutulur. Bu dosyada yalnızca gönderen/
alıcı adresi ve ek izleme kodları saklanır.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from ..core.settings import DATA_DIR

CONFIG_PATH = DATA_DIR / "daily_alert_config.json"


@dataclass(frozen=True)
class AlertConfig:
    sender: str
    recipient: str
    extra_codes: tuple[str, ...] = field(default_factory=tuple)


def save_config(config: AlertConfig, config_path: Path = CONFIG_PATH) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sender": config.sender,
        "recipient": config.recipient,
        "extra_codes": list(config.extra_codes),
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config(config_path: Path = CONFIG_PATH) -> AlertConfig:
    """Önce bulut ortam değişkenlerine, yoksa yerel JSON dosyasına bakar."""

    cloud_sender = os.getenv("PORTFOY_GMAIL_SENDER")
    cloud_recipient = os.getenv("PORTFOY_REPORT_RECIPIENT")
    if cloud_sender and cloud_recipient:
        cloud_codes_raw = os.getenv("PORTFOY_WATCH_CODES", "")
        extra = tuple(c.strip().upper() for c in cloud_codes_raw.split(",") if c.strip())
        return AlertConfig(sender=cloud_sender, recipient=cloud_recipient, extra_codes=extra)

    if not config_path.exists():
        raise RuntimeError("E-posta ayarı bulunamadı. Önce configure_daily_alert.py çalıştırın.")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    return AlertConfig(
        sender=data["sender"],
        recipient=data["recipient"],
        extra_codes=tuple(data.get("extra_codes", [])),
    )
