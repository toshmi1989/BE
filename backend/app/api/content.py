"""Phase 12A.2 — content foundation API."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services import content_service as cs

router = APIRouter(tags=["content"])


@router.get("/procedure-definitions")
def list_procedures(
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return cs.list_procedure_definitions(db, project_id=project_id)


@router.post("/procedure-definitions", status_code=201)
def create_procedure(
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return cs.create_procedure_definition(db, payload)


@router.get("/projects/{project_id}/procedure-schedule")
def get_schedule(project_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return cs.get_procedure_schedule(db, project_id)


@router.post("/projects/{project_id}/procedure-schedule")
def post_schedule(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    persist = bool((payload or {}).get("persist"))
    return cs.compose_and_optionally_persist_schedule(db, project_id, persist=persist)


@router.post("/projects/{project_id}/procedure-schedule/validate")
def validate_schedule(project_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return cs.validate_procedure_schedule(db, project_id)


@router.get("/projects/{project_id}/bioanalysis")
def get_bio(project_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return cs.get_bioanalysis(db, project_id)


@router.post("/projects/{project_id}/bioanalysis/propose")
def propose_bio(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return cs.propose_bioanalysis_for_project(db, project_id, payload)


@router.post("/projects/{project_id}/bioanalysis/validate")
def validate_bio(project_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return cs.validate_bioanalysis(db, project_id)


@router.get("/projects/{project_id}/safety-plan")
def get_safety(project_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return cs.get_safety_plan(db, project_id)


@router.post("/projects/{project_id}/safety-plan/propose")
def propose_safety(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return cs.propose_safety_for_project(db, project_id, payload)


@router.post("/projects/{project_id}/safety-plan/validate")
def validate_safety(project_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return cs.validate_safety(db, project_id)


@router.get("/projects/{project_id}/content-matrix")
def content_matrix(project_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return cs.get_content_matrix_for_project(db, project_id)


@router.post("/projects/{project_id}/content/resolve")
def content_resolve(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return cs.resolve_content(db, project_id, payload)


@router.post("/projects/{project_id}/content/validate")
def content_validate(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return cs.validate_content(db, project_id, payload)


@router.post("/projects/{project_id}/content/generate-core")
def generate_core(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Phase 12B.1 — generate core protocol sections from canonical data."""
    return cs.generate_core_protocol_content(db, project_id, payload)


@router.post("/projects/{project_id}/content/generate-sections-5-8")
def generate_sections_5_8(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Phase 12B.2 — generate sections 5–8 (eligibility / procedures / PK / safety)."""
    return cs.generate_sections_5_8_content(db, project_id, payload)


@router.post("/projects/{project_id}/content/generate-sections-9-15")
def generate_sections_9_15(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Phase 12B.3 — generate sections 9–15 (statistics / admin / ethics / data / finance)."""
    return cs.generate_sections_9_15_content(db, project_id, payload)


@router.post("/projects/{project_id}/content/generate-sections-16-18")
def generate_sections_16_18(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Phase 12B.4 — generate sections 16–18 (appendices / conclusion / literature)."""
    return cs.generate_sections_16_18_content(db, project_id, payload)


@router.post("/projects/{project_id}/content/generate-full-document")
def generate_full_document(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Phase 12B.4 — full protocol assemble + full-document QA (does not force FINAL)."""
    return cs.generate_full_protocol_content(db, project_id, payload)
