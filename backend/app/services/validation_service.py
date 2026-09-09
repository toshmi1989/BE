from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.exceptions import NotFoundError, ValidationError
from app.domain.study_snapshot import build_canonical_snapshot, build_consistency_snapshot
from app.domain.validation_engine import validate_project
from app.domain.validation_graph import change_impact
from app.domain.validation_types import IssueDraft, summarize_issues
from app.models import (
    Project,
    SamplingPlan,
    ValidationIssue,
)
from app.schemas.phase5 import (
    ChangeImpactOut,
    ValidationIssueOut,
    ValidationRunOut,
    ValidationSummaryOut,
)


def _orm_to_dict(obj: Any) -> dict | None:
    if obj is None:
        return None
    data: dict[str, Any] = {}
    for col in obj.__table__.columns:
        data[col.name] = getattr(obj, col.name)
    # provenance-friendly aliases
    if hasattr(obj, "status"):
        data["provenance"] = {
            "status": getattr(obj, "status", None),
            "origin": getattr(obj, "origin", None),
            "source_ids": list(getattr(obj, "source_ids", None) or []),
        }
    return data


def build_project_context(db: Session, project_id: UUID) -> dict:
    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.study),
            selectinload(Project.product),
            selectinload(Project.reference_product),
            selectinload(Project.sources),
            selectinload(Project.design),
            selectinload(Project.food),
            selectinload(Project.eligibility_criteria),
            selectinload(Project.subjects),
            selectinload(Project.analytes),
            selectinload(Project.pk_parameters),
            selectinload(Project.washout),
            selectinload(Project.observation),
            selectinload(Project.sampling).selectinload(SamplingPlan.points),
            selectinload(Project.blood_volume),
            selectinload(Project.cv_studies),
            selectinload(Project.cv_selection),
            selectinload(Project.statistical_config),
            selectinload(Project.sample_size_calculations),
            selectinload(Project.client_input),
            selectinload(Project.sponsor),
            selectinload(Project.organizations),
            selectinload(Project.persons),
            selectinload(Project.study_administration),
            selectinload(Project.safety_plan),
            selectinload(Project.bioanalysis_plan),
            selectinload(Project.knowledge_gaps),
            selectinload(Project.knowledge_rules),
            selectinload(Project.expert_decisions),
            selectinload(Project.research_case),
        )
    )
    project = db.execute(stmt).scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found", field="project_id")

    eligibility = {"inclusion": [], "non_inclusion": [], "exclusion": []}
    for row in project.eligibility_criteria or []:
        eligibility.setdefault(row.category, []).append(
            {"id": str(row.id), "number": row.number, "text": row.text}
        )

    sample_sizes = sorted(
        project.sample_size_calculations or [],
        key=lambda r: r.created_at,
        reverse=True,
    )
    latest_ss = _orm_to_dict(sample_sizes[0]) if sample_sizes else None

    sampling = None
    if project.sampling:
        sampling = _orm_to_dict(project.sampling)
        sampling["points"] = [
            {
                "id": str(p.id),
                "time_h": p.time_h,
                "reason": p.reason,
            }
            for p in (project.sampling.points or [])
        ]
        sampling["total_points_per_period"] = project.sampling.total_points_per_period or len(
            sampling["points"]
        )

    sponsor = _orm_to_dict(project.sponsor)
    if sponsor and not sponsor.get("legal_name"):
        sponsor["legal_name"] = sponsor.get("name")

    organizations = [_orm_to_dict(o) for o in (project.organizations or [])]
    org_by_id = {str(o.get("id")): o for o in organizations if o.get("id")}

    persons: list[dict] = []
    for p in project.persons or []:
        row = _orm_to_dict(p) or {}
        if row.get("organization_id"):
            org = org_by_id.get(str(row["organization_id"]))
            if org and org.get("name"):
                row["organization_name"] = org["name"]
        persons.append(row)

    study_administration = _orm_to_dict(project.study_administration)
    safety_plan = _orm_to_dict(project.safety_plan)
    bioanalysis_plan = _orm_to_dict(project.bioanalysis_plan)

    evidence_claims: list[dict] = []
    case = project.research_case
    if case is not None:
        # Lazy-load evidences/claims when research case present
        from app.models.research import Evidence, EvidenceClaim

        evid_rows = (
            db.execute(select(Evidence).where(Evidence.research_case_id == case.id))
            .scalars()
            .all()
        )
        for ev in evid_rows:
            claims = (
                db.execute(select(EvidenceClaim).where(EvidenceClaim.evidence_id == ev.id))
                .scalars()
                .all()
            )
            for c in claims:
                evidence_claims.append(
                    {
                        "id": str(c.id),
                        "field_name": c.field_name,
                        "value": c.value,
                        "status": c.status,
                        "origin": c.origin,
                        "source_ids": list(c.source_ids or []) or [str(ev.source_id)],
                        "evidence_id": str(ev.id),
                        "evidence_type": ev.evidence_type,
                    }
                )

    sources = []
    for s in project.sources or []:
        sources.append(
            {
                "id": str(s.id),
                "type": s.type,
                "title": s.title,
                "authors": list(s.authors or []),
                "year": s.year,
                "url": s.url,
                "page": s.page,
                "section": s.section,
                "verified": bool(s.verified),
                "access_date": getattr(s, "access_date", None),
            }
        )

    return {
        "project_id": str(project.id),
        "study": _orm_to_dict(project.study),
        "product": _orm_to_dict(project.product),
        "reference_product": _orm_to_dict(project.reference_product),
        "sources": sources,
        "design": _orm_to_dict(project.design),
        "food": _orm_to_dict(project.food),
        "eligibility": eligibility,
        "subjects": _orm_to_dict(project.subjects),
        "analytes": [_orm_to_dict(a) for a in (project.analytes or [])],
        "pk_parameters": [
            {
                **(_orm_to_dict(p) or {}),
                "analyte_id": str(p.analyte_id),
            }
            for p in (project.pk_parameters or [])
        ],
        "washout": _orm_to_dict(project.washout),
        "observation": _orm_to_dict(project.observation),
        "sampling": sampling,
        "blood_volume": _orm_to_dict(project.blood_volume),
        "cv_studies": [
            {
                **(_orm_to_dict(c) or {}),
                "evidence": c.evidence or [],
            }
            for c in (project.cv_studies or [])
        ],
        "cv_selection": _orm_to_dict(project.cv_selection),
        "statistical_config": _orm_to_dict(project.statistical_config),
        "sample_size": latest_ss,
        "sponsor": sponsor,
        "organizations": organizations,
        "persons": persons,
        "study_administration": study_administration,
        "safety_plan": safety_plan,
        "bioanalysis_plan": bioanalysis_plan,
        "knowledge_gaps": [_orm_to_dict(g) for g in (project.knowledge_gaps or [])],
        "knowledge_rules": [_orm_to_dict(r) for r in (project.knowledge_rules or [])],
        "expert_decisions": [_orm_to_dict(d) for d in (project.expert_decisions or [])],
        "evidence_claims": evidence_claims,
        "evidence_summary": {"count": len(evidence_claims)},
    }


def _serialize_issue(row: ValidationIssue) -> ValidationIssueOut:
    return ValidationIssueOut.model_validate(row)


def run_validation(db: Session, project_id: UUID) -> ValidationRunOut:
    ctx = build_project_context(db, project_id)
    drafts: list[IssueDraft] = validate_project(ctx)

    # Preserve non-OPEN human decisions; replace OPEN auto issues
    existing = (
        db.execute(select(ValidationIssue).where(ValidationIssue.project_id == project_id))
        .scalars()
        .all()
    )
    preserved_keys: set[tuple] = set()
    for row in existing:
        if row.status in {"ACKNOWLEDGED", "RESOLVED", "IGNORED"}:
            preserved_keys.add((row.rule_id, row.entity_id, row.field, row.message))
        elif row.status == "OPEN":
            db.delete(row)
    db.flush()

    stored: list[ValidationIssue] = []
    for draft in drafts:
        key = (draft.rule_id, draft.entity_id, draft.field, draft.message)
        if key in preserved_keys:
            continue
        row = ValidationIssue(
            project_id=project_id,
            category=draft.category,
            severity=draft.severity,
            rule_id=draft.rule_id,
            entity_type=draft.entity_type,
            entity_id=draft.entity_id,
            field=draft.field,
            message=draft.message,
            details=draft.details or {},
            source_ids=list(draft.source_ids or []),
            blocking=bool(draft.blocking),
            status="OPEN",
        )
        db.add(row)
        stored.append(row)
    db.commit()

    issues = list_validation_issues(db, project_id)
    summary_raw = summarize_issues(
        [
            {
                "severity": i.severity,
                "blocking": i.blocking,
                "status": i.status,
            }
            for i in issues
        ]
    )
    summary = ValidationSummaryOut(**summary_raw, total=len(issues))
    consistency = build_consistency_snapshot(ctx)
    canonical = build_canonical_snapshot(ctx).to_dict()
    return ValidationRunOut(
        summary=summary,
        issues=issues,
        consistency_snapshot=consistency,
        canonical_snapshot=canonical,
        change_impact_example=change_impact("design"),
    )


def list_validation_issues(db: Session, project_id: UUID) -> list[ValidationIssueOut]:
    if db.get(Project, project_id) is None:
        raise NotFoundError("Project not found", field="project_id")
    rows = (
        db.execute(
            select(ValidationIssue)
            .where(ValidationIssue.project_id == project_id)
            .order_by(ValidationIssue.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [_serialize_issue(r) for r in rows]


def validation_summary(db: Session, project_id: UUID) -> ValidationSummaryOut:
    issues = list_validation_issues(db, project_id)
    raw = summarize_issues(
        [{"severity": i.severity, "blocking": i.blocking, "status": i.status} for i in issues]
    )
    return ValidationSummaryOut(**raw, total=len(issues))


def _set_issue_status(db: Session, project_id: UUID, issue_id: UUID, status: str) -> ValidationIssueOut:
    row = db.get(ValidationIssue, issue_id)
    if row is None or row.project_id != project_id:
        raise NotFoundError("Validation issue not found", field="issue_id")
    if status not in {"ACKNOWLEDGED", "RESOLVED", "IGNORED", "OPEN"}:
        raise ValidationError(f"Invalid issue status: {status}", field="status")
    row.status = status
    db.commit()
    db.refresh(row)
    return _serialize_issue(row)


def acknowledge_issue(db: Session, project_id: UUID, issue_id: UUID) -> ValidationIssueOut:
    return _set_issue_status(db, project_id, issue_id, "ACKNOWLEDGED")


def resolve_issue(db: Session, project_id: UUID, issue_id: UUID) -> ValidationIssueOut:
    return _set_issue_status(db, project_id, issue_id, "RESOLVED")


def get_change_impact(changed_entity: str) -> ChangeImpactOut:
    return ChangeImpactOut(**change_impact(changed_entity))


def get_snapshots(db: Session, project_id: UUID) -> dict:
    ctx = build_project_context(db, project_id)
    return {
        "consistency": build_consistency_snapshot(ctx),
        "canonical": build_canonical_snapshot(ctx).to_dict(),
        "fingerprint": build_canonical_snapshot(ctx).fingerprint(),
    }
