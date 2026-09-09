"""Phase 28 — Canonical WorkspaceStudy create / list / catalog sync."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domain.workspace_documents import list_study_documents
from app.models.auth import Organization, WorkspaceStudy

DEV_ORG_SLUG = "local-dev"
RESERVED_DEMO_KEYS = {"UPDCB-02-BE-2026"}


def get_or_create_dev_organization(db: Session) -> Organization:
    org = db.execute(
        select(Organization).where(Organization.slug == DEV_ORG_SLUG)
    ).scalar_one_or_none()
    if org:
        return org
    org = Organization(name="Local Development", slug=DEV_ORG_SLUG, status="ACTIVE")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def create_canonical_study(
    db: Session,
    *,
    organization_id: UUID,
    created_by_user_id: UUID | None,
    study_key: str | None = None,
    title: str | None = None,
    sponsor: str | None = None,
    product: str | None = None,
    dose: str | None = None,
    is_demo: bool = False,
) -> WorkspaceStudy:
    key = (study_key or f"STUDY-{uuid4().hex[:10]}").strip()
    if not key:
        raise HTTPException(status_code=400, detail={"message": "study_key required", "field": "study_key"})
    if key in RESERVED_DEMO_KEYS and not is_demo:
        raise HTTPException(
            status_code=400,
            detail={"message": "Reserved demo study key", "field": "study_key"},
        )
    existing = db.execute(
        select(WorkspaceStudy).where(WorkspaceStudy.study_key == key)
    ).scalar_one_or_none()
    if existing:
        if existing.organization_id != organization_id:
            raise HTTPException(status_code=409, detail={"message": "study_key already exists", "field": "study_key"})
        # Merge null metadata on retry
        changed = False
        if title and not existing.title:
            existing.title = title
            changed = True
        if sponsor and not existing.sponsor:
            existing.sponsor = sponsor
            changed = True
        if product and not existing.product:
            existing.product = product
            changed = True
        if dose and not existing.dose:
            existing.dose = dose
            changed = True
        if changed:
            db.commit()
            db.refresh(existing)
        return existing
    row = WorkspaceStudy(
        organization_id=organization_id,
        study_key=key,
        title=title,
        sponsor=sponsor,
        product=product,
        dose=dose,
        lifecycle="DRAFT",
        readiness_code="NOT_STARTED",
        readiness_label="Not started",
        document_count=0,
        created_by_user_id=created_by_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def study_to_catalog_dict(row: WorkspaceStudy) -> dict[str, Any]:
    return {
        "study_id": str(row.id),
        "study_key": row.study_key,
        "title": row.title,
        "sponsor": row.sponsor,
        "product": row.product,
        "dose": row.dose,
        "lifecycle": row.lifecycle,
        "status": row.status,
        "readiness": row.readiness_code,
        "readiness_label": row.readiness_label,
        "document_count": int(row.document_count or 0),
        "state_version": row.state_version,
        "organization_id": str(row.organization_id),
        "created_by_user_id": str(row.created_by_user_id) if row.created_by_user_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_studies_for_org(
    db: Session,
    *,
    organization_id: UUID,
    q: str | None = None,
    lifecycle: str | None = None,
    readiness: str | None = None,
    offset: int = 0,
    limit: int = 20,
    sort: str = "-updated_at",
) -> dict[str, Any]:
    offset = max(0, int(offset))
    limit = min(100, max(1, int(limit)))
    stmt = select(WorkspaceStudy).where(
        WorkspaceStudy.organization_id == organization_id,
        WorkspaceStudy.status == "ACTIVE",
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                WorkspaceStudy.study_key.ilike(like),
                WorkspaceStudy.title.ilike(like),
                WorkspaceStudy.sponsor.ilike(like),
                WorkspaceStudy.product.ilike(like),
            )
        )
    if lifecycle:
        stmt = stmt.where(WorkspaceStudy.lifecycle == lifecycle)
    if readiness:
        stmt = stmt.where(WorkspaceStudy.readiness_code == readiness)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(db.execute(count_stmt).scalar_one())

    sort_map = {
        "-updated_at": WorkspaceStudy.updated_at.desc(),
        "updated_at": WorkspaceStudy.updated_at.asc(),
        "-created_at": WorkspaceStudy.created_at.desc(),
        "created_at": WorkspaceStudy.created_at.asc(),
        "title": WorkspaceStudy.title.asc(),
        "study_key": WorkspaceStudy.study_key.asc(),
    }
    order = sort_map.get(sort or "-updated_at", WorkspaceStudy.updated_at.desc())
    rows = db.execute(stmt.order_by(order).offset(offset).limit(limit)).scalars().all()
    return {
        "studies": [study_to_catalog_dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
        "organization_id": str(organization_id),
    }


def sync_study_summary(
    db: Session,
    study_key: str,
    *,
    organization_id: UUID | None = None,
) -> WorkspaceStudy | None:
    """Denormalize readiness / lifecycle / document_count onto WorkspaceStudy.

    Call while in-memory state is still warm (before cache invalidate).
    """
    row = db.execute(
        select(WorkspaceStudy).where(WorkspaceStudy.study_key == study_key)
    ).scalar_one_or_none()
    if row is None:
        return None
    docs = list_study_documents(db, study_key)
    row.document_count = len(docs)
    try:
        from app.domain.study_workspace import compute_readiness

        ready = compute_readiness(study_key)
        row.lifecycle = str(ready.get("lifecycle") or row.lifecycle or "DRAFT")
        row.readiness_code = str(ready.get("readiness") or ready.get("readiness_code") or "UNKNOWN")
        row.readiness_label = str(
            ready.get("readiness_label") or ready.get("overall_readiness") or row.readiness_code
        )
    except Exception:
        pass
    if organization_id is not None:
        row.organization_id = organization_id
    row.state_version = int(row.state_version or 1) + 1
    db.commit()
    db.refresh(row)
    return row


def get_study_by_key(db: Session, study_key: str) -> WorkspaceStudy | None:
    return db.execute(
        select(WorkspaceStudy).where(WorkspaceStudy.study_key == study_key)
    ).scalar_one_or_none()
