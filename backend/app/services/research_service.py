from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.evidence_apply import EvidenceClaimData, apply_verified_evidence_claims
from app.domain.exceptions import NotFoundError, ProvenanceGuardError, ValidationError
from app.domain.source_ranking import ranking_as_dict
from app.models import Analyte, Project, SourceRankingConfig
from app.models.research import (
    Evidence,
    EvidenceClaim,
    EvidenceConflict,
    ResearchCase,
    ResearchTask,
)
from app.schemas.common import ProvenanceIn
from app.schemas.phase5 import (
    ApplyVerifiedOut,
    ApplyVerifiedRequest,
    EvidenceConflictCreate,
    EvidenceConflictOut,
    EvidenceConflictResolve,
    EvidenceCreate,
    EvidenceOut,
    EvidenceClaimOut,
    ResearchCaseCreate,
    ResearchCaseOut,
    ResearchTaskCreate,
    ResearchTaskOut,
)
from app.services.provenance import apply_provenance, bump_entity_version


TASK_TYPES = {
    "REFERENCE_PRODUCT",
    "REGISTRATION",
    "PRODUCT_LABEL",
    "PRODUCT_SPECIFIC_GUIDELINE",
    "PK",
    "ANALYTES",
    "BIOEQUIVALENCE_STUDIES",
    "CV",
    "SAFETY",
    "FOOD_CONDITION",
    "OTHER",
}
EVIDENCE_TYPES = {
    "REFERENCE",
    "PK",
    "DESIGN",
    "FOOD",
    "ANALYTE",
    "CV",
    "SAFETY",
    "REGISTRATION",
    "OTHER",
}


def _get_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", field="project_id")
    return project


def ensure_research_case(
    db: Session, project_id: UUID, payload: ResearchCaseCreate | None = None
) -> ResearchCaseOut:
    _get_project(db, project_id)
    row = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        row = ResearchCase(
            project_id=project_id,
            status=(payload.status if payload else "NEW"),
            client_input_id=payload.client_input_id if payload else None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return ResearchCaseOut.model_validate(row)


def get_research_case(db: Session, project_id: UUID) -> ResearchCaseOut:
    _get_project(db, project_id)
    row = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Research case not found", field="research_case")
    return ResearchCaseOut.model_validate(row)


def _case(db: Session, project_id: UUID) -> ResearchCase:
    row = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Research case not found — create one first", field="research_case")
    return row


def create_task(db: Session, project_id: UUID, payload: ResearchTaskCreate) -> ResearchTaskOut:
    case = _case(db, project_id)
    if payload.task_type not in TASK_TYPES:
        raise ValidationError(f"Unsupported task_type: {payload.task_type}", field="task_type")
    row = ResearchTask(
        research_case_id=case.id,
        task_type=payload.task_type,
        query_profile=payload.query_profile or {},
        status=payload.status,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        notes=payload.notes,
        depends_on_tasks=list(getattr(payload, "depends_on_tasks", None) or []),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ResearchTaskOut.model_validate(row)


def list_tasks(db: Session, project_id: UUID) -> list[ResearchTaskOut]:
    case = _case(db, project_id)
    rows = (
        db.execute(select(ResearchTask).where(ResearchTask.research_case_id == case.id))
        .scalars()
        .all()
    )
    return [ResearchTaskOut.model_validate(r) for r in rows]


def create_evidence(db: Session, project_id: UUID, payload: EvidenceCreate) -> EvidenceOut:
    case = _case(db, project_id)
    if payload.evidence_type not in EVIDENCE_TYPES:
        raise ValidationError(
            f"Unsupported evidence_type: {payload.evidence_type}", field="evidence_type"
        )
    row = Evidence(
        research_case_id=case.id,
        source_id=payload.source_id,
        evidence_type=payload.evidence_type,
        claim=payload.claim,
        extracted_text=payload.extracted_text,
        page=str(payload.page) if payload.page is not None else None,
        section=payload.section,
        confidence=payload.confidence,
        verification_status=payload.verification_status,
    )
    db.add(row)
    db.flush()
    for c in payload.claims:
        claim = EvidenceClaim(
            evidence_id=row.id,
            field_name=c.field_name,
            value=c.value,
            normalized_value=c.normalized_value,
            unit=c.unit,
            confidence=c.confidence,
            status=c.status,
            origin=c.origin,
            source_ids=list(c.source_ids or [payload.source_id]),
        )
        db.add(claim)
    db.commit()
    row = db.execute(
        select(Evidence)
        .where(Evidence.id == row.id)
        .options(selectinload(Evidence.claims))
    ).scalar_one()
    return _serialize_evidence(row)


def _serialize_evidence(row: Evidence) -> EvidenceOut:
    return EvidenceOut(
        id=row.id,
        research_case_id=row.research_case_id,
        source_id=row.source_id,
        evidence_type=row.evidence_type,
        claim=row.claim,
        extracted_text=row.extracted_text,
        page=row.page,
        section=row.section,
        confidence=row.confidence,
        verification_status=row.verification_status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        claims=[EvidenceClaimOut.model_validate(c) for c in (row.claims or [])],
    )


def list_evidence(db: Session, project_id: UUID) -> list[EvidenceOut]:
    case = _case(db, project_id)
    rows = (
        db.execute(
            select(Evidence)
            .where(Evidence.research_case_id == case.id)
            .options(selectinload(Evidence.claims))
        )
        .scalars()
        .all()
    )
    return [_serialize_evidence(r) for r in rows]


def create_conflict(
    db: Session, project_id: UUID, payload: EvidenceConflictCreate
) -> EvidenceConflictOut:
    case = _case(db, project_id)
    row = EvidenceConflict(
        research_case_id=case.id,
        field_name=payload.field_name,
        evidence_ids=list(payload.evidence_ids),
        values=list(payload.values),
        severity=payload.severity,
        resolution=payload.resolution,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return EvidenceConflictOut.model_validate(row)


def list_conflicts(db: Session, project_id: UUID) -> list[EvidenceConflictOut]:
    case = _case(db, project_id)
    rows = (
        db.execute(select(EvidenceConflict).where(EvidenceConflict.research_case_id == case.id))
        .scalars()
        .all()
    )
    return [EvidenceConflictOut.model_validate(r) for r in rows]


def resolve_conflict(
    db: Session, project_id: UUID, conflict_id: UUID, payload: EvidenceConflictResolve
) -> EvidenceConflictOut:
    case = _case(db, project_id)
    row = db.get(EvidenceConflict, conflict_id)
    if row is None or row.research_case_id != case.id:
        raise NotFoundError("Conflict not found", field="conflict_id")
    row.resolution = payload.resolution
    row.resolved_by = payload.resolved_by
    row.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return EvidenceConflictOut.model_validate(row)


def apply_verified(db: Session, project_id: UUID, payload: ApplyVerifiedRequest) -> ApplyVerifiedOut:
    _get_project(db, project_id)
    claims_orm: list[EvidenceClaim] = []
    for cid in payload.claim_ids:
        claim = db.get(EvidenceClaim, cid)
        if claim is None:
            raise NotFoundError("Claim not found", field="claim_ids")
        # ensure belongs to project research case
        evidence = db.get(Evidence, claim.evidence_id)
        case = db.get(ResearchCase, evidence.research_case_id) if evidence else None
        if case is None or case.project_id != project_id:
            raise NotFoundError("Claim not in project research case", field="claim_ids")
        claims_orm.append(claim)

    analyte: Analyte | None = None
    if payload.analyte_id:
        analyte = db.get(Analyte, payload.analyte_id)
        if analyte is None or analyte.project_id != project_id:
            raise NotFoundError("Analyte not found", field="analyte_id")
    else:
        analyte = (
            db.execute(select(Analyte).where(Analyte.project_id == project_id)).scalars().first()
        )
    if analyte is None:
        raise ValidationError("Analyte required to apply PK claims", field="analyte_id")

    target_status = analyte.status

    def mutate(claim_data: EvidenceClaimData) -> None:
        if claim_data.status != "VERIFIED":
            raise ProvenanceGuardError("Only VERIFIED claims can update study")
        if target_status == "VERIFIED" and claim_data.status != "VERIFIED":
            raise ProvenanceGuardError("Cannot overwrite VERIFIED analyte with non-verified claim")
        # Proposed claims never reach here via apply_verified_evidence_claims filter,
        # but double-guard if somehow called:
        if claim_data.status != "VERIFIED":
            raise ProvenanceGuardError("PROPOSED claim cannot update study")

        nv = claim_data.normalized_value or {}
        fname = claim_data.field_name
        if fname in {"tmax", "tmax_min", "tmax_max"} or fname.startswith("tmax"):
            if "min" in nv:
                analyte.tmax_min = float(nv["min"])
            if "max" in nv:
                analyte.tmax_max = float(nv["max"])
            if claim_data.unit:
                analyte.tmax_unit = claim_data.unit
            if fname == "tmax_min" and claim_data.value and "min" not in nv:
                analyte.tmax_min = float(nv.get("min") or claim_data.value)
        elif fname.startswith("half_life"):
            if "min" in nv:
                analyte.half_life_min = float(nv["min"])
            if "max" in nv:
                analyte.half_life_max = float(nv["max"])
            if claim_data.unit:
                analyte.half_life_unit = claim_data.unit
        else:
            raise ValidationError(f"Unsupported claim field: {fname}", field="field_name")

        apply_provenance(
            analyte,
            ProvenanceIn(
                origin="SOURCE_DERIVED",
                status="PROPOSED",
                source_ids=claim_data.source_ids,
                notes=f"Applied from evidence claim {claim_data.id}",
            ),
        )
        bump_entity_version(analyte)

    claim_data = [
        EvidenceClaimData(
            id=str(c.id),
            field_name=c.field_name,
            value=c.value,
            normalized_value=c.normalized_value,
            unit=c.unit,
            confidence=c.confidence,
            status=c.status,
            origin=c.origin,
            source_ids=list(c.source_ids or []),
        )
        for c in claims_orm
    ]
    # Extra rule: PROPOSED must not update VERIFIED study
    for c in claim_data:
        if c.status != "VERIFIED" and target_status == "VERIFIED":
            raise ProvenanceGuardError(
                "PROPOSED EvidenceClaim cannot update VERIFIED study field"
            )
        if c.status != "VERIFIED":
            # skip via engine; also enforce hard error if all are proposed and user expected apply
            pass

    result = apply_verified_evidence_claims(
        claims=claim_data,
        target_status=target_status,
        mutate=mutate,
    )
    db.commit()
    return ApplyVerifiedOut(
        applied=result.applied, skipped=result.skipped, warnings=result.warnings
    )


def get_or_seed_source_ranking(db: Session) -> dict:
    row = db.execute(
        select(SourceRankingConfig).where(SourceRankingConfig.active.is_(True))
    ).scalar_one_or_none()
    if row is None:
        data = ranking_as_dict()
        row = SourceRankingConfig(version=data["version"], rules=data["rules"], active=True)
        db.add(row)
        db.commit()
        db.refresh(row)
    return {"version": row.version, "rules": row.rules, "active": row.active}
