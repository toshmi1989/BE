"""Explicit conflict resolution for research evidence — Phase 15.3.

Reviewer must choose VALUE_A / VALUE_B / KEEP_BOTH / REQUEST_MORE_INFORMATION.
Never average. Never auto-pick by source priority.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.research_evidence_models import EvidenceConflictRecord
from app.domain.research_evidence_store import get_claim, list_conflicts, put_claim, put_conflict


RESOLVE_ACTIONS = (
    "VALUE_A",
    "VALUE_B",
    "KEEP_BOTH",
    "REQUEST_MORE_INFORMATION",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_evidence_conflict(
    conflict_id: str,
    *,
    action: str,
    reviewer: str,
    actor: str | None = None,
    rationale: str | None = None,
) -> EvidenceConflictRecord:
    if actor and str(actor).upper() in {"AI", "MOCKAI", "MOCK_AI"}:
        raise PermissionError("AI cannot resolve evidence conflicts")
    if not reviewer or not str(reviewer).strip():
        raise ValueError("reviewer required")
    if action not in RESOLVE_ACTIONS:
        raise ValueError(f"Invalid action: {action}")
    if rationale and "average" in rationale.lower():
        raise ValueError("Averaging conflicting evidence is forbidden")

    conflict = next((c for c in list_conflicts() if c.id == conflict_id), None)
    if conflict is None:
        # also search by task lists
        from app.domain.research_evidence_store import _CONFLICTS

        conflict = _CONFLICTS.get(conflict_id)
    if conflict is None:
        raise KeyError("conflict not found")
    if conflict.status != "OPEN":
        raise ValueError("Conflict is not OPEN")

    ids = list(conflict.claim_ids or [])
    if action in {"VALUE_A", "VALUE_B"} and len(ids) < 2:
        raise ValueError("Need two claim ids for VALUE_A/VALUE_B")

    if action == "VALUE_A":
        keep, drop = ids[0], ids[1:]
        _keep_reject(keep, drop, reviewer, rationale)
        conflict.status = "RESOLVED"
        conflict.resolution = f"VALUE_A selected by {reviewer}: {keep}"
    elif action == "VALUE_B":
        keep, drop = ids[1], [ids[0]] + ids[2:]
        _keep_reject(keep, drop, reviewer, rationale)
        conflict.status = "RESOLVED"
        conflict.resolution = f"VALUE_B selected by {reviewer}: {keep}"
    elif action == "KEEP_BOTH":
        conflict.status = "OPEN"
        conflict.resolution = f"KEEP_BOTH by {reviewer} — both remain visible; not averaged"
        # stay OPEN so task cannot COMPLETE silently
    else:  # REQUEST_MORE_INFORMATION
        conflict.status = "OPEN"
        conflict.resolution = f"REQUEST_MORE_INFORMATION by {reviewer}: {rationale or ''}"
        for cid in ids:
            c = get_claim(cid)
            if c:
                c.usability = "REQUIRES_REVIEW"
                c.review_history.append(
                    {"action": "REQUEST_MORE_INFORMATION", "reviewer": reviewer, "at": _now()}
                )
                put_claim(c)

    conflict.notes = (conflict.notes or "") + f" | resolved_action={action}"
    put_conflict(conflict)
    return conflict


def _keep_reject(keep_id: str, drop_ids: list[str], reviewer: str, rationale: str | None) -> None:
    keep = get_claim(keep_id)
    if keep:
        keep.review_history.append(
            {
                "action": "CONFLICT_SELECTED",
                "reviewer": reviewer,
                "rationale": rationale,
                "at": _now(),
            }
        )
        put_claim(keep)
    for did in drop_ids:
        d = get_claim(did)
        if d:
            d.verification_status = "REJECTED"
            d.usability = "NOT_USABLE_FOR_DECISION"
            d.review_history.append(
                {
                    "action": "CONFLICT_REJECTED",
                    "reviewer": reviewer,
                    "rationale": rationale or "not selected in conflict resolution",
                    "at": _now(),
                }
            )
            put_claim(d)
