"""İlk kurulum: günlük sinyal uyarısı için Gmail bilgilerini ve izleme listesini ayarlar.

Çalıştırma (proje kökünden):
    ..\\.venv\\Scripts\\python.exe configure_daily_alert.py

Uygulama parolası düz metin olarak hiçbir dosyaya yazılmaz; Windows güvenli
kimlik kasasına kaydedilir. Yalnızca gönderen/alıcı adresi ve izleme listesi
``data/daily_alert_config.json`` dosyasında (Git tarafından izlenmez) tutulur.
"""

from __future__ import annotations

import getpass
import re

from pm.alerts.config import AlertConfig, save_config
from pm.alerts.mailer import save_app_password

DEFAULT_EMAIL = "akkayatokat@gmail.com"


def main() -> None:
    print("Portföy Yöneticisi günlük e-posta uyarısı ayarı")
    sender = input(f"Gönderen Gmail adresi [{DEFAULT_EMAIL}]: ").strip() or DEFAULT_EMAIL
    recipient = input(f"Raporun gideceği adres [{DEFAULT_EMAIL}]: ").strip() or DEFAULT_EMAIL
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", sender):
        raise SystemExit("Geçerli bir gönderen e-posta adresi girin.")

    password = getpass.getpass("Google uygulama parolası (ekranda görünmez): ").strip()
    if len(password.replace(" ", "")) != 16:
        raise SystemExit("Google uygulama parolası 16 karakter olmalıdır.")

    extra_raw = input(
        "İzleme listesine eklenecek ek kodlar — portföyünüzdeki pozisyonlar zaten "
        "otomatik dahildir (virgülle ayırın, boş bırakılabilir, örn. THYAO, USDTRY, GRAMALTIN): "
    ).strip()
    extra_codes = tuple(c.strip().upper() for c in extra_raw.split(",") if c.strip())

    save_app_password(sender, password)
    save_config(AlertConfig(sender=sender, recipient=recipient, extra_codes=extra_codes))
    print("Ayar tamamlandı. Parola Windows güvenli kimlik kasasında saklandı.")
    print(
        "Test etmek için: "
        "..\\.venv\\Scripts\\python.exe -m pm.alerts.runner --dry-run --force"
    )


if __name__ == "__main__":
    main()
