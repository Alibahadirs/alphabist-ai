from __future__ import annotations

import smtplib
from email.message import EmailMessage


KEYRING_SERVICE = "AlphaBIST AI Daily Report"


def save_app_password(sender: str, password: str) -> None:
    import keyring

    keyring.set_password(KEYRING_SERVICE, sender, password.replace(" ", ""))


def load_app_password(sender: str) -> str | None:
    import keyring

    return keyring.get_password(KEYRING_SERVICE, sender)


def send_report(
    *, sender: str, recipient: str, subject: str, html_body: str,
    csv_bytes: bytes, csv_filename: str,
) -> None:
    password = load_app_password(sender)
    if not password:
        raise RuntimeError("Gmail uygulama parolası güvenli kasada bulunamadı.")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content("AlphaBIST AI günlük teknik raporu ekte ve HTML görünümünde sunulmuştur.")
    message.add_alternative(html_body, subtype="html")
    message.add_attachment(csv_bytes, maintype="text", subtype="csv", filename=csv_filename)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)
