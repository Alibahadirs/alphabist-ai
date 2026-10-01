"""Gmail üzerinden SMTP ile e-posta gönderimi (AlphaBIST AI'daki aynı desen).

Uygulama parolası düz metin olarak hiçbir yerde saklanmaz: Windows güvenli
kimlik kasasına (`keyring`) yazılır. Bulut (GitHub Actions vb.) ortamlarda
`PORTFOY_GMAIL_APP_PASSWORD` ortam değişkeni kasanın yerini alır.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

KEYRING_SERVICE = "Portfoy Yoneticisi Gunluk Uyari"


def save_app_password(sender: str, password: str) -> None:
    import keyring

    keyring.set_password(KEYRING_SERVICE, sender, password.replace(" ", ""))


def load_app_password(sender: str) -> str | None:
    cloud_password = os.getenv("PORTFOY_GMAIL_APP_PASSWORD")
    if cloud_password:
        return cloud_password.replace(" ", "")
    import keyring

    return keyring.get_password(KEYRING_SERVICE, sender)


def send_alert_email(
    *,
    sender: str,
    recipient: str,
    subject: str,
    html_body: str,
    csv_bytes: bytes = b"",
    csv_filename: str = "sinyal.csv",
) -> None:
    password = load_app_password(sender)
    if not password:
        raise RuntimeError("Gmail uygulama parolası güvenli kasada bulunamadı.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(
        "Portföy Yöneticisi günlük sinyal uyarısı ekte ve HTML görünümünde sunulmuştur."
    )
    message.add_alternative(html_body, subtype="html")
    if csv_bytes:
        message.add_attachment(csv_bytes, maintype="text", subtype="csv", filename=csv_filename)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)
