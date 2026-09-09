"""Conflict detection for CandidateStudyValue — Phase 14.

No majority vote. No auto-resolve. No Study mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.study_input_classes import CONFLICT_OUTCOMES, CONFLICT_RESOLUTION_STATUSES
from app.domain.study_input_package import CandidateStudyValue


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_value(value: Any) -> str:
    if isinstance(value, list):
        return "|".join(_norm_value(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}"
    if value is None:
        return ""
    s = str(value).strip().lower()
    s = s.replace("мг", "mg").replace("ё", "е")
    # Non-material trailing geography for organization names
    for suffix in (", россия", ", russia", ", рф", ", russian federation"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    s = " ".join(s.split())
    return s


@dataclass
class FieldConflict:
    conflict_id: str
    field_path: str
    candidate_ids: list[str]
    values: list[Any]
    sources: list[dict[str, Any]]
    status: str = "OPEN"
    outcome: str | None = None
    severity: str = "HIGH"
    selected_candidate_id: str | None = None
    reviewer: str | None = None
    reviewed_at: str | None = None
    reason: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_candidate_conflicts(
    candidates: list[CandidateStudyValue],
    *,
    exclude_rejected: bool = True,
) -> list[FieldConflict]:
    by_field: dict[str, list[CandidateStudyValue]] = {}
    for c in candidates:
        if exclude_rejected and c.status == "REJECTED":
            continue
        if c.document_type == "GOLDEN_PROTOCOL":
            continue  # reference output never participates in Study input conflicts
        by_field.setdefault(c.field_path, []).append(c)

    out: list[FieldConflict] = []
    for path, items in sorted(by_field.items()):
        uniq_map: dict[str, list[CandidateStudyValue]] = {}
        for it in items:
            key = _norm_value(it.value)
            uniq_map.setdefault(key, []).append(it)
        if len(uniq_map) <= 1:
            continue
        flat = [x for group in uniq_map.values() for x in group]
        out.append(
            FieldConflict(
                conflict_id=f"SIC-{uuid4().hex[:10]}",
                field_path=path,
                candidate_ids=[c.id for c in flat],
                values=sorted({str(c.value) for c in flat}),
                sources=[
                    {
                        "candidate_id": c.id,
                        "value": c.value,
                        "source_id": c.source_id,
                        "document_type": c.document_type,
                        "status": c.status,
                        "excerpt": c.excerpt,
                        "location": c.location,
                    }
                    for c in flat
                ],
                status="OPEN",
                severity="CRITICAL" if path.endswith(".dose") else "HIGH",
            )
        )
    return out


def resolve_conflict(
    conflict: FieldConflict,
    *,
    reviewer: str,
    outcome: str,
    reason: str,
    selected_candidate_id: str | None = None,
    status: str = "RESOLVED",
) -> FieldConflict:
    if not reviewer or not str(reviewer).strip():
        raise ValueError("reviewer required")
    if not reason or not str(reason).strip():
        raise ValueError("reason required")
    if outcome not in CONFLICT_OUTCOMES:
        raise ValueError(f"Invalid outcome: {outcome}")
    if status not in CONFLICT_RESOLUTION_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    if outcome == "SELECT_VALUE" and not selected_candidate_id:
        raise ValueError("selected_candidate_id required for SELECT_VALUE")
    # Never auto-resolve without explicit reviewer action (this function IS the expert action)
    conflict.status = status
    conflict.outcome = outcome
    conflict.reviewer = reviewer
    conflict.reviewed_at = _now()
    conflict.reason = reason
    conflict.selected_candidate_id = selected_candidate_id
    return conflict


def auto_resolve_forbidden(conflict: FieldConflict) -> None:
    """Hard negative: callers must not silently flip OPEN→RESOLVED."""
    if conflict.status == "OPEN" and conflict.outcome is None and conflict.reviewer is None:
        return
    raise RuntimeError("Conflict appears already resolved — auto-resolve is forbidden")
