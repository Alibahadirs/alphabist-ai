import csv
import io
from datetime import date

from app.market_data.export import build_market_health_queue_csv
from app.market_data.remediation import MarketHealthTask


def test_market_health_queue_csv_is_auditable_and_excel_compatible():
    task = MarketHealthTask(
        task_id="market-123",
        symbol="ASELS",
        health_status="Bütünlük hatası",
        priority=100,
        severity="Kritik",
        reason="Kayıt parmak izi eşleşmiyor.",
        suggested_action="Kaydı yeniden doğrula.",
        issue_fingerprint="abc123",
        latest_date=date(2026, 7, 21),
        age_days=2,
    )

    content = build_market_health_queue_csv((task,))

    assert content.startswith(b"\xef\xbb\xbf")
    rows = list(
        csv.reader(io.StringIO(content.decode("utf-8-sig")))
    )
    assert rows[0] == [
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
    assert rows[1] == [
        "market-123",
        "ASELS",
        "Bütünlük hatası",
        "100",
        "Kritik",
        "2026-07-21",
        "2",
        "Kayıt parmak izi eşleşmiyor.",
        "Kaydı yeniden doğrula.",
        "Açık",
        "",
        "",
        "Güncel",
        "abc123",
    ]


def test_market_health_queue_csv_handles_missing_dates_and_age():
    task = MarketHealthTask(
        task_id="market-456",
        symbol="BIMAS",
        health_status="Veri yok",
        priority=80,
        severity="Yüksek",
        reason="Henüz kayıt yok.",
        suggested_action="Sağlayıcıları kontrol et.",
        issue_fingerprint="def456",
        latest_date=None,
        age_days=None,
    )

    rows = list(
        csv.reader(
            io.StringIO(
                build_market_health_queue_csv((task,)).decode("utf-8-sig")
            )
        )
    )

    assert rows[1][5:7] == ["", ""]
