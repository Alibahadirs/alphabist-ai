from app.market_data.batch import diagnose_market_batch
from app.market_data.diagnostics import MarketDiagnostic, ProviderDiagnostic


def _provider(available=True):
    return ProviderDiagnostic(
        provider="Test",
        available=available,
        eligible=available,
        freshness_status="Güncel günlük veri" if available else "Veri alınamadı",
        quote={"last": 100} if available else None,
        error=None if available else "kapalı",
    )


def _diagnostic(symbol, verified=True, available=True):
    return MarketDiagnostic(
        symbol=symbol,
        primary=_provider(available),
        secondary=_provider(available),
        comparison=None,
        cross_verified=verified,
        status="test",
    )


def test_market_batch_normalizes_deduplicates_and_counts_results():
    def loader(symbol):
        if symbol == "FAIL":
            raise RuntimeError("bağlantı hatası")
        if symbol == "NONE":
            return _diagnostic(symbol, verified=False, available=False)
        return _diagnostic(symbol, verified=symbol == "GOOD")

    summary = diagnose_market_batch(
        [" good ", "GOOD", "PART", "NONE", "FAIL"],
        loader,
    )

    assert summary.total == 4
    assert summary.cross_verified == 1
    assert summary.partial == 1
    assert summary.unavailable == 1
    assert summary.failed == 1
    assert [item.symbol for item in summary.items] == [
        "GOOD",
        "PART",
        "NONE",
        "FAIL",
    ]


def test_market_batch_rejects_invalid_or_oversized_input():
    try:
        diagnose_market_batch(["THYAO;DROP"])
    except ValueError as exc:
        assert "Geçersiz hisse kodu" in str(exc)
    else:
        raise AssertionError("Geçersiz hisse kodu kabul edildi")

    try:
        diagnose_market_batch([f"S{index}" for index in range(21)])
    except ValueError as exc:
        assert "en fazla 20" in str(exc)
    else:
        raise AssertionError("Toplu işlem limiti uygulanmadı")
