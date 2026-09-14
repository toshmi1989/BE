"""Bridge verified usable research evidence → Decision Engine — Phase 15.2.

Does NOT approve decisions. Does NOT mutate Study ORM.
May supply verified numeric context for recompute only.
"""

from __future__ import annotations

import re
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
        if c.field_path in {"pk.t_half", "pk.expected_t_half"} and (
            c.measurement or c.value is not None
        ):
            # Planning half-life may be a SmPC range (e.g. 9–14 h). Ranges populate
            # structured facts for protocol text but do NOT set washout scalar.
            is_range = bool(
                (c.measurement or {}).get("statistic_type") == "RANGE"
                or (
                    isinstance(c.value, str)
                    and re.search(r"[–\-—to]", c.value)
                )
            )
            if is_range:
                val = c.value
                if val is None and c.measurement:
                    val = c.measurement.get("range") or c.measurement.get("value")
                if val in (None, "", []):
                    continue
                ctx.structured_facts["pk.expected_t_half"] = val
                ctx.structured_facts["pk.t_half"] = val
                ctx.fact_statuses["pk.expected_t_half"] = "VERIFIED"
                ctx.fact_statuses["pk.t_half"] = "VERIFIED"
                ctx.fact_sources["pk.expected_t_half"] = "RESEARCH_EVIDENCE"
                ctx.fact_sources["pk.t_half"] = "RESEARCH_EVIDENCE"
                applied.extend(["pk.expected_t_half", "pk.t_half"])
                # MISSING_HALF_LIFE_FOR_WASHOUT remains — washout needs expert point
                continue
            if c.value is not None and isinstance(c.value, (int, float)):
                ctx.half_life = float(c.value)
                ctx.structured_facts["pk.expected_t_half"] = float(c.value)
                ctx.structured_facts["pk.t_half"] = float(c.value)
                ctx.fact_statuses["pk.expected_t_half"] = "VERIFIED"
                ctx.fact_statuses["pk.t_half"] = "VERIFIED"
                ctx.fact_sources["pk.expected_t_half"] = "RESEARCH_EVIDENCE"
                ctx.fact_sources["pk.t_half"] = "RESEARCH_EVIDENCE"
                # Both names carry the same verified planning value
                applied.extend(["pk.expected_t_half", "pk.t_half"])
                ctx.knowledge_gaps = [
                    g for g in ctx.knowledge_gaps if g.get("code") != "MISSING_HALF_LIFE_FOR_WASHOUT"
                ]
            elif isinstance(c.value, str) and c.value.strip():
                # Point-like string without range separators
                raw = c.value.strip().replace(",", ".")
                m = re.search(r"(\d+(?:\.\d+)?)", raw)
                if m:
                    ctx.half_life = float(m.group(1))
                    ctx.structured_facts["pk.expected_t_half"] = float(m.group(1))
                    ctx.structured_facts["pk.t_half"] = float(m.group(1))
                    ctx.fact_statuses["pk.expected_t_half"] = "VERIFIED"
                    ctx.fact_statuses["pk.t_half"] = "VERIFIED"
                    ctx.fact_sources["pk.expected_t_half"] = "RESEARCH_EVIDENCE"
                    ctx.fact_sources["pk.t_half"] = "RESEARCH_EVIDENCE"
                    applied.extend(["pk.expected_t_half", "pk.t_half"])
                    ctx.knowledge_gaps = [
                        g
                        for g in ctx.knowledge_gaps
                        if g.get("code") != "MISSING_HALF_LIFE_FOR_WASHOUT"
                    ]
        elif c.field_path in {"pk.Tmax", "pk.expected_tmax"} and (
            isinstance(c.value, (int, float))
            or (isinstance(c.value, str) and c.value.strip())
            or (c.measurement and c.measurement.get("statistic_type") == "RANGE")
        ):
            # Verified expected (planning) Tmax — may be point or range (e.g. 2–4 h)
            val = c.value
            if val is None and c.measurement:
                val = c.measurement.get("range") or c.measurement.get("value")
            ctx.tmax = val
            ctx.structured_facts["pk.expected_tmax"] = val
            ctx.structured_facts["pk.Tmax"] = val
            ctx.fact_statuses["pk.expected_tmax"] = "VERIFIED"
            ctx.fact_statuses["pk.Tmax"] = "VERIFIED"
            ctx.fact_sources["pk.expected_tmax"] = "RESEARCH_EVIDENCE"
            ctx.fact_sources["pk.Tmax"] = "RESEARCH_EVIDENCE"
            applied.extend(["pk.expected_tmax", "pk.Tmax"])
            ctx.knowledge_gaps = [
                g for g in ctx.knowledge_gaps if g.get("code") != "MISSING_TMAX_FOR_SAMPLING"
            ]
        elif c.field_path in {"food.calorie_target", "food.fat_target"}:
            meas = c.measurement or {}
            composition = meas.get("value") if isinstance(meas.get("value"), dict) else {}
            calories = composition.get("calories", c.value if c.field_path == "food.calorie_target" else None)
            fat = composition.get("fat", c.value if c.field_path == "food.fat_target" else None)
            if calories is None and fat is None:
                # A meal description alone is not the composition the engine needs
                continue
            if calories is not None:
                ctx.structured_facts["food.calorie_target"] = calories
                ctx.fact_statuses["food.calorie_target"] = "VERIFIED"
                ctx.fact_sources["food.calorie_target"] = "RESEARCH_EVIDENCE"
                applied.append("food.calorie_target")
            if fat is not None:
                ctx.structured_facts["food.fat_target"] = fat
                ctx.fact_statuses["food.fat_target"] = "VERIFIED"
                ctx.fact_sources["food.fat_target"] = "RESEARCH_EVIDENCE"
                applied.append("food.fat_target")
            if composition.get("description"):
                ctx.structured_facts["food.meal_description"] = composition["description"]
            ctx.knowledge_gaps = [
                g for g in ctx.knowledge_gaps if g.get("code") != "MISSING_MEAL_COMPOSITION"
            ]
        elif c.field_path in {"cv_intra", "cvintra", "statistics.cvintra"} and c.cvintra:
            # A dict written by hand has no is_cvintra flag; within-subject is enough
            if str(c.cvintra.get("variability_type") or "") != "WITHIN_SUBJECT":
                continue
            if c.usability == "USABLE_FOR_DECISION" or can_unblock_decision(c, domain="DESIGN"):
                ctx.cvintra = c.cvintra.get("CV_value")
                ctx.structured_facts["cv_intra"] = ctx.cvintra
                ctx.fact_statuses["cv_intra"] = "VERIFIED"
                ctx.fact_sources["cv_intra"] = "RESEARCH_EVIDENCE"
                applied.append("cv_intra")
                ctx.knowledge_gaps = [
                    g for g in ctx.knowledge_gaps if g.get("code") != "MISSING_CVINTRA"
                ]
        elif c.field_path in {
            "product.pharmacology",
            "product.mechanism",
            "product.pharmacological_class",
            "product.chemical_formula",
            "product.molecular_weight",
            "product.inn",
            "product.trade_name",
            "product.contraindications",
            "product.interactions",
            "product.safety_summary",
            "food.effect_summary",
        }:
            # Phase 30 — verified product-specific facts (never from PROPOSED AI alone)
            if c.usability != "USABLE_FOR_DECISION" and c.applicability not in {
                "DIRECT",
                "HIGH",
                "MODERATE",
            }:
                # Still allow VERIFIED + expert-set applicability HIGH/DIRECT via usability
                if not (
                    c.verification_status == "VERIFIED"
                    and c.applicability in {"DIRECT", "HIGH", "MODERATE"}
                ):
                    continue
            if c.value in (None, "", []):
                continue
            fp = str(c.field_path)
            ctx.structured_facts[fp] = c.value
            ctx.fact_statuses[fp] = "VERIFIED"
            ctx.fact_sources[fp] = "VERIFIED_EVIDENCE"
            applied.append(fp)
            # Aggregate flag for contamination FINAL gate — only when all required
            # pharmacology fields are present on context after this apply.
            from app.domain.product_knowledge import PRODUCT_KNOWLEDGE_FIELDS

            needed = [
                f.field_path
                for f in PRODUCT_KNOWLEDGE_FIELDS
                if f.required_for_final_pharmacology
            ]
            if needed and all(
                ctx.structured_facts.get(k) not in (None, "", [], {}) for k in needed
            ):
                ctx.structured_facts["evidence.pharmacology_verified"] = True
                ctx.fact_statuses["evidence.pharmacology_verified"] = "VERIFIED"
                ctx.fact_sources["evidence.pharmacology_verified"] = "VERIFIED_EVIDENCE"
                applied.append("evidence.pharmacology_verified")
                ctx.knowledge_gaps = [
                    g
                    for g in ctx.knowledge_gaps
                    if g.get("code") != "MISSING_PRODUCT_PHARMACOLOGY"
                ]
            if fp in {"product.chemical_formula", "product.molecular_weight"}:
                ctx.knowledge_gaps = [
                    g
                    for g in ctx.knowledge_gaps
                    if g.get("code") != "MISSING_PRODUCT_CHEMISTRY"
                ]
            if fp in {"product.inn", "product.trade_name"}:
                ctx.knowledge_gaps = [
                    g
                    for g in ctx.knowledge_gaps
                    if g.get("code") != "MISSING_PRODUCT_IDENTITY"
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
        if fp in {"pk.t_half", "pk.expected_t_half"}:
            domains.update({"WASHOUT", "SAMPLING"})
        if fp in {"pk.Tmax", "pk.expected_tmax"}:
            domains.add("SAMPLING")
        if fp == "cv_intra":
            domains.add("DESIGN")
        if fp in {"food.calorie_target", "food.fat_target"}:
            domains.add("FOOD")
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
