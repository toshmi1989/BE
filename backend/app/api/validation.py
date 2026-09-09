from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.phase5 import (
    ChangeImpactOut,
    ChangeImpactRequest,
    ValidationIssueOut,
    ValidationRunOut,
    ValidationSummaryOut,
)
from app.services import validation_service as val

router = APIRouter(tags=["validation"])


@router.post("/projects/{project_id}/validate", response_model=ValidationRunOut)
def validate_project(project_id: UUID, db: Session = Depends(get_db)) -> ValidationRunOut:
    return val.run_validation(db, project_id)


@router.get("/projects/{project_id}/validation", response_model=list[ValidationIssueOut])
def get_validation(project_id: UUID, db: Session = Depends(get_db)) -> list[ValidationIssueOut]:
    return val.list_validation_issues(db, project_id)


@router.get("/projects/{project_id}/validation/summary", response_model=ValidationSummaryOut)
def get_validation_summary(
    project_id: UUID, db: Session = Depends(get_db)
) -> ValidationSummaryOut:
    return val.validation_summary(db, project_id)


@router.post(
    "/projects/{project_id}/validation/{issue_id}/acknowledge",
    response_model=ValidationIssueOut,
)
def acknowledge_issue(
    project_id: UUID, issue_id: UUID, db: Session = Depends(get_db)
) -> ValidationIssueOut:
    return val.acknowledge_issue(db, project_id, issue_id)


@router.post(
    "/projects/{project_id}/validation/{issue_id}/resolve",
    response_model=ValidationIssueOut,
)
def resolve_issue(
    project_id: UUID, issue_id: UUID, db: Session = Depends(get_db)
) -> ValidationIssueOut:
    return val.resolve_issue(db, project_id, issue_id)


@router.post("/projects/{project_id}/validation/impact", response_model=ChangeImpactOut)
def validation_impact(project_id: UUID, payload: ChangeImpactRequest) -> ChangeImpactOut:
    # project_id reserved for future scoped graphs; impact map is global deterministic
    _ = project_id
    return val.get_change_impact(payload.changed_entity)


@router.get("/projects/{project_id}/validation/snapshot")
def validation_snapshot(project_id: UUID, db: Session = Depends(get_db)) -> dict:
    return val.get_snapshots(db, project_id)
