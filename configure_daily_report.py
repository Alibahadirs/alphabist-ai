from __future__ import annotations

import getpass
import json
import re

from app.core.settings import settings
from app.daily_scan.mailer import save_app_password


DEFAULT_EMAIL = "akkayatokat@gmail.com"


def main() -> None:
    print("AlphaBIST AI günlük e-posta ayarı")
    sender = input(f"Gönderen Gmail adresi [{DEFAULT_EMAIL}]: ").strip() or DEFAULT_EMAIL
    recipient = input(f"Raporun gideceği adres [{DEFAULT_EMAIL}]: ").strip() or DEFAULT_EMAIL
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", sender + ""):
        raise SystemExit("Geçerli bir gönderen e-posta adresi girin.")
    password = getpass.getpass("Google uygulama parolası (ekranda görünmez): ").strip()
    if len(password.replace(" ", "")) != 16:
        raise SystemExit("Google uygulama parolası 16 karakter olmalıdır.")
    save_app_password(sender, password)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    config = {"sender": sender, "recipient": recipient}
    (settings.data_dir / "daily_report_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Ayar tamamlandı. Parola Windows güvenli kimlik kasasında saklandı.")


if __name__ == "__main__":
    main()
