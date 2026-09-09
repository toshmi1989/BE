"""Bridge verified usable research evidence → Decision Engine — Phase 15.2.

Does NOT approve decisions. Does NOT mutate Study ORM.
May supply verified numeric context for recompute only.
"""

from __future__ import annotations

from typing import Any

from app.domain.decision_context import DecisionContext
from app.domain.decision_dependency import domains_affected_by_field
from app.domain.decision_engine import invalidate_on_upstream_change, recompute_decisions
from app.domain.decision_models import ProtocolDecision
from app.domain.research_evidence_store import list_claims
from app.domain.research_usability import can_unblock_decision


def apply_verified_research_to_context(
    ctx: DecisionContext,
    *,
    study_id: str | None = None,
) -> tuple[DecisionContext, list[str]]:
    """Inject VERIFIED + USABLE measurements into DecisionContext. No Study mutation."""
    sid = study_id or ctx.study_id
    applied: list[str] = []
    claims = list_claims(study_id=sid)
    for c in claims:
        if c.verification_status != "VERIFIED":
            continue
        if c.usability != "USABLE_FOR_DECISION":
            continue
        if c.applicability in {"LOW", "NOT_APPLICABLE", "UNKNOWN"}:
            continue
        if c.field_path == "pk.t_half" and c.measurement:
            # Only point values — ranges do not set half_life scalar
            if c.measurement.get("statistic_type") == "RANGE":
                continue
            if c.value is not None and isinstance(c.value, (int, float)):
                ctx.half_life = float(c.value)
                ctx.structured_facts["pk.t_half"] = float(c.value)
                ctx.fact_statuses["pk.t_half"] = "VERIFIED"
                ctx.fact_sources["pk.t_half"] = "RESEARCH_EVIDENCE"
                applied.append("pk.t_half")
                # Remove gap if present
                ctx.knowledge_gaps = [
                    g for g in ctx.knowledge_gaps if g.get("code") != "MISSING_HALF_LIFE_FOR_WASHOUT"
                ]
        elif c.field_path == "pk.Tmax" and isinstance(c.value, (int, float)):
            ctx.tmax = float(c.value)
            ctx.structured_facts["pk.Tmax"] = float(c.value)
            ctx.fact_statuses["pk.Tmax"] = "VERIFIED"
            ctx.fact_sources["pk.Tmax"] = "RESEARCH_EVIDENCE"
            applied.append("pk.Tmax")
            ctx.knowledge_gaps = [
                g for g in ctx.knowledge_gaps if g.get("code") != "MISSING_TMAX_FOR_SAMPLING"
            ]
        elif c.field_path == "cv_intra" and c.cvintra and c.cvintra.get("is_cvintra"):
            if can_unblock_decision(c, domain="DESIGN"):
                ctx.cvintra = c.cvintra.get("CV_value")
                ctx.structured_facts["cv_intra"] = ctx.cvintra
                ctx.fact_statuses["cv_intra"] = "VERIFIED"
                ctx.fact_sources["cv_intra"] = "RESEARCH_EVIDENCE"
                applied.append("cv_intra")
                ctx.knowledge_gaps = [
                    g for g in ctx.knowledge_gaps if g.get("code") != "MISSING_CVINTRA"
                ]
    ctx.study_mutated = False
    return ctx, applied


def recompute_affected_decisions(
    ctx: DecisionContext,
    *,
    applied_fields: list[str],
    previous: list[ProtocolDecision] | None = None,
) -> dict[str, Any]:
    """Dependency-aware recompute after research evidence applied."""
    domains: set[str] = set()
    for fp in applied_fields:
        domains.update(domains_affected_by_field(fp if fp != "cv_intra" else "CVintra"))
        if fp == "pk.t_half":
            domains.update({"WASHOUT", "SAMPLING"})
        if fp == "pk.Tmax":
            domains.add("SAMPLING")
        if fp == "cv_intra":
            domains.add("DESIGN")
    if not domains:
        return {
            "recomputed_domains": [],
            "decisions": previous or [],
            "study_mutated": False,
            "automatic_medical_decisions": 0,
        }
    # Invalidate then recompute only affected
    if previous:
        for fp in applied_fields:
            invalidate_on_upstream_change(previous, changed_field=fp)
    decisions = recompute_decisions(ctx, previous=previous, domains=sorted(domains))
    return {
        "recomputed_domains": sorted(domains),
        "unaffected_note": "FOOD not recomputed unless dependency registry requires",
        "decisions": decisions,
        "study_mutated": False,
        "automatic_medical_decisions": 0,
        "expert_decisions": 0,
    }
