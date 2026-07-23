from datetime import date

from app.market_data.health import MarketHealthItem, MarketHealthSummary
from app.market_data.remediation import (
    build_market_health_queue,
    filter_market_health_queue,
    summarize_market_health_queue,
)


def _summary(*items: MarketHealthItem) -> MarketHealthSummary:
    return MarketHealthSummary(
        items=items,
        verified=sum(item.status == "Doğrulandı" for item in items),
        partial=sum(item.status == "Kısmi" for item in items),
        unavailable=sum(item.status == "Veri yok" for item in items),
        stale=sum(item.status == "Eski" for item in items),
        invalid=sum(item.status == "Bütünlük hatası" for item in items),
    )


def _item(
    symbol: str,
    status: str,
    priority: int,
    detail: str,
) -> MarketHealthItem:
    return MarketHealthItem(
        symbol=symbol,
        status=status,
        priority=priority,
        latest_date=date(2026, 7, 21),
        age_days=2,
        cross_verified=status == "Doğrulandı",
        integrity_valid=status != "Bütünlük hatası",
        detail=detail,
    )


def test_queue_omits_verified_items_and_orders_by_priority():
    queue = build_market_health_queue(
        _summary(
            _item("AKSA", "Doğrulandı", 0, "Tamam"),
            _item("THYAO", "Kısmi", 50, "Tek kaynak"),
            _item("BIMAS", "Veri yok", 80, "Fiyat yok"),
            _item("GARAN", "Eski", 90, "Tarih eski"),
            _item("ASELS", "Bütünlük hatası", 100, "Bozuk kayıt"),
        )
    )

    assert [task.symbol for task in queue] == [
        "ASELS",
        "GARAN",
        "BIMAS",
        "THYAO",
    ]
    assert [task.severity for task in queue] == [
        "Kritik",
        "Kritik",
        "Yüksek",
        "Orta",
    ]
    assert "bütünlüğünü" in queue[0].suggested_action
    assert "sağlayıcılarını" in queue[2].suggested_action


def test_task_id_is_stable_while_issue_fingerprint_tracks_changes():
    first = build_market_health_queue(
        _summary(_item("AKSA", "Eski", 90, "İki gün eski"))
    )[0]
    second = build_market_health_queue(
        _summary(_item("AKSA", "Eski", 90, "Üç gün eski"))
    )[0]

    assert first.task_id == second.task_id
    assert first.issue_fingerprint != second.issue_fingerprint


def test_queue_filters_by_query_status_severity_and_priority():
    queue = build_market_health_queue(
        _summary(
            _item("ASELS", "Bütünlük hatası", 100, "Bozuk kayıt"),
            _item("GARAN", "Eski", 90, "Gecikmeli fiyat"),
            _item("BIMAS", "Veri yok", 80, "Sağlayıcı yanıt vermedi"),
            _item("THYAO", "Kısmi", 50, "Tek kaynak"),
        )
    )

    assert [
        task.symbol
        for task in filter_market_health_queue(queue, query="sağlayıcı")
    ] == ["BIMAS", "THYAO"]
    assert [
        task.symbol
        for task in filter_market_health_queue(
            queue,
            statuses={"Eski", "Veri yok"},
        )
    ] == ["GARAN", "BIMAS"]
    assert [
        task.symbol
        for task in filter_market_health_queue(
            queue,
            severities={"Kritik"},
            minimum_priority=95,
        )
    ] == ["ASELS"]


def test_empty_filter_selection_returns_no_tasks():
    queue = build_market_health_queue(
        _summary(_item("ASELS", "Bütünlük hatası", 100, "Bozuk kayıt"))
    )

    assert filter_market_health_queue(queue, statuses=set()) == ()
    assert filter_market_health_queue(queue, severities=set()) == ()


def test_queue_summary_counts_severity_and_unique_symbols():
    queue = build_market_health_queue(
        _summary(
            _item("ASELS", "Bütünlük hatası", 100, "Bozuk kayıt"),
            _item("GARAN", "Eski", 90, "Gecikmeli fiyat"),
            _item("BIMAS", "Veri yok", 80, "Fiyat yok"),
            _item("THYAO", "Kısmi", 50, "Tek kaynak"),
        )
    )

    summary = summarize_market_health_queue(queue)

    assert summary.total == 4
    assert summary.critical == 2
    assert summary.high == 1
    assert summary.medium == 1
    assert summary.affected_symbols == 4
