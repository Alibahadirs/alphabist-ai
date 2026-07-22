from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ValidationError, model_validator

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


@dataclass(frozen=True)
class MarketBatchRunAudit:
    id: int
    run: MarketBatchRun | None
    integrity_valid: bool
    status: str
    error: str | None
    stored_fingerprint: str
    created_at: str


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


def audit_market_batch_run_payload(
    *,
    record_id: int,
    run_payload: str,
    stored_fingerprint: str,
    created_at: str,
) -> MarketBatchRunAudit:
    try:
        payload = json.loads(run_payload)
    except (json.JSONDecodeError, TypeError) as exc:
        return MarketBatchRunAudit(
            id=record_id,
            run=None,
            integrity_valid=False,
            status="Yük bozuk",
            error=str(exc),
            stored_fingerprint=stored_fingerprint,
            created_at=created_at,
        )
    if not isinstance(payload, dict):
        return MarketBatchRunAudit(
            id=record_id,
            run=None,
            integrity_valid=False,
            status="Yük bozuk",
            error="Toplu çalışma yükü JSON nesnesi değil.",
            stored_fingerprint=stored_fingerprint,
            created_at=created_at,
        )

    payload.update(id=record_id, created_at=created_at)
    try:
        run = MarketBatchRun(**payload)
    except ValidationError as exc:
        return MarketBatchRunAudit(
            id=record_id,
            run=None,
            integrity_valid=False,
            status="Şema hatası",
            error=str(exc),
            stored_fingerprint=stored_fingerprint,
            created_at=created_at,
        )

    calculated_fingerprint = market_batch_run_fingerprint(run)
    integrity_valid = bool(
        run.fingerprint
        and run.fingerprint == stored_fingerprint
        and run.fingerprint == calculated_fingerprint
    )
    return MarketBatchRunAudit(
        id=record_id,
        run=run,
        integrity_valid=integrity_valid,
        status="Doğrulandı" if integrity_valid else "Parmak izi hatası",
        error=None if integrity_valid else "Kayıt içeriği parmak iziyle eşleşmiyor.",
        stored_fingerprint=stored_fingerprint,
        created_at=created_at,
    )
