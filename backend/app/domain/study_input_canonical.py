"""Canonical resolution — Phase 14.

Only VERIFIED / explicitly resolved candidates may populate Study projection.
Extraction never mutates Study. Previous protocol never overwrites Study.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.study_input_package import CandidateStudyValue


@dataclass
class CanonicalResolutionResult:
    applied: dict[str, Any] = field(default_factory=dict)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    study_mutated: bool = False  # always False in this phase — projection only
    notes: str = "Projection only; Study ORM not mutated by extraction"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_to_canonical_projection(
    candidates: list[CandidateStudyValue],
    *,
    conflicts: list[dict[str, Any]] | None = None,
    require_verified: bool = True,
) -> CanonicalResolutionResult:
    """Build a read-only projection dict. Never mutates Study."""
    conflicts = conflicts or []
    open_conflict_fields = {
        str(c.get("field_path"))
        for c in conflicts
        if str(c.get("status") or "OPEN") in {"OPEN", "UNDER_REVIEW"}
    }
    # For SELECT_VALUE resolved conflicts, prefer selected candidate
    selected_by_field: dict[str, str] = {}
    for c in conflicts:
        if str(c.get("status")) == "RESOLVED" and c.get("selected_candidate_id"):
            selected_by_field[str(c.get("field_path"))] = str(c["selected_candidate_id"])

    by_field: dict[str, list[CandidateStudyValue]] = {}
    for cand in candidates:
        if cand.document_type in {"GOLDEN_PROTOCOL", "PREVIOUS_PROTOCOL", "OTHER"}:
            # Contextual / non-authoritative for Study fields
            continue
        by_field.setdefault(cand.field_path, []).append(cand)

    result = CanonicalResolutionResult()
    for path, items in sorted(by_field.items()):
        if path in open_conflict_fields:
            result.skipped.append(
                {"field_path": path, "reason": "OPEN_CONFLICT", "candidate_ids": [i.id for i in items]}
            )
            continue
        selected_id = selected_by_field.get(path)
        if selected_id:
            chosen = next((i for i in items if i.id == selected_id), None)
            if chosen is None:
                result.skipped.append({"field_path": path, "reason": "SELECTED_CANDIDATE_MISSING"})
                continue
            if require_verified and chosen.status != "VERIFIED":
                result.skipped.append(
                    {"field_path": path, "reason": "SELECTED_NOT_VERIFIED", "candidate_id": chosen.id}
                )
                continue
            result.applied[path] = {
                "value": chosen.value,
                "candidate_id": chosen.id,
                "source_id": chosen.source_id,
                "status": chosen.status,
            }
            continue

        verified = [i for i in items if i.status == "VERIFIED"]
        if require_verified:
            if len(verified) == 1:
                v = verified[0]
                result.applied[path] = {
                    "value": v.value,
                    "candidate_id": v.id,
                    "source_id": v.source_id,
                    "status": v.status,
                }
            elif len(verified) > 1:
                # Still conflicting verified values — skip
                result.skipped.append(
                    {
                        "field_path": path,
                        "reason": "MULTIPLE_VERIFIED",
                        "candidate_ids": [i.id for i in verified],
                    }
                )
            else:
                result.skipped.append(
                    {
                        "field_path": path,
                        "reason": "NOT_VERIFIED",
                        "candidate_ids": [i.id for i in items],
                        "statuses": [i.status for i in items],
                    }
                )
        else:
            # Non-authoritative preview only
            result.skipped.append(
                {
                    "field_path": path,
                    "reason": "PREVIEW_ONLY_REQUIRE_VERIFIED",
                    "candidate_ids": [i.id for i in items],
                }
            )

    result.study_mutated = False
    return result


def assert_extraction_does_not_mutate_study(before: dict[str, Any], after: dict[str, Any]) -> None:
    if before != after:
        raise AssertionError("Study mutated by extraction — forbidden")
