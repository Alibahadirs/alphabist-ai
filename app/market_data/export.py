from __future__ import annotations

import csv
import io

from app.market_data.health import MarketHealthSummary
from app.market_data.batch_history import (
    MarketBatchRun,
    MarketBatchRunAudit,
    market_batch_run_fingerprint,
)
from app.market_data.models import (
    MarketDiagnosticSnapshot,
    market_snapshot_fingerprint,
)
from app.market_data.remediation import MarketHealthTask


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


def build_market_health_queue_csv(
    tasks: tuple[MarketHealthTask, ...],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "Görev ID",
            "Hisse",
            "Sağlık durumu",
            "Öncelik",
            "Önem",
            "Son fiyat tarihi",
            "Veri yaşı (gün)",
            "Sorun",
            "Önerilen işlem",
            "İş akışı durumu",
            "Çalışma notu",
            "Son güncelleme",
            "Sorun kanıtı",
            "Sorun parmak izi",
        ]
    )
    for task in tasks:
        writer.writerow(
            [
                task.task_id,
                task.symbol,
                task.health_status,
                task.priority,
                task.severity,
                task.latest_date.isoformat() if task.latest_date else "",
                task.age_days if task.age_days is not None else "",
                task.reason,
                task.suggested_action,
                task.workflow_status.value,
                task.workflow_note,
                (
                    task.workflow_updated_at.isoformat()
                    if task.workflow_updated_at
                    else ""
                ),
                (
                    "Güncel"
                    if task.issue_fingerprint_matches
                    else "Değişti - yeniden aç"
                ),
                task.issue_fingerprint,
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def build_market_batch_run_csv(runs: list[MarketBatchRun]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "Çalışma zamanı",
            "Hisse",
            "Sonuç",
            "Açıklama",
            "Toplam",
            "Doğrulandı",
            "Kısmi",
            "Veri yok",
            "Hata",
            "Anlık görüntü parmak izi",
            "Çalışma bütünlüğü",
            "Çalışma parmak izi",
        ]
    )
    for run in runs:
        integrity = (
            "Doğrulandı"
            if run.fingerprint == market_batch_run_fingerprint(run)
            else "Geçersiz"
        )
        for item in run.items:
            writer.writerow(
                [
                    run.observed_at.isoformat(),
                    item.symbol,
                    item.status,
                    item.detail,
                    run.total,
                    run.cross_verified,
                    run.partial,
                    run.unavailable,
                    run.failed,
                    item.snapshot_fingerprint,
                    integrity,
                    run.fingerprint,
                ]
            )
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def build_market_batch_audit_csv(
    audits: list[MarketBatchRunAudit],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "Kayıt ID",
            "Çalışma zamanı",
            "Hisse",
            "Sonuç",
            "Açıklama",
            "Toplam",
            "Doğrulandı",
            "Kısmi",
            "Veri yok",
            "Hata",
            "Denetim durumu",
            "Denetim hatası",
            "Kayıt parmak izi",
        ]
    )
    for audit in audits:
        run = audit.run
        items = run.items if run is not None else (None,)
        for item in items:
            writer.writerow(
                [
                    audit.id,
                    (
                        run.observed_at.isoformat()
                        if run is not None
                        else audit.created_at
                    ),
                    item.symbol if item is not None else "",
                    item.status if item is not None else "",
                    item.detail if item is not None else "",
                    run.total if run is not None else "",
                    run.cross_verified if run is not None else "",
                    run.partial if run is not None else "",
                    run.unavailable if run is not None else "",
                    run.failed if run is not None else "",
                    audit.status,
                    audit.error or "",
                    audit.stored_fingerprint,
                ]
            )
    return ("\ufeff" + output.getvalue()).encode("utf-8")
