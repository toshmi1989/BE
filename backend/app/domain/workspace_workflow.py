"""Phase 17 / 17.5 — Persistent workflow run records."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace_persistence import WorkspaceWorkflowRun


def save_workflow_run(
    db: Session,
    *,
    study_key: str,
    workflow_id: str,
    stage: str,
    status: str,
    steps: list[dict[str, Any]] | None = None,
    result_summary: dict[str, Any] | None = None,
    error: str | None = None,
    organization_id: UUID | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    if idempotency_key:
        prior = db.execute(
            select(WorkspaceWorkflowRun).where(
                WorkspaceWorkflowRun.study_key == study_key,
                WorkspaceWorkflowRun.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if prior and prior.status == "COMPLETE":
            return _ser(prior)

    row = db.execute(
        select(WorkspaceWorkflowRun).where(WorkspaceWorkflowRun.workflow_id == workflow_id)
    ).scalar_one_or_none()
    if row is None and idempotency_key:
        row = db.execute(
            select(WorkspaceWorkflowRun).where(
                WorkspaceWorkflowRun.study_key == study_key,
                WorkspaceWorkflowRun.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
    if row is None:
        row = WorkspaceWorkflowRun(workflow_id=workflow_id, study_key=study_key)
        db.add(row)
    row.workflow_id = workflow_id
    row.study_key = study_key
    row.organization_id = organization_id or row.organization_id
    row.stage = stage
    row.status = status
    row.error = error
    if idempotency_key:
        row.idempotency_key = idempotency_key
    if steps is not None:
        row.steps = steps
    if result_summary is not None:
        row.result_summary = result_summary
    db.commit()
    db.refresh(row)
    return _ser(row)


def get_workflow_run(db: Session, workflow_id: str) -> dict[str, Any] | None:
    row = db.execute(
        select(WorkspaceWorkflowRun).where(WorkspaceWorkflowRun.workflow_id == workflow_id)
    ).scalar_one_or_none()
    return _ser(row) if row else None


def find_by_idempotency(db: Session, study_key: str, idempotency_key: str) -> dict[str, Any] | None:
    row = db.execute(
        select(WorkspaceWorkflowRun).where(
            WorkspaceWorkflowRun.study_key == study_key,
            WorkspaceWorkflowRun.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    return _ser(row) if row else None


def _ser(row: WorkspaceWorkflowRun) -> dict[str, Any]:
    return {
        "workflow_id": row.workflow_id,
        "study_id": row.study_key,
        "stage": row.stage,
        "status": row.status,
        "error": row.error,
        "steps": row.steps,
        "result_summary": row.result_summary,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
