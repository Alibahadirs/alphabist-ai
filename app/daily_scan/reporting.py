from __future__ import annotations

import csv
import html
import io
from datetime import datetime

from app.daily_scan.models import DailyScanResult, DailyTechnicalAssessment


def _number(value: float | None, digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def build_csv(result: DailyScanResult) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Hisse", "Tarih", "Kapanış", "Günlük %", "Destek", "Direnç",
        "Desteğe Uzaklık %", "Dirence Uzaklık %", "Stop Referansı",
        "Risk/Kazanç", "RSI", "EMA20", "EMA50", "Hacim Oranı",
        "Teknik Durum", "Puan", "Açıklama",
    ])
    for item in sorted(result.assessments, key=lambda x: (-x.score, x.symbol)):
        writer.writerow([
            item.symbol, item.price_date.isoformat(), _number(item.close),
            _number(item.daily_change_percent), _number(item.support),
            _number(item.resistance), _number(item.support_distance_percent),
            _number(item.resistance_distance_percent), _number(item.stop_level),
            _number(item.risk_reward_ratio), _number(item.rsi),
            _number(item.ema_20), _number(item.ema_50),
            _number(item.volume_ratio), item.status, item.score, item.explanation,
        ])
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def build_html(result: DailyScanResult, top_count: int = 50) -> str:
    ranked = sorted(result.assessments, key=lambda x: (-x.score, x.symbol))
    rows = "".join(_row(item) for item in ranked[:top_count])
    generated = result.generated_at.strftime("%d.%m.%Y %H:%M")
    market_date = result.market_date.strftime("%d.%m.%Y") if result.market_date else "-"
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><style>
body{{font-family:Arial,sans-serif;color:#172033;max-width:1100px;margin:auto;padding:20px}}
h1{{color:#163e72}} .summary{{background:#eef4fb;padding:14px;border-radius:8px}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin-top:18px}}
th,td{{border:1px solid #d7deea;padding:7px;text-align:right}}
th{{background:#163e72;color:white}} td:first-child,td:nth-child(8){{text-align:left}}
.note{{margin-top:18px;color:#596579;font-size:12px}}
</style></head><body>
<h1>AlphaBIST AI — Günlük Teknik Tarama</h1>
<div class="summary"><b>Piyasa verisi:</b> {market_date} &nbsp; | &nbsp;
<b>Başarılı:</b> {result.successful_symbols}/{result.requested_symbols} &nbsp; | &nbsp;
<b>Oluşturulma:</b> {generated}</div>
<p>En yüksek teknik puanlı ilk {min(top_count, len(ranked))} hisse aşağıdadır. Tüm sonuçlar ekli CSV dosyasındadır.</p>
<table><thead><tr><th>Hisse</th><th>Kapanış</th><th>Destek</th><th>Direnç</th>
<th>RSI</th><th>R/K</th><th>Puan</th><th>Teknik görünüm</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="note"><b>Önemli:</b> Bu rapor otomatik teknik göstergelere dayanır; yatırım tavsiyesi değildir.
Veriler gecikmeli veya eksik olabilir. İşlem kararı vermeden önce güncel fiyatı ve şirket haberlerini doğrulayın.</p>
</body></html>"""


def _row(item: DailyTechnicalAssessment) -> str:
    values = [
        html.escape(item.symbol), _number(item.close), _number(item.support),
        _number(item.resistance), _number(item.rsi), _number(item.risk_reward_ratio),
        str(item.score), html.escape(item.status),
    ]
    return "<tr>" + "".join(f"<td>{value}</td>" for value in values) + "</tr>"


def report_filename(prefix: str, generated_at: datetime) -> str:
    return f"alphabist_{prefix}_{generated_at:%Y%m%d_%H%M}.{'html' if prefix == 'rapor' else 'csv'}"
