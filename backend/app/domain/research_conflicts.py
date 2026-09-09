"""Research evidence conflicts — Phase 15.2. Never average."""

from __future__ import annotations

from typing import Any

from app.domain.research_evidence_models import EvidenceConflictRecord, ResearchClaim


def detect_numeric_conflicts(
    claims: list[ResearchClaim],
    *,
    field_path: str,
    research_task_id: str | None = None,
    study_id: str | None = None,
    relative_tolerance: float = 0.15,
) -> list[EvidenceConflictRecord]:
    """Material numeric differences → OPEN conflict. Do not average."""
    relevant = [
        c
        for c in claims
        if c.field_path == field_path and c.verification_status != "REJECTED"
    ]
    numeric: list[tuple[ResearchClaim, float]] = []
    for c in relevant:
        # Skip pure ranges without point value for averaging check — still conflict if differ
        v = c.value
        if isinstance(v, (int, float)):
            numeric.append((c, float(v)))
        elif isinstance(v, str) and "-" in v and c.measurement and c.measurement.get("statistic_type") == "RANGE":
            continue  # ranges handled separately
        else:
            try:
                numeric.append((c, float(v)))
            except (TypeError, ValueError):
                continue
    if len(numeric) < 2:
        return []

    values = [v for _, v in numeric]
    vmin, vmax = min(values), max(values)
    if vmin == 0:
        material = vmax != 0
    else:
        material = abs(vmax - vmin) / abs(vmin) > relative_tolerance
    if not material:
        return []

    return [
        EvidenceConflictRecord(
            field_path=field_path,
            claim_ids=[c.claim_id or c.id for c, _ in numeric],
            values=[v for _, v in numeric],
            research_task_id=research_task_id,
            study_id=study_id,
            severity="HIGH",
            status="OPEN",
            notes="Do not average conflicting values; do not auto-pick authority",
        )
    ]


def assert_no_average(conflict: EvidenceConflictRecord) -> None:
    if conflict.resolution and "average" in conflict.resolution.lower():
        raise ValueError("Averaging conflicting evidence is forbidden")


def merge_forbidden(claim_a: ResearchClaim, claim_b: ResearchClaim) -> bool:
    """Different PK parameters / variability types must not merge."""
    if claim_a.field_path != claim_b.field_path:
        return True
    ca = claim_a.cvintra or {}
    cb = claim_b.cvintra or {}
    if ca and cb:
        if ca.get("PK_parameter") != cb.get("PK_parameter"):
            return True
        if ca.get("variability_type") != cb.get("variability_type"):
            return True
    return False
