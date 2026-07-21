from __future__ import annotations

import csv
import io

from app.market_data.health import MarketHealthSummary
from app.market_data.models import (
    MarketDiagnosticSnapshot,
    market_snapshot_fingerprint,
)


def build_market_diagnostic_csv(
    snapshots: list[MarketDiagnosticSnapshot],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "Hisse",
            "Kontrol zamanı",
            "Birincil fiyat",
            "Yedek fiyat",
            "Birincil tarih",
            "Yedek tarih",
            "Fiyat farkı (%)",
            "Değişim farkı (puan)",
            "Tarih farkı (gün)",
            "Çapraz doğrulandı",
            "Durum",
            "Bütünlük",
            "Parmak izi",
        ]
    )
    for item in snapshots:
        writer.writerow(
            [
                item.symbol,
                item.created_at or "",
                item.primary_price,
                item.secondary_price,
                item.primary_date.isoformat() if item.primary_date else "",
                item.secondary_date.isoformat() if item.secondary_date else "",
                item.price_difference_percent,
                item.change_difference_points,
                item.date_gap_days,
                "Evet" if item.cross_verified else "Hayır",
                item.status,
                (
                    "Doğrulandı"
                    if item.fingerprint == market_snapshot_fingerprint(item)
                    else "Geçersiz"
                ),
                item.fingerprint,
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def build_market_health_csv(summary: MarketHealthSummary) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "Hisse",
            "Sağlık durumu",
            "Öncelik",
            "Son fiyat tarihi",
            "Veri yaşı (gün)",
            "Çapraz doğrulandı",
            "Bütünlük",
            "Açıklama",
        ]
    )
    for item in summary.items:
        writer.writerow(
            [
                item.symbol,
                item.status,
                item.priority,
                item.latest_date.isoformat() if item.latest_date else "",
                item.age_days,
                "Evet" if item.cross_verified else "Hayır",
                "Doğrulandı" if item.integrity_valid else "Geçersiz",
                item.detail,
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")
