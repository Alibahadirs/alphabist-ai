from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator

from app.market_data.batch import MarketBatchSummary
from app.market_data.models import build_market_diagnostic_snapshot


class MarketBatchRunItem(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    status: str
    detail: str
    snapshot_fingerprint: str = ""


class MarketBatchRun(BaseModel):
    id: int | None = None
    observed_at: datetime
    total: int = Field(ge=0)
    cross_verified: int = Field(ge=0)
    partial: int = Field(ge=0)
    unavailable: int = Field(ge=0)
    failed: int = Field(ge=0)
    items: tuple[MarketBatchRunItem, ...]
    fingerprint: str = ""
    created_at: str | None = None

    @model_validator(mode="after")
    def validate_counts(self) -> "MarketBatchRun":
        expected = {
            "total": len(self.items),
            "cross_verified": sum(
                item.status == "Çapraz doğrulandı" for item in self.items
            ),
            "partial": sum(item.status == "Kısmi veri" for item in self.items),
            "unavailable": sum(item.status == "Veri yok" for item in self.items),
            "failed": sum(item.status == "Hata" for item in self.items),
        }
        actual = {field: getattr(self, field) for field in expected}
        if actual != expected:
            raise ValueError("Toplu piyasa kontrolü sayaçları sonuçlarla uyuşmuyor.")
        return self


def build_market_batch_run(
    summary: MarketBatchSummary,
    observed_at: datetime | None = None,
) -> MarketBatchRun:
    items = tuple(
        MarketBatchRunItem(
            symbol=item.symbol,
            status=item.status,
            detail=item.detail,
            snapshot_fingerprint=(
                build_market_diagnostic_snapshot(item.diagnostic).fingerprint
                if item.diagnostic is not None
                else ""
            ),
        )
        for item in summary.items
    )
    run = MarketBatchRun(
        observed_at=observed_at or datetime.now(timezone.utc),
        total=summary.total,
        cross_verified=summary.cross_verified,
        partial=summary.partial,
        unavailable=summary.unavailable,
        failed=summary.failed,
        items=items,
    )
    return run.model_copy(
        update={"fingerprint": market_batch_run_fingerprint(run)}
    )


def market_batch_run_fingerprint(run: MarketBatchRun) -> str:
    payload = run.model_dump(
        mode="json",
        exclude={"id", "fingerprint", "created_at"},
    )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
