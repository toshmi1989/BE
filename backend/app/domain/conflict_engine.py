"""Conflict detection across evidence claims — never auto-resolve."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ClaimSnippet:
    evidence_id: str
    claim_id: str
    field_name: str
    value: str | None
    normalized_value: dict | None
    status: str


@dataclass
class ConflictDraft:
    field_name: str
    evidence_ids: list[str]
    values: list[Any]
    severity: str = "WARNING"


def _norm_key(nv: dict | None, value: str | None) -> str:
    if nv:
        if "min" in nv and "max" in nv:
            return f"range:{nv.get('min')}-{nv.get('max')}:{nv.get('unit')}"
        if "value" in nv:
            return f"value:{nv.get('value')}:{nv.get('unit')}"
    return f"raw:{(value or '').strip().lower()}"


def detect_conflicts(claims: list[ClaimSnippet]) -> list[ConflictDraft]:
    by_field: dict[str, list[ClaimSnippet]] = {}
    for c in claims:
        if c.status == "REJECTED":
            continue
        by_field.setdefault(c.field_name, []).append(c)

    conflicts: list[ConflictDraft] = []
    for field_name, group in sorted(by_field.items()):
        keys = {_norm_key(c.normalized_value, c.value) for c in group}
        if len(keys) <= 1:
            continue
        conflicts.append(
            ConflictDraft(
                field_name=field_name,
                evidence_ids=sorted({c.evidence_id for c in group}),
                values=[
                    {
                        "claim_id": c.claim_id,
                        "value": c.value,
                        "normalized_value": c.normalized_value,
                    }
                    for c in group
                ],
                severity="WARNING",
            )
        )
    return conflicts
