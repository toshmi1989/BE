"""Deterministic research query generation — Phase 15.2. AI optional only."""

from __future__ import annotations

from typing import Any

from app.domain.research_evidence_classes import GAP_TO_TASK
from app.domain.research_evidence_models import ResearchQuery, ResearchTask


def build_query_text(
    task_type: str,
    *,
    active_substance: str | None = None,
    dosage_form: str | None = None,
    dose: str | None = None,
    extra: str | None = None,
) -> str:
    inn = (active_substance or "active substance").strip()
    form = (dosage_form or "").strip()
    dose_s = (dose or "").strip()
    templates = {
        "FIND_HALF_LIFE_PK": f"{inn} pharmacokinetics half-life healthy volunteers",
        "FIND_TMAX_PK": f"{inn} Tmax healthy volunteers {form or 'extended release'}".strip(),
        "FIND_CVINTRA_LITERATURE": (
            f"{inn} within-subject variability Cmax AUC bioequivalence"
        ),
        "FIND_MEAL_COMPOSITION": f"{inn} high-calorie breakfast meal composition fed bioequivalence",
        "FIND_SMPC_REFERENCE_PRODUCT": f"{inn} SmPC product information {dose_s}".strip(),
        "FIND_ANALOGUE_STUDY": f"{inn} bioequivalence crossover healthy volunteers",
        "FIND_REGULATORY_EVIDENCE": f"{inn} bioequivalence guideline",
        "OTHER": f"{inn} pharmacokinetics",
    }
    base = templates.get(task_type, templates["OTHER"])
    if extra:
        base = f"{base} {extra}"
    return " ".join(base.split())


def generate_research_query(
    task: ResearchTask,
    *,
    context: dict[str, Any] | None = None,
    created_by: str = "DETERMINISTIC",
) -> ResearchQuery:
    ctx = context or {}
    meta = GAP_TO_TASK.get(task.knowledge_gap_code or "", {})
    qtype = meta.get("query_type") or _query_type_for_task(task.task_type)
    text = task.query or build_query_text(
        task.task_type,
        active_substance=ctx.get("active_substance") or ctx.get("analyte"),
        dosage_form=ctx.get("dosage_form"),
        dose=ctx.get("dose"),
    )
    return ResearchQuery(
        research_task_id=task.id,
        query_text=text,
        query_type=qtype,
        created_by=created_by,
        study_id=task.study_id,
        ai_proposed=created_by.upper() in {"AI", "MOCKAI"},
    )


def ai_propose_alternative_query(
    task: ResearchTask,
    *,
    alternative_text: str,
) -> ResearchQuery:
    """AI may propose alternatives — remains auditable, never auto-run as sole query."""
    if not alternative_text.strip():
        raise ValueError("alternative_text required")
    meta = GAP_TO_TASK.get(task.knowledge_gap_code or "", {})
    return ResearchQuery(
        research_task_id=task.id,
        query_text=alternative_text.strip(),
        query_type=meta.get("query_type") or _query_type_for_task(task.task_type),
        created_by="AI",
        study_id=task.study_id,
        ai_proposed=True,
    )


def _query_type_for_task(task_type: str) -> str:
    return {
        "FIND_HALF_LIFE_PK": "PK",
        "FIND_TMAX_PK": "PK",
        "FIND_CVINTRA_LITERATURE": "CV",
        "FIND_MEAL_COMPOSITION": "FOOD",
        "FIND_SMPC_REFERENCE_PRODUCT": "IDENTITY",
        "FIND_ANALOGUE_STUDY": "ANALOGUE",
        "FIND_REGULATORY_EVIDENCE": "REGULATORY",
    }.get(task_type, "OTHER")
