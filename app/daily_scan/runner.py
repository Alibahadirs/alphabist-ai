from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.core.settings import settings
from app.daily_scan.mailer import send_report
from app.daily_scan.reporting import build_csv, build_html, report_filename
from app.daily_scan.service import run_scan


CONFIG_PATH = settings.data_dir / "daily_report_config.json"


def _config() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        raise RuntimeError("E-posta ayarı bulunamadı. Önce configure_daily_report.py çalıştırın.")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="AlphaBIST günlük teknik tarama")
    parser.add_argument("--dry-run", action="store_true", help="E-posta göndermeden rapor üret")
    parser.add_argument("--force", action="store_true", help="Hafta sonu/tatil kontrolünü geç")
    parser.add_argument("--limit", type=int, help="İlk N sembolü tara")
    parser.add_argument("--symbols", help="Virgülle ayrılmış semboller")
    args = parser.parse_args()

    today = date.today()
    if today.weekday() >= 5 and not args.force:
        print("Hafta sonu olduğu için tarama yapılmadı.")
        return 0

    symbols = [x.strip().upper() for x in args.symbols.split(",")] if args.symbols else None
    result = run_scan(symbols=symbols, limit=args.limit)
    if not result.assessments:
        raise RuntimeError("Rapor oluşturulamadı; hiçbir hisse için geçerli veri alınamadı.")

    html_body = build_html(result)
    csv_bytes = build_csv(result)
    report_dir = settings.data_dir / "daily_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_name = report_filename("rapor", result.generated_at)
    csv_name = report_filename("veriler", result.generated_at)
    (report_dir / html_name).write_text(html_body, encoding="utf-8")
    (report_dir / csv_name).write_bytes(csv_bytes)

    if not args.dry_run:
        config = _config()
        send_report(
            sender=config["sender"], recipient=config["recipient"],
            subject=f"AlphaBIST günlük teknik rapor — {result.market_date:%d.%m.%Y}",
            html_body=html_body, csv_bytes=csv_bytes, csv_filename=csv_name,
        )
    print(f"Rapor hazır: {result.successful_symbols}/{result.requested_symbols} hisse, {html_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
