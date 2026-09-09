from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.conflict_engine import ClaimSnippet, detect_conflicts
from app.domain.evidence_fields import EVIDENCE_FIELD_DEFINITIONS, field_by_code, fields_as_list
from app.domain.evidence_normalize import normalize_claim_value
from app.domain.exceptions import NotFoundError, ValidationError
from app.domain.research_completeness import calculate_research_completeness
from app.domain.research_profile import ClientResearchInput, build_search_profile
from app.domain.research_tasks import generate_research_tasks
from app.models import ClientInput, Project
from app.models.documents import EvidenceFieldDefinitionRow, ResearchProfile
from app.models.research import Evidence, EvidenceClaim, EvidenceConflict, ResearchCase, ResearchTask
from app.schemas.phase5 import EvidenceConflictOut, EvidenceOut, ResearchTaskOut
from app.schemas.phase6 import (
    CompletenessOut,
    ManualEvidenceRequest,
    ResearchProfileIn,
    ResearchProfileOut,
)
from app.services import research_service as foundation
from app.services.research_service import _serialize_evidence


def _project(db: Session, project_id: UUID) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise NotFoundError("Project not found", field="project_id")
    return p


def upsert_research_profile(
    db: Session, project_id: UUID, payload: ResearchProfileIn
) -> ResearchProfileOut:
    project = _project(db, project_id)
    data = payload.model_dump()
    if payload.sync_from_client_input and project.client_input is None:
        # load client input if relationship not loaded
        ci = db.execute(
            select(ClientInput).where(ClientInput.project_id == project_id)
        ).scalar_one_or_none()
    else:
        ci = project.client_input
    if payload.sync_from_client_input and ci is not None:
        data["requested_product_name"] = data["requested_product_name"] or ci.requested_product_name
        data["inn"] = data["inn"] or ci.inn
        data["dosage"] = data["dosage"] or ci.dosage
        data["dosage_form"] = data["dosage_form"] or ci.dosage_form
        data["route"] = data["route"] or ci.route
        data["requested_subject_count"] = (
            data["requested_subject_count"]
            if data["requested_subject_count"] is not None
            else ci.requested_subject_count
        )

    search = build_search_profile(
        ClientResearchInput(
            requested_product_name=data.get("requested_product_name"),
            inn=data.get("inn"),
            dosage=data.get("dosage"),
            dosage_form=data.get("dosage_form"),
            route=data.get("route"),
            requested_subject_count=data.get("requested_subject_count"),
            country=data.get("country"),
            regulatory_jurisdiction=data.get("regulatory_jurisdiction"),
        )
    )

    row = db.execute(
        select(ResearchProfile).where(ResearchProfile.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        row = ResearchProfile(project_id=project_id)
        db.add(row)
    row.requested_product_name = data.get("requested_product_name")
    row.inn = data.get("inn")
    row.dosage = data.get("dosage")
    row.dosage_form = data.get("dosage_form")
    row.route = data.get("route")
    row.requested_subject_count = data.get("requested_subject_count")
    row.country = data.get("country")
    row.regulatory_jurisdiction = data.get("regulatory_jurisdiction")
    row.search_profile = search.to_dict()
    row.version = search.version
    db.commit()
    db.refresh(row)
    return ResearchProfileOut.model_validate(row)


def get_research_profile(db: Session, project_id: UUID) -> ResearchProfileOut:
    _project(db, project_id)
    row = db.execute(
        select(ResearchProfile).where(ResearchProfile.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Research profile not found", field="research_profile")
    return ResearchProfileOut.model_validate(row)


def generate_tasks_for_project(db: Session, project_id: UUID) -> list[ResearchTaskOut]:
    foundation.ensure_research_case(db, project_id)
    profile = db.execute(
        select(ResearchProfile).where(ResearchProfile.project_id == project_id)
    ).scalar_one_or_none()
    if profile is None:
        # auto-build from client input
        upsert_research_profile(db, project_id, ResearchProfileIn())
        profile = db.execute(
            select(ResearchProfile).where(ResearchProfile.project_id == project_id)
        ).scalar_one()

    search = build_search_profile(
        ClientResearchInput(
            requested_product_name=profile.requested_product_name,
            inn=profile.inn,
            dosage=profile.dosage,
            dosage_form=profile.dosage_form,
            route=profile.route,
            requested_subject_count=profile.requested_subject_count,
            country=profile.country,
            regulatory_jurisdiction=profile.regulatory_jurisdiction,
        )
    )
    drafts = generate_research_tasks(search)
    case = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one()

    # replace TODO/BLOCKED generated tasks of same types (keep DONE)
    existing = (
        db.execute(select(ResearchTask).where(ResearchTask.research_case_id == case.id))
        .scalars()
        .all()
    )
    done_types = {t.task_type for t in existing if t.status == "DONE"}
    for t in existing:
        if t.status != "DONE":
            db.delete(t)
    db.flush()

    created: list[ResearchTask] = []
    for d in drafts:
        if d.task_type in done_types:
            continue
        row = ResearchTask(
            research_case_id=case.id,
            task_type=d.task_type,
            query_profile=d.query_profile,
            status=d.status,
            priority=d.priority,
            notes=d.notes,
            depends_on_tasks=list(d.depends_on_tasks),
            result_count=0,
        )
        db.add(row)
        created.append(row)

    if case.status == "NEW":
        case.status = "RESEARCHING"
    db.commit()
    return foundation.list_tasks(db, project_id)


def seed_evidence_field_definitions(db: Session) -> list[dict]:
    existing = {
        r.code
        for r in db.execute(select(EvidenceFieldDefinitionRow)).scalars().all()
    }
    for d in EVIDENCE_FIELD_DEFINITIONS:
        if d.code in existing:
            continue
        db.add(
            EvidenceFieldDefinitionRow(
                code=d.code,
                expected_type=d.expected_type,
                unit=d.unit,
                target_entity=d.target_entity,
                target_field=d.target_field,
                evidence_type=d.evidence_type,
                description=d.description,
                active=True,
            )
        )
    db.commit()
    return fields_as_list()


def create_manual_evidence(db: Session, project_id: UUID, payload: ManualEvidenceRequest) -> EvidenceOut:
    foundation.ensure_research_case(db, project_id)
    seed_evidence_field_definitions(db)
    definition = field_by_code(payload.field_code)
    if definition is None:
        raise ValidationError(f"Unknown field_code: {payload.field_code}", field="field_code")

    normalized = normalize_claim_value(payload.field_code, payload.extracted_text)
    evidence_type = payload.evidence_type or definition.evidence_type

    from app.schemas.phase5 import EvidenceClaimIn, EvidenceCreate

    created = foundation.create_evidence(
        db,
        project_id,
        EvidenceCreate(
            source_id=payload.source_id,
            evidence_type=evidence_type,
            claim=f"{payload.field_code}: {payload.extracted_text}",
            extracted_text=payload.extracted_text,
            page=payload.page,
            section=payload.section,
            confidence=None,
            verification_status="PROPOSED",
            claims=[
                EvidenceClaimIn(
                    field_name=payload.field_code,
                    value=payload.extracted_text,
                    normalized_value=normalized.normalized,
                    unit=normalized.unit or definition.unit,
                    status="PROPOSED",
                    origin="USER",
                    source_ids=[payload.source_id],
                )
            ],
        ),
    )

    if payload.auto_detect_conflicts:
        refresh_conflicts(db, project_id)

    _maybe_ready_for_review(db, project_id)
    return created


def refresh_conflicts(db: Session, project_id: UUID) -> list[EvidenceConflictOut]:
    case = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one_or_none()
    if case is None:
        raise NotFoundError("Research case not found", field="research_case")

    claims = (
        db.execute(
            select(EvidenceClaim, Evidence)
            .join(Evidence, EvidenceClaim.evidence_id == Evidence.id)
            .where(Evidence.research_case_id == case.id)
        )
        .all()
    )
    snippets = [
        ClaimSnippet(
            evidence_id=str(ev.id),
            claim_id=str(cl.id),
            field_name=cl.field_name,
            value=cl.value,
            normalized_value=cl.normalized_value,
            status=cl.status,
        )
        for cl, ev in claims
    ]
    drafts = detect_conflicts(snippets)

    # remove unresolved auto conflicts and recreate (keep resolved)
    existing = (
        db.execute(select(EvidenceConflict).where(EvidenceConflict.research_case_id == case.id))
        .scalars()
        .all()
    )
    for row in existing:
        if row.resolved_at is None:
            db.delete(row)
    db.flush()

    for d in drafts:
        db.add(
            EvidenceConflict(
                research_case_id=case.id,
                field_name=d.field_name,
                evidence_ids=d.evidence_ids,
                values=d.values,
                severity=d.severity,
            )
        )
    db.commit()
    return foundation.list_conflicts(db, project_id)


def research_completeness(db: Session, project_id: UUID) -> CompletenessOut:
    foundation.ensure_research_case(db, project_id)
    case = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one()
    tasks = foundation.list_tasks(db, project_id)
    evidences = foundation.list_evidence(db, project_id)
    field_codes: list[str] = []
    for ev in evidences:
        for c in ev.claims:
            field_codes.append(c.field_name)
    conflicts = foundation.list_conflicts(db, project_id)
    unresolved = sum(1 for c in conflicts if c.resolved_at is None)
    result = calculate_research_completeness(
        tasks=[t.model_dump() for t in tasks],
        evidence_field_codes=field_codes,
        unresolved_conflicts=unresolved,
    )
    status = _maybe_ready_for_review(db, project_id)
    out = CompletenessOut(**result.to_dict(), research_case_status=status or case.status)
    return out


def _maybe_ready_for_review(db: Session, project_id: UUID) -> str | None:
    case = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one_or_none()
    if case is None:
        return None
    tasks = (
        db.execute(select(ResearchTask).where(ResearchTask.research_case_id == case.id))
        .scalars()
        .all()
    )
    required = {"REFERENCE_PRODUCT", "PRODUCT_LABEL", "PK"}
    by_type = {t.task_type: t for t in tasks}
    # ready if required tasks exist and each has result_count>0 or DONE, and some evidence
    evidences = (
        db.execute(select(Evidence).where(Evidence.research_case_id == case.id)).scalars().all()
    )
    ok = True
    for ttype in required:
        t = by_type.get(ttype)
        if t is None:
            ok = False
            break
        if t.status not in {"DONE", "NEEDS_REVIEW"} and t.result_count <= 0 and not evidences:
            ok = False
            break
    if ok and evidences and case.status in {"NEW", "RESEARCHING"}:
        case.status = "READY_FOR_REVIEW"
        db.commit()
    return case.status


def mark_task_has_results(db: Session, project_id: UUID, task_type: str, count: int = 1) -> None:
    case = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one_or_none()
    if case is None:
        return
    task = db.execute(
        select(ResearchTask).where(
            ResearchTask.research_case_id == case.id, ResearchTask.task_type == task_type
        )
    ).scalar_one_or_none()
    if task is None:
        return
    task.result_count = max(task.result_count, count)
    if task.status == "TODO":
        task.status = "IN_PROGRESS"
    db.commit()
