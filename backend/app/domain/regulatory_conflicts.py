"""Evidence conflicts & StudyEvidenceConflict — Phase 13.1.

Conflicts are detected, never auto-resolved. No Study mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.regulatory_source_classes import CONFLICT_TYPES


@dataclass
class ClassifiedEvidenceConflict:
    conflict_id: str
    conflict_type: str
    affected_field: str
    claim_ids: list[str]
    source_ids: list[str]
    values: list[Any]
    severity: str = "MEDIUM"  # LOW|MEDIUM|HIGH|CRITICAL
    resolution_status: str = "OPEN"  # OPEN|IN_REVIEW|RESOLVED
    resolution: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StudyEvidenceConflict:
    conflict_id: str
    study_field: str
    canonical_value: Any
    source_value: Any
    source_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    severity: str = "HIGH"
    resolution_status: str = "OPEN"
    resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_conflict_type(
    *,
    same_field: bool,
    different_jurisdiction: bool = False,
    different_version: bool = False,
    different_population: bool = False,
    different_definition: bool = False,
    different_methodology: bool = False,
    different_time: bool = False,
) -> str:
    if different_version:
        return "VERSION_CONFLICT"
    if different_jurisdiction:
        return "JURISDICTION_CONFLICT"
    if different_population:
        return "POPULATION_CONFLICT"
    if different_definition:
        return "DEFINITION_CONFLICT"
    if different_methodology:
        return "METHODOLOGY_CONFLICT"
    if different_time:
        return "TIME_CONFLICT"
    if same_field:
        return "VALUE_CONFLICT"
    return "VALUE_CONFLICT"


def detect_value_conflicts(claims: list[dict[str, Any]]) -> list[ClassifiedEvidenceConflict]:
    """Group by field_name; emit conflict when normalized values differ. No auto-resolve."""
    by_field: dict[str, list[dict]] = {}
    for c in claims:
        fn = str(c.get("field_name") or "")
        if not fn:
            continue
        by_field.setdefault(fn, []).append(c)
    out: list[ClassifiedEvidenceConflict] = []
    n = 0
    for fn, items in sorted(by_field.items()):
        vals = []
        for it in items:
            v = it.get("normalized_claim") or it.get("normalized_value") or it.get("value") or it.get("raw_extract")
            vals.append(v)
        uniq = {str(v) for v in vals if v is not None}
        if len(uniq) <= 1:
            continue
        n += 1
        ctype = classify_conflict_type(same_field=True)
        assert ctype in CONFLICT_TYPES
        out.append(
            ClassifiedEvidenceConflict(
                conflict_id=f"EC-{n:03d}",
                conflict_type=ctype,
                affected_field=fn,
                claim_ids=[str(it.get("claim_id") or it.get("id") or "") for it in items],
                source_ids=sorted(
                    {
                        str(s)
                        for it in items
                        for s in (it.get("source_ids") or ([it.get("source_id")] if it.get("source_id") else []))
                        if s
                    }
                ),
                values=list(uniq),
                severity="HIGH",
                resolution_status="OPEN",
            )
        )
    return out


def detect_study_evidence_conflict(
    *,
    study_field: str,
    canonical_value: Any,
    source_value: Any,
    source_ids: list[str] | None = None,
    claim_ids: list[str] | None = None,
    conflict_id: str = "SEC-001",
) -> StudyEvidenceConflict | None:
    """If source disagrees with canonical study — conflict, do NOT update Study."""
    if canonical_value is None or source_value is None:
        return None
    if str(canonical_value).strip() == str(source_value).strip():
        return None
    return StudyEvidenceConflict(
        conflict_id=conflict_id,
        study_field=study_field,
        canonical_value=canonical_value,
        source_value=source_value,
        source_ids=list(source_ids or []),
        claim_ids=list(claim_ids or []),
        severity="HIGH",
        resolution_status="OPEN",
    )


def resolve_conflict_forbidden_auto(conflict: ClassifiedEvidenceConflict | StudyEvidenceConflict) -> None:
    """Hard guard used by tests: automatic resolution is not allowed in this module."""
    raise RuntimeError("Automatic conflict resolution is forbidden in Phase 13.1")
