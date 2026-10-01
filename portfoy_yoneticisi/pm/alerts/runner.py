"""Zamanlanmış görev tarafından çağrılan giriş noktası: `python -m pm.alerts.runner`.

Kurulum: önce proje kökünde (portfoy_yoneticisi/) `configure_daily_alert.py`
çalıştırılıp e-posta/parola ayarlanmalı, ardından `install_daily_alert_task.ps1`
ile Windows Görev Zamanlayıcı'na günlük görev eklenmelidir.
"""

from __future__ import annotations

import argparse
from datetime import date

from .config import load_config
from .mailer import send_alert_email
from .reporting import build_csv, build_html
from .service import run_daily_scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portföy Yöneticisi günlük sinyal uyarısı")
    parser.add_argument(
        "--dry-run", action="store_true", help="E-posta göndermeden raporu ekrana yazdır"
    )
    parser.add_argument("--force", action="store_true", help="Hafta sonu kontrolünü geç")
    args = parser.parse_args(argv)

    today = date.today()
    if today.weekday() >= 5 and not args.force:
        print("Hafta sonu olduğu için tarama yapılmadı (BIST kapalı). --force ile zorlayabilirsiniz.")
        return 0

    config = load_config()
    result = run_daily_scan(extra_codes=config.extra_codes)

    html_body = build_html(result)
    print(
        f"{len(result.actionable)} aksiyon alınabilir sinyal bulundu "
        f"({result.evaluated}/{result.requested} enstrüman değerlendirildi)."
    )
    if result.errors:
        print(f"{len(result.errors)} enstrüman için veri alınamadı.")

    if args.dry_run:
        print(html_body)
        return 0

    csv_bytes = build_csv(result)
    send_alert_email(
        sender=config.sender,
        recipient=config.recipient,
        subject=f"Portföy Yöneticisi günlük sinyal uyarısı — {today:%d.%m.%Y}",
        html_body=html_body,
        csv_bytes=csv_bytes,
        csv_filename=f"sinyal_{today:%Y%m%d}.csv",
    )
    print("E-posta gönderildi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
