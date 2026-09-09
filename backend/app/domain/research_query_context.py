"""Conflict-aware query context — Phase 15.3.

Do not inject unresolved conflict values (e.g. dose 15 vs 30) into queries.
"""

from __future__ import annotations

from typing import Any

from app.domain.research_query_gen import build_query_text, generate_research_query
from app.domain.research_evidence_models import ResearchQuery, ResearchTask


CRITICAL_CONFLICT_FIELDS = frozenset(
    {
        "reference_product.dose",
        "reference_product.name",
        "test_product.dose",
    }
)


def build_safe_query_context(
    *,
    structured_facts: dict[str, Any] | None = None,
    open_conflicts: list[dict[str, Any]] | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    facts = dict(structured_facts or {})
    extras = dict(extras or {})
    conflict_fields = {
        str(c.get("field_path"))
        for c in (open_conflicts or [])
        if str(c.get("status") or "OPEN") == "OPEN"
    }
    ctx: dict[str, Any] = {}
    # Prefer extras for identity when not conflicting
    for key, fact_path in (
        ("active_substance", "test_product.active_substance"),
        ("analyte", "bioanalysis.analyte"),
        ("dosage_form", "test_product.dosage_form"),
        ("product", "reference_product.name"),
        ("dose", "reference_product.dose"),
        ("population", "subjects.population"),
        ("condition", "design.conditions"),
    ):
        if fact_path in conflict_fields or key in {"dose"} and "reference_product.dose" in conflict_fields:
            continue
        val = extras.get(key) or facts.get(fact_path)
        if val is not None and val != "":
            ctx[key] = val
    # Active substance often known even when dose conflicts
    if "active_substance" not in ctx:
        for path in ("test_product.active_substance", "reference_product.active_substance", "bioanalysis.analyte"):
            if path not in conflict_fields and facts.get(path):
                ctx["active_substance"] = facts[path]
                break
        if "active_substance" not in ctx and extras.get("active_substance"):
            ctx["active_substance"] = extras["active_substance"]
    if "reference_product.dose" in conflict_fields:
        ctx["unresolved_context"] = "reference_product.dose conflict — dose omitted from query"
    return ctx


def generate_contextual_query(
    task: ResearchTask,
    *,
    structured_facts: dict[str, Any] | None = None,
    open_conflicts: list[dict[str, Any]] | None = None,
    extras: dict[str, Any] | None = None,
) -> ResearchQuery:
    ctx = build_safe_query_context(
        structured_facts=structured_facts,
        open_conflicts=open_conflicts,
        extras=extras,
    )
    # Broader query when dose conflicted
    extra = None
    if ctx.get("unresolved_context"):
        extra = "pharmacokinetics"  # broaden, no invented dose
    text = build_query_text(
        task.task_type,
        active_substance=ctx.get("active_substance") or ctx.get("analyte"),
        dosage_form=ctx.get("dosage_form"),
        dose=ctx.get("dose"),  # only if not conflicted
        extra=extra,
    )
    # SmPC-specific multi-query hint stored in task notes elsewhere
    if task.task_type == "FIND_SMPC_REFERENCE_PRODUCT":
        product = ctx.get("product") or ctx.get("active_substance") or "reference product"
        text = f"{product} SmPC prescribing information"
    q = generate_research_query(task, context=ctx)
    q.query_text = text
    return q


def smpc_query_variants(product: str | None, active_substance: str | None = None) -> list[str]:
    name = (product or active_substance or "reference product").strip()
    return [
        f"{name} SmPC",
        f"{name} instruction",
        f"{name} prescribing information",
    ]
