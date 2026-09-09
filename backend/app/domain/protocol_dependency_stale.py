"""Phase 28 — Detect stale protocol draft dependencies vs current approved state."""

from __future__ import annotations

from typing import Any

from app.domain.decision_store import list_decisions
from app.domain.sample_size_store import list_calculations
from app.domain.statistics_store import latest_plan as latest_stats_plan
from app.domain.study_workspace import list_protocol_drafts


def _approved_sample_size(study_id: str):
    calcs = list_calculations(study_id)
    approved = [c for c in calcs if str(c.status).upper() in {"ACCEPTED", "APPROVED"}]
    return approved[-1] if approved else None


def detect_stale_protocol_dependencies(
    study_id: str,
    *,
    draft: dict[str, Any] | None = None,
    current_snapshot_id: str | None = None,
    current_snapshot_version: int | None = None,
) -> dict[str, Any]:
    """Compare latest protocol draft based_on_* against current authoritative state.

    Stale means the draft's recorded dependency *identities* drifted (or an
    approved dependency was revoked). Missing approvals are separate preflight
    gates (PRIMARY_BE_APPROVED / SAMPLE_SIZE_APPROVED), not staleness.
    """
    drafts = list_protocol_drafts(study_id)
    d = draft or (drafts[-1] if drafts else None)
    if not d:
        return {"stale": False, "reasons": [], "draft_version": None}

    reasons: list[dict[str, Any]] = []
    based_snap = d.get("based_on_snapshot")
    based_stats = d.get("based_on_statistics")
    based_ss = d.get("based_on_sample_size")
    based_decisions = set(d.get("based_on_decisions") or [])

    if current_snapshot_id and based_snap and based_snap != current_snapshot_id:
        # Ignore provisional package_id style refs that are clearly not SNAP-*
        if str(based_snap).startswith("SNAP") or str(current_snapshot_id).startswith("SNAP"):
            reasons.append(
                {
                    "code": "STALE_SNAPSHOT",
                    "field": "based_on_snapshot",
                    "expected": based_snap,
                    "actual": current_snapshot_id,
                    "message": "Protocol draft is based on an older snapshot",
                }
            )

    st = latest_stats_plan(study_id)
    if based_stats:
        if st is None or st.id != based_stats:
            reasons.append(
                {
                    "code": "STALE_STATISTICS_PLAN",
                    "field": "based_on_statistics",
                    "expected": based_stats,
                    "actual": getattr(st, "id", None),
                    "message": "Protocol draft statistics plan is not current",
                }
            )
        elif str(st.status).upper() in {"REJECTED", "SUPERSEDED", "WITHDRAWN", "REVOKED"}:
            reasons.append(
                {
                    "code": "STALE_STATISTICS_PLAN",
                    "field": "statistics_status",
                    "expected": "APPROVED",
                    "actual": st.status,
                    "message": "Statistics plan used by draft was revoked",
                }
            )

    approved_ss = _approved_sample_size(study_id)
    if based_ss:
        all_calcs = list_calculations(study_id)
        based_calc = next((c for c in all_calcs if c.id == based_ss), None)
        # Drift: an approved calculation exists and is not the one the draft used
        if approved_ss is not None and approved_ss.id != based_ss:
            reasons.append(
                {
                    "code": "STALE_SAMPLE_SIZE_CALC",
                    "field": "based_on_sample_size",
                    "expected": based_ss,
                    "actual": approved_ss.id,
                    "message": "Protocol draft sample size calculation is not current",
                }
            )
        # Revoke: draft's calc existed as accepted and is no longer
        elif based_calc is not None and str(based_calc.status).upper() in {
            "REJECTED",
            "SUPERSEDED",
            "WITHDRAWN",
            "REVOKED",
        }:
            reasons.append(
                {
                    "code": "STALE_SAMPLE_SIZE_STATUS",
                    "field": "sample_size_status",
                    "expected": "ACCEPTED",
                    "actual": based_calc.status,
                    "message": "Sample size used by draft was revoked",
                }
            )

    current_decision_ids = {dec.id for dec in list_decisions(study_id) if dec.status != "SUPERSEDED"}
    if based_decisions and not based_decisions.issubset(current_decision_ids):
        reasons.append(
            {
                "code": "STALE_DECISION_SET",
                "field": "based_on_decisions",
                "expected": sorted(based_decisions),
                "actual": sorted(current_decision_ids),
                "message": "Protocol draft decision set no longer matches current decisions",
            }
        )

    return {
        "stale": bool(reasons),
        "reasons": reasons,
        "draft_version": d.get("version"),
        "draft_protocol_id": d.get("protocol_id"),
        "current_snapshot_id": current_snapshot_id,
        "current_snapshot_version": current_snapshot_version,
        "code": "PROTOCOL_DEPENDENCIES_STALE" if reasons else None,
    }
