"""Phase 12A.2 — content foundation service (no Study mutation from proposals)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.content_matrix import list_content_matrix
from app.domain.content_proposals import propose_bioanalysis, propose_safety
from app.domain.content_resolver import ContentResolver
from app.domain.content_renderer import render_resolved
from app.domain.content_validation import validate_resolved_contents
from app.domain.exceptions import NotFoundError, ValidationError
from app.domain.procedure_definition import ProcedureDefinition, validate_procedure_definition
from app.domain.procedure_events import (
    events_from_schedule,
    structural_dependencies,
    validate_schedule_events,
)
from app.domain.procedure_schedule import compose_procedure_schedule
from app.domain.content_foundation_constants import PROCEDURE_CATEGORIES, PROCEDURE_STAGES
from app.models import Project
from app.models.bioanalysis_plan import BioanalysisPlanRecord
from app.models.expert_decision import ExpertDecisionRecord
from app.models.knowledge_gap import KnowledgeGapRecord
from app.models.knowledge_rule import KnowledgeRuleRecord
from app.models.procedure_definition import ProcedureDefinitionRecord
from app.models.procedure_schedule import ProcedureScheduleRecord
from app.models.safety_plan import SafetyPlanRecord
from app.services.provenance import bump_entity_version
from app.services.validation_service import build_project_context


def _get_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", field="project_id")
    return project


def list_procedure_definitions(
    db: Session, *, project_id: UUID | None = None
) -> list[dict[str, Any]]:
    stmt = select(ProcedureDefinitionRecord).order_by(ProcedureDefinitionRecord.sequence_order.asc())
    if project_id is not None:
        stmt = stmt.where(ProcedureDefinitionRecord.project_id == project_id)
    rows = db.execute(stmt).scalars().all()
    return [_proc_out(r) for r in rows]


def create_procedure_definition(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = payload.get("project_id")
    if not project_id:
        raise ValidationError("project_id required", field="project_id")
    _get_project(db, UUID(str(project_id)))
    stage = str(payload.get("stage") or "SCREENING")
    if stage not in PROCEDURE_STAGES:
        raise ValidationError(f"Invalid stage: {stage}", field="stage")
    if payload["category"] not in PROCEDURE_CATEGORIES:
        raise ValidationError(f"Invalid category: {payload['category']}", field="category")
    proc = ProcedureDefinition(
        code=str(payload["code"]),
        name=str(payload["name"]),
        category=str(payload["category"]),
        stage=stage,
        period=payload.get("period"),
        relative_time_min=payload.get("relative_time_min"),
        duration_min=payload.get("duration_min"),
        sequence_order=int(payload.get("sequence_order") or 0),
        mandatory=bool(payload.get("mandatory", True)),
        condition=payload.get("condition"),
        source_ids=list(payload.get("source_ids") or []),
        origin=str(payload.get("origin") or "USER"),
        status=str(payload.get("status") or "PROPOSED"),
        rule_ids=list(payload.get("rule_ids") or payload.get("knowledge_rule_ids") or []),
        notes=payload.get("notes") or payload.get("description"),
    )
    errs = validate_procedure_definition(proc)
    if errs:
        raise ValidationError("; ".join(errs), field="procedure")
    row = ProcedureDefinitionRecord(
        project_id=UUID(str(project_id)),
        code=proc.code,
        name=proc.name,
        category=proc.category,
        stage=proc.stage,
        period=proc.period,
        relative_time_min=proc.relative_time_min,
        duration_min=proc.duration_min,
        sequence_order=proc.sequence_order,
        mandatory=proc.mandatory,
        condition=proc.condition,
        rule_ids=list(proc.rule_ids),
        status=proc.status,
        origin=proc.origin,
        source_ids=list(proc.source_ids),
        notes=proc.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _proc_out(row)


def _proc_out(r: ProcedureDefinitionRecord) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "project_id": str(r.project_id),
        "code": r.code,
        "name": r.name,
        "category": r.category,
        "stage": r.stage,
        "period": r.period,
        "relative_time_min": r.relative_time_min,
        "duration_min": r.duration_min,
        "sequence_order": r.sequence_order,
        "mandatory": r.mandatory,
        "condition": r.condition,
        "rule_ids": list(r.rule_ids or []),
        "status": r.status,
        "origin": r.origin,
        "source_ids": list(r.source_ids or []),
        "entity_version": r.entity_version,
    }


def get_procedure_schedule(db: Session, project_id: UUID) -> dict[str, Any]:
    _get_project(db, project_id)
    ctx = build_project_context(db, project_id)
    schedule = compose_procedure_schedule(ctx)
    events = events_from_schedule(schedule)
    deps = structural_dependencies()
    return {
        **schedule.to_dict(),
        "events": [e.to_dict() for e in events],
        "dependencies": [d.to_dict() for d in deps],
        "persisted": False,
        "note": "Composed from canonical context — proposal/composition does not mutate Study",
    }


def compose_and_optionally_persist_schedule(
    db: Session, project_id: UUID, *, persist: bool = False
) -> dict[str, Any]:
    """Compose schedule. Persist only when explicitly requested — still does not mutate Design/Sampling."""
    project = _get_project(db, project_id)
    result = get_procedure_schedule(db, project_id)
    if not persist:
        return result
    sched = project.procedure_schedule
    if sched is None:
        sched = ProcedureScheduleRecord(project_id=project_id)
        db.add(sched)
        db.flush()
    sched.dependency_trace = list(result.get("dependency_trace") or [])
    sched.composition_notes = result.get("notes")
    sched.status = result.get("status") or "PROPOSED"
    sched.origin = "SOURCE_DERIVED"
    bump_entity_version(sched)
    # Replace procedure definition rows for this schedule (content layer only)
    existing = list(
        db.execute(
            select(ProcedureDefinitionRecord).where(
                ProcedureDefinitionRecord.project_id == project_id
            )
        )
        .scalars()
        .all()
    )
    for row in existing:
        db.delete(row)
    for p in result.get("procedures") or []:
        db.add(
            ProcedureDefinitionRecord(
                project_id=project_id,
                schedule_id=sched.id,
                code=p["code"],
                name=p["name"],
                category=p["category"],
                stage=p["stage"],
                period=p.get("period"),
                relative_time_min=p.get("relative_time_min"),
                duration_min=p.get("duration_min"),
                sequence_order=int(p.get("sequence_order") or 0),
                mandatory=bool(p.get("mandatory", True)),
                condition=p.get("condition"),
                rule_ids=list(p.get("rule_ids") or []),
                status=p.get("status") or "PROPOSED",
                origin=p.get("origin") or "SOURCE_DERIVED",
                source_ids=list(p.get("source_ids") or []),
            )
        )
    db.commit()
    result["persisted"] = True
    result["schedule_id"] = str(sched.id)
    return result


def validate_procedure_schedule(db: Session, project_id: UUID) -> dict[str, Any]:
    data = get_procedure_schedule(db, project_id)
    from app.domain.procedure_events import ProcedureEvent

    events = [ProcedureEvent(**{k: v for k, v in e.items() if k in ProcedureEvent.__dataclass_fields__}) for e in data.get("events") or []]  # type: ignore[attr-defined]
    issues = validate_schedule_events(events)
    return {"project_id": str(project_id), "issues": issues, "status": "OK" if not any(i.get("blocking") for i in issues) else "FAILED"}


def get_bioanalysis(db: Session, project_id: UUID) -> dict[str, Any]:
    _get_project(db, project_id)
    row = db.execute(
        select(BioanalysisPlanRecord).where(BioanalysisPlanRecord.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        return propose_bioanalysis().to_dict() | {"persisted": False}
    return {
        "plan": {
            "matrix": row.matrix,
            "analytical_method": row.analytical_method,
            "lloq": row.lloq,
            "acceptance_criteria": row.acceptance_criteria,
            "status": row.status,
            "field_sources": dict(row.field_sources or {}),
        },
        "persisted": True,
        "requires_expert_confirmation": True,
    }


def propose_bioanalysis_for_project(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    _get_project(db, project_id)
    body = dict(body or {})
    proposal = propose_bioanalysis(
        provided=body.get("plan") or body,
        evidence_claim_ids=body.get("evidence_claim_ids"),
    )
    # Ensure foundation gaps exist (idempotent by question)
    for gap in proposal.knowledge_gaps:
        _ensure_gap(db, project_id, gap)
    db.commit()
    out = proposal.to_dict()
    out["persisted"] = False
    out["mutates_study"] = False
    return out


def validate_bioanalysis(db: Session, project_id: UUID) -> dict[str, Any]:
    prop = propose_bioanalysis_for_project(db, project_id, {})
    issues = []
    if prop["invented_defaults"]:
        issues.append({"code": "CONTENT.PROPOSED_AS_FINAL", "severity": "ERROR", "blocking": True})
    if any("method" in str(g.get("question")).lower() for g in prop.get("knowledge_gaps") or []):
        issues.append(
            {
                "code": "CONTENT.MISSING_SOURCE",
                "severity": "ERROR",
                "blocking": True,
                "message": "Bioanalysis method missing",
            }
        )
    return {"project_id": str(project_id), "issues": issues, "proposal": prop}


def get_safety_plan(db: Session, project_id: UUID) -> dict[str, Any]:
    _get_project(db, project_id)
    row = db.execute(
        select(SafetyPlanRecord).where(SafetyPlanRecord.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        return propose_safety().to_dict() | {"persisted": False}
    return {
        "plan": {
            "vital_signs": row.vital_signs,
            "ECG": row.ECG,
            "AE": row.AE,
            "SAE": row.SAE,
            "status": row.status,
        },
        "persisted": True,
    }


def propose_safety_for_project(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    _get_project(db, project_id)
    proposal = propose_safety(body.get("plan") if body else body)
    for gap in proposal.knowledge_gaps:
        _ensure_gap(db, project_id, gap)
    db.commit()
    out = proposal.to_dict()
    out["persisted"] = False
    out["mutates_study"] = False
    return out


def validate_safety(db: Session, project_id: UUID) -> dict[str, Any]:
    prop = propose_safety_for_project(db, project_id, {})
    return {
        "project_id": str(project_id),
        "issues": [
            {
                "code": "CONTENT.KNOWLEDGE_GAP_OPEN",
                "severity": "WARNING",
                "blocking": False,
                "message": g.get("question"),
            }
            for g in prop.get("knowledge_gaps") or []
        ],
        "proposal": prop,
        "invented_defaults": prop.get("invented_defaults") or [],
    }


def get_content_matrix_for_project(db: Session, project_id: UUID) -> dict[str, Any]:
    _get_project(db, project_id)
    rows = list_content_matrix()
    return {
        "project_id": str(project_id),
        "version": "CONTENT.FOUNDATION.v2",
        "rows": rows,
        "count": len(rows),
    }


def resolve_content(db: Session, project_id: UUID, body: dict[str, Any] | None = None) -> dict[str, Any]:
    _get_project(db, project_id)
    body = dict(body or {})
    ctx = build_project_context(db, project_id)
    # Build a lightweight canonical-like snapshot from validation context
    from app.domain.study_snapshot import build_canonical_snapshot

    try:
        snap = build_canonical_snapshot(ctx)
        snapshot = snap.to_dict() if hasattr(snap, "to_dict") else dict(snap)  # type: ignore[arg-type]
    except Exception:
        snapshot = {
            "design": (ctx.get("design") or {}).get("type"),
            "food": (ctx.get("food") or {}).get("condition"),
            "washout": (ctx.get("washout") or {}).get("selected_value"),
            "randomized_n": (ctx.get("subjects") or {}).get("planned_randomized_n"),
        }
    if body.get("canonical_snapshot"):
        snapshot = {**snapshot, **body["canonical_snapshot"]}

    decisions = [
        {
            "id": str(d.id),
            "decision_type": d.decision_type,
            "status": d.status,
            "proposed_value": d.proposed_value,
            "final_value": d.final_value,
            "decided_at": d.decided_at.isoformat() if d.decided_at else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in db.execute(
            select(ExpertDecisionRecord).where(ExpertDecisionRecord.project_id == project_id)
        )
        .scalars()
        .all()
    ]
    rules = [
        {"rule_code": r.rule_code, "status": r.status, "id": str(r.id)}
        for r in db.execute(select(KnowledgeRuleRecord).where(KnowledgeRuleRecord.project_id.is_(None)))
        .scalars()
        .all()
    ]
    gaps = [
        {
            "id": str(g.id),
            "question": g.question,
            "status": g.status,
            "blocking": g.blocking,
            "importance": g.importance,
        }
        for g in db.execute(
            select(KnowledgeGapRecord).where(KnowledgeGapRecord.project_id == project_id)
        )
        .scalars()
        .all()
    ]
    resolved = ContentResolver().resolve(
        canonical_snapshot=snapshot,
        expert_decisions=decisions,
        knowledge_rules=rules,
        knowledge_gaps=gaps,
        section_codes=body.get("section_codes"),
    )
    rendered = [render_resolved(r) for r in resolved]
    return {
        "project_id": str(project_id),
        "resolved": [r.to_dict() for r in resolved],
        "rendered": rendered,
        "mutates_canonical": False,
        "note": "ContentResolver is read-only — does not write Canonical Study",
    }


def validate_content(db: Session, project_id: UUID, body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = dict(body or {})
    resolved_payload = resolve_content(db, project_id, body)
    from app.domain.content_resolver import ResolvedContent

    resolved_objs: list[ResolvedContent] = []
    for r in resolved_payload["resolved"]:
        known = set(ResolvedContent.__dataclass_fields__)  # type: ignore[attr-defined]
        resolved_objs.append(ResolvedContent(**{k: v for k, v in r.items() if k in known}))
    findings = validate_resolved_contents(
        resolved_objs,
        expert_decisions=body.get("expert_decisions"),
        legacy_template_values=body.get("legacy_template_values"),
        mark_proposed_as_final=bool(body.get("mark_proposed_as_final")),
    )
    return {
        "project_id": str(project_id),
        "findings": [f.to_dict() for f in findings],
        "blocking": any(f.blocking for f in findings),
    }


def _ensure_gap(db: Session, project_id: UUID, gap: dict[str, Any]) -> None:
    q = gap.get("question")
    if not q:
        return
    existing = db.execute(
        select(KnowledgeGapRecord).where(
            KnowledgeGapRecord.project_id == project_id,
            KnowledgeGapRecord.question == q,
        )
    ).scalar_one_or_none()
    if existing:
        return
    db.add(
        KnowledgeGapRecord(
            project_id=project_id,
            domain=str(gap.get("domain") or "QA"),
            question=q,
            importance=str(gap.get("importance") or "MEDIUM"),
            blocking=bool(gap.get("blocking")),
            status="OPEN",
            related_rule_id=gap.get("related_rule_id"),
        )
    )


def generate_core_protocol_content(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Phase 12B.1 — assemble CORE sections only; optional persist via protocol build.

    Does not invent medical values. Does not mutate Study fields.
    """
    from app.domain.content_core_templates import CORE_12B1_SECTION_CODES
    from app.domain.content_generation_qa import run_content_generation_qa
    from app.domain.protocol_assembly import assemble_protocol
    from app.domain.study_snapshot import build_canonical_snapshot
    from app.services import protocol_service as protocol
    from app.services import validation_service as validation

    _get_project(db, project_id)
    body = dict(body or {})
    persist = bool(body.get("persist", True))
    validation_run = validation.run_validation(db, project_id)
    ctx = validation.build_project_context(db, project_id)
    only = set(body.get("section_codes") or CORE_12B1_SECTION_CODES)
    assembled = assemble_protocol(
        ctx,
        blocking_validation=bool(validation_run.summary.blocking),
        validation_issues=[i.model_dump() for i in validation_run.issues],
        only_sections=only,
    )
    snap = build_canonical_snapshot(ctx).to_dict()
    findings = run_content_generation_qa(
        sections=assembled.get("sections") or [],
        canonical=snap,
        mode=str(body.get("mode") or "DRAFT"),
        legacy_hints=body.get("legacy_hints"),
    )
    # Persist gaps from unresolved core blocks
    for s in assembled.get("sections") or []:
        for b in s.get("content_blocks") or []:
            for g in b.get("knowledge_gaps") or []:
                _ensure_gap(db, project_id, g)
    db.commit()

    draft_id = None
    if persist:
        # Full protocol build ensures draft consistency; generators already 12B.1-aware
        draft = protocol.build_protocol(db, project_id)
        draft_id = str(draft.id)

    return {
        "project_id": str(project_id),
        "core_section_codes": sorted(only),
        "sections": assembled.get("sections") or [],
        "tables": assembled.get("tables") or [],
        "qa_findings": [f.to_dict() for f in findings],
        "blocking": any(f.blocking for f in findings),
        "protocol_draft_id": draft_id,
        "mutates_study": False,
        "generator_version": assembled.get("generator_version"),
        "note": "Core content from Canonical/Approved decisions — no template-as-truth",
    }


def generate_sections_5_8_content(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Phase 12B.2 — assemble sections 5–8; optional persist. No medical invention."""
    from app.domain.content_core_templates import CORE_12B2_SECTION_CODES
    from app.domain.content_generation_qa import run_sections_5_8_qa
    from app.domain.protocol_assembly import assemble_protocol
    from app.domain.study_snapshot import build_canonical_snapshot
    from app.services import protocol_service as protocol
    from app.services import validation_service as validation

    _get_project(db, project_id)
    body = dict(body or {})
    persist = bool(body.get("persist", True))
    validation_run = validation.run_validation(db, project_id)
    ctx = validation.build_project_context(db, project_id)
    only = set(body.get("section_codes") or CORE_12B2_SECTION_CODES)
    assembled = assemble_protocol(
        ctx,
        blocking_validation=bool(validation_run.summary.blocking),
        validation_issues=[i.model_dump() for i in validation_run.issues],
        only_sections=only,
    )
    snap = build_canonical_snapshot(ctx).to_dict()
    findings = run_sections_5_8_qa(
        sections=assembled.get("sections") or [],
        canonical=snap,
        ctx=ctx,
        mode=str(body.get("mode") or "DRAFT"),
        legacy_hints=body.get("legacy_hints"),
    )
    for s in assembled.get("sections") or []:
        for b in s.get("content_blocks") or []:
            for g in b.get("knowledge_gaps") or []:
                _ensure_gap(db, project_id, g)
    db.commit()

    draft_id = None
    if persist:
        draft = protocol.build_protocol(db, project_id)
        draft_id = str(draft.id)

    return {
        "project_id": str(project_id),
        "section_codes": sorted(only),
        "sections": assembled.get("sections") or [],
        "tables": assembled.get("tables") or [],
        "qa_findings": [f.to_dict() for f in findings],
        "blocking": any(f.blocking for f in findings),
        "protocol_draft_id": draft_id,
        "mutates_study": False,
        "generator_version": assembled.get("generator_version"),
        "note": "Sections 5–8 from Criteria/ProcedureSchedule/PK/Bioanalysis/SafetyPlan — no medical invention",
    }


def generate_sections_9_15_content(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Phase 12B.3 — assemble sections 9–15; optional persist. No invented stats/admin defaults."""
    from app.domain.content_core_templates import CORE_12B3_SECTION_CODES
    from app.domain.content_generation_qa import run_sections_9_15_qa
    from app.domain.protocol_assembly import assemble_protocol
    from app.domain.study_snapshot import build_canonical_snapshot
    from app.services import protocol_service as protocol
    from app.services import validation_service as validation

    _get_project(db, project_id)
    body = dict(body or {})
    persist = bool(body.get("persist", True))
    validation_run = validation.run_validation(db, project_id)
    ctx = validation.build_project_context(db, project_id)
    only = set(body.get("section_codes") or CORE_12B3_SECTION_CODES)
    assembled = assemble_protocol(
        ctx,
        blocking_validation=bool(validation_run.summary.blocking),
        validation_issues=[i.model_dump() for i in validation_run.issues],
        only_sections=only,
    )
    snap = build_canonical_snapshot(ctx).to_dict()
    findings = run_sections_9_15_qa(
        sections=assembled.get("sections") or [],
        canonical=snap,
        ctx=ctx,
        mode=str(body.get("mode") or "DRAFT"),
        legacy_hints=body.get("legacy_hints"),
    )
    for s in assembled.get("sections") or []:
        for b in s.get("content_blocks") or []:
            for g in b.get("knowledge_gaps") or []:
                _ensure_gap(db, project_id, g)
    db.commit()

    draft_id = None
    if persist:
        draft = protocol.build_protocol(db, project_id)
        draft_id = str(draft.id)

    return {
        "project_id": str(project_id),
        "section_codes": sorted(only),
        "sections": assembled.get("sections") or [],
        "tables": assembled.get("tables") or [],
        "qa_findings": [f.to_dict() for f in findings],
        "blocking": any(f.blocking for f in findings),
        "protocol_draft_id": draft_id,
        "mutates_study": False,
        "generator_version": assembled.get("generator_version"),
        "note": "Sections 9–15 from StatisticalConfig/SubjectPlan/StudyAdministration — no invented defaults",
    }


def generate_sections_16_18_content(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Phase 12B.4 — assemble sections 16–18; optional persist. No invented content."""
    from app.domain.content_core_templates import CORE_12B4_SECTION_CODES
    from app.domain.document_completeness import assess_document_completeness
    from app.domain.full_document_qa import run_full_document_qa
    from app.domain.protocol_assembly import assemble_protocol
    from app.domain.study_snapshot import build_canonical_snapshot
    from app.services import protocol_service as protocol
    from app.services import validation_service as validation

    _get_project(db, project_id)
    body = dict(body or {})
    persist = bool(body.get("persist", True))
    mode = str(body.get("mode") or "DRAFT")
    validation_run = validation.run_validation(db, project_id)
    ctx = validation.build_project_context(db, project_id)
    only = set(body.get("section_codes") or CORE_12B4_SECTION_CODES)
    assembled = assemble_protocol(
        ctx,
        blocking_validation=bool(validation_run.summary.blocking),
        validation_issues=[i.model_dump() for i in validation_run.issues],
        only_sections=only,
    )
    snap = build_canonical_snapshot(ctx).to_dict()
    qa_report = run_full_document_qa(
        assembled=assembled,
        ctx=ctx,
        canonical=snap,
        mode=mode,
        legacy_hints=body.get("legacy_hints"),
    )
    completeness = assess_document_completeness(assembled, qa_report.findings)
    for s in assembled.get("sections") or []:
        for b in s.get("content_blocks") or []:
            for g in b.get("knowledge_gaps") or []:
                _ensure_gap(db, project_id, g)
    db.commit()

    draft_id = None
    if persist:
        draft = protocol.build_protocol(db, project_id)
        draft_id = str(draft.id)

    return {
        "project_id": str(project_id),
        "section_codes": sorted(only),
        "sections": assembled.get("sections") or [],
        "tables": assembled.get("tables") or [],
        "qa_report": qa_report.to_dict(),
        "completeness": completeness.to_dict(),
        "blocking": qa_report.gate == "BLOCKED" or any(f.get("blocking") for f in qa_report.findings),
        "gate": qa_report.gate,
        "protocol_draft_id": draft_id,
        "mutates_study": False,
        "generator_version": assembled.get("generator_version"),
        "note": "Sections 16–18 appendices/conclusion/literature — no invented content",
    }


def generate_full_protocol_content(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Phase 12B.4 — full protocol assemble + full-document QA + completeness.

    Does not mutate Study. Does not force FINAL PASS.
    """
    from app.domain.document_completeness import assess_document_completeness
    from app.domain.full_document_qa import run_full_document_qa
    from app.domain.protocol_assembly import assemble_protocol
    from app.domain.study_snapshot import build_canonical_snapshot
    from app.services import protocol_service as protocol
    from app.services import validation_service as validation

    _get_project(db, project_id)
    body = dict(body or {})
    persist = bool(body.get("persist", False))
    mode = str(body.get("mode") or "DRAFT")
    validation_run = validation.run_validation(db, project_id)
    ctx = validation.build_project_context(db, project_id)
    # Full tree — no only_sections filter
    assembled = assemble_protocol(
        ctx,
        blocking_validation=bool(validation_run.summary.blocking),
        validation_issues=[i.model_dump() for i in validation_run.issues],
    )
    snap = build_canonical_snapshot(ctx).to_dict()
    qa_report = run_full_document_qa(
        assembled=assembled,
        ctx=ctx,
        canonical=snap,
        mode=mode,
        legacy_hints=body.get("legacy_hints"),
    )
    completeness = assess_document_completeness(assembled, qa_report.findings)
    for s in assembled.get("sections") or []:
        for b in s.get("content_blocks") or []:
            for g in b.get("knowledge_gaps") or []:
                _ensure_gap(db, project_id, g)
    db.commit()

    draft_id = None
    if persist:
        draft = protocol.build_protocol(db, project_id)
        draft_id = str(draft.id)

    return {
        "project_id": str(project_id),
        "sections": assembled.get("sections") or [],
        "tables": assembled.get("tables") or [],
        "references": assembled.get("references") or [],
        "build_report": assembled.get("build_report") or {},
        "qa_report": qa_report.to_dict(),
        "completeness": completeness.to_dict(),
        "blocking": qa_report.gate == "BLOCKED" or completeness.readiness == "BLOCKED",
        "gate": qa_report.gate,
        "readiness": completeness.readiness,
        "protocol_draft_id": draft_id,
        "mutates_study": False,
        "generator_version": assembled.get("generator_version"),
        "status": assembled.get("status"),
        "note": "Full document content + QA — FINAL gate not forced",
    }
