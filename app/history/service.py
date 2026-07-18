from collections.abc import Sequence

from app.audit.models import CompanyDataAudit
from app.history.models import ScoreHistoryEntry


def select_previous_comparable_audit(
    history: Sequence[CompanyDataAudit],
) -> CompanyDataAudit | None:
    if len(history) < 2:
        return None
    current = history[-1]
    return next(
        (
            audit
            for audit in reversed(history[:-1])
            if audit.methodology_version == current.methodology_version
        ),
        None,
    )


def calculate_latest_comparable_score_delta(
    history: Sequence[ScoreHistoryEntry],
    methodology_version: str,
) -> float | None:
    compatible = sorted(
        (
            entry
            for entry in history
            if entry.methodology_version == methodology_version
        ),
        key=lambda entry: entry.id,
    )
    if len(compatible) < 2:
        return None
    return round(
        compatible[-1].total_score - compatible[-2].total_score,
        2,
    )
