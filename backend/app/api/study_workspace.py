"""Phase 17 — Study Workspace & workflow API (persistent + auth-aware)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.domain.auth_service import AuthContext, assert_study_access
from app.domain.exceptions import ValidationError
from app.domain.protocol_workflow import run_protocol_workflow
from app.domain.study_workspace import (
    aggregate_conflicts,
    append_audit,
    audit_timeline,
    list_protocol_drafts,
    protocol_draft_diff,
)
from app.domain.workspace_authority import (
    after_mutation,
    ensure_db_authoritative,
    read_preflight,
    read_readiness,
    read_workspace_summary,
)
from app.domain.workspace_documents import list_study_documents, store_study_document
from app.domain.workspace_protocol import (
    build_preview_from_draft,
    generate_docx_artifact,
    get_artifact,
    list_artifacts,
    read_artifact_bytes,
)
from app.domain.workspace_rbac import ROLES, require
from app.domain.workspace_snapshots import create_snapshot, list_snapshots
from app.domain.workspace_workflow import find_by_idempotency, get_workflow_run, save_workflow_run
from app.models.workspace_persistence import WorkspaceDecisionRecord

router = APIRouter(tags=["study-workspace"])


class WorkflowIn(BaseModel):
    use_golden_fixture: bool = True
    run_research: bool = False
    prepare_protocol_draft: bool = True
    auto_approve_decisions: bool = False
    auto_resolve_conflicts: bool = False
    auto_approve_sample_size: bool = False
    auto_approve_statistics: bool = False
    created_by: str = "workflow"
    role: str | None = "MEDICAL_WRITER"
    persist: bool = True
    idempotency_key: str | None = None


class RoleCheckIn(BaseModel):
    role: str
    permission: str


class ExpertDecisionIn(BaseModel):
    question: str
    selected_option: str
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    decision_id: str | None = None
    status: str = "APPROVED"  # expert action only — never auto from workflow


class DocxIn(BaseModel):
    confirm_warnings: bool = False


def _auth_for_study(
    study_id: str,
    *,
    permission: str,
    authorization: str | None,
    db: Session,
) -> AuthContext | None:
    from app.domain.auth_service import resolve_auth

    auth = resolve_auth(db, authorization, required=None)
    return assert_study_access(db, auth, study_id, permission=permission)


@router.get("/studies/{study_id}/workspace")
def get_workspace(
    study_id: str,
    package_id: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    # DB is authoritative — never serve stale process cache as canonical
    return read_workspace_summary(db, study_id, package_id=package_id)


@router.get("/studies/{study_id}/readiness")
def get_readiness(
    study_id: str,
    package_id: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    return read_readiness(db, study_id, package_id=package_id)


@router.get("/studies/{study_id}/conflicts")
def get_conflicts(
    study_id: str,
    package_id: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    rows = aggregate_conflicts(study_id, package_id=package_id)
    return {
        "study_id": study_id,
        "conflicts": rows,
        "count": len(rows),
        "auto_resolve_forbidden": True,
        "study_mutated": False,
        "db_authoritative": True,
    }


@router.get("/studies/{study_id}/preflight")
def get_preflight(
    study_id: str,
    package_id: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="qa", authorization=authorization, db=db)
    return read_preflight(db, study_id, package_id=package_id)


@router.get("/studies/{study_id}/audit")
def get_audit(
    study_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    return {"study_id": study_id, "timeline": audit_timeline(study_id), "db_authoritative": True}


@router.get("/studies/{study_id}/protocol-drafts")
def get_drafts(
    study_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    return {"study_id": study_id, "drafts": list_protocol_drafts(study_id), "db_authoritative": True}


@router.get("/studies/{study_id}/protocol-drafts/diff")
def get_draft_diff(
    study_id: str,
    from_version: int = 1,
    to_version: int = 2,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    return protocol_draft_diff(study_id, from_version, to_version)


@router.get("/studies/{study_id}/protocol/preview")
def protocol_preview(
    study_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    return build_preview_from_draft(db, study_id)


@router.post("/studies/{study_id}/protocol/generate-docx")
def protocol_generate_docx(
    study_id: str,
    payload: DocxIn | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    auth = _auth_for_study(study_id, permission="generate_protocol", authorization=authorization, db=db)
    payload = payload or DocxIn()
    ensure_db_authoritative(db, study_id)
    try:
        art = generate_docx_artifact(
            db,
            study_id,
            created_by=auth.email if auth else "system",
            organization_id=auth.organization_id if auth else None,
            force_warnings_ok=payload.confirm_warnings,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": e.message, "field": e.field, "details": e.details}) from e
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    return art


@router.get("/studies/{study_id}/protocol/artifacts")
def protocol_artifacts(
    study_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    return {"study_id": study_id, "artifacts": list_artifacts(db, study_id)}


@router.get("/studies/{study_id}/protocol/artifacts/{artifact_id}")
def protocol_artifact_meta(
    study_id: str,
    artifact_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    art = get_artifact(db, artifact_id)
    if not art or art["study_id"] != study_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return art


@router.get("/studies/{study_id}/protocol/artifacts/{artifact_id}/download")
def protocol_artifact_download(
    study_id: str,
    artifact_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Response:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    try:
        data, meta = read_artifact_bytes(db, artifact_id)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    if meta["study_id"] != study_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return Response(
        content=data,
        media_type=meta["mime_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{meta["filename"]}"',
            "X-Content-SHA256": meta["sha256"],
        },
    )


@router.get("/studies/{study_id}/snapshots")
def snapshots(
    study_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    return {"study_id": study_id, "snapshots": list_snapshots(db, study_id)}


@router.post("/studies/{study_id}/snapshots")
def post_snapshot(
    study_id: str,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    auth = _auth_for_study(study_id, permission="approve_decisions", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    snap = create_snapshot(
        db,
        study_id,
        created_by=auth.email if auth else "system",
        organization_id=auth.organization_id if auth else None,
        reason="manual_snapshot",
        idempotency_key=idempotency_key,
    )
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    return snap


@router.post("/studies/{study_id}/decisions/expert")
def expert_decision(
    study_id: str,
    payload: ExpertDecisionIn,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create versioned expert decision (never auto-APPROVED by workflow)."""
    auth = _auth_for_study(study_id, permission="approve_decisions", authorization=authorization, db=db)
    from uuid import uuid4

    from app.domain.study_input_store import list_packages, put_package

    ensure_db_authoritative(db, study_id)

    did = payload.decision_id or (f"ED-{idempotency_key}" if idempotency_key else f"ED-{uuid4().hex[:12]}")
    # Idempotent decision by decision_id
    from sqlalchemy import select

    existing = db.execute(
        select(WorkspaceDecisionRecord).where(
            WorkspaceDecisionRecord.decision_id == did,
            WorkspaceDecisionRecord.version == 1,
        )
    ).scalar_one_or_none()
    if existing:
        snaps = list_snapshots(db, study_id)
        return {
            "decision_id": did,
            "status": existing.status,
            "snapshot": snaps[-1] if snaps else None,
            "study_mutated": False,
            "idempotent_replay": True,
        }

    row = WorkspaceDecisionRecord(
        decision_id=did,
        study_key=study_id,
        organization_id=auth.organization_id if auth else None,
        question=payload.question,
        selected_option=payload.selected_option,
        status=payload.status,
        rationale=payload.rationale,
        evidence_refs=payload.evidence_refs,
        created_by=auth.email if auth else "expert",
        version=1,
    )
    db.add(row)
    db.commit()

    if payload.status == "APPROVED" and (
        "dose" in payload.question.lower() or "reference_product.dose" in payload.question
    ):
        pkg = None
        for p in list_packages():
            if p.study_id == study_id:
                pkg = p
                break
        if pkg is None and list_packages():
            pkg = list_packages()[-1]
        if pkg:
            updated = []
            for c in pkg.conflicts:
                cc = dict(c)
                if cc.get("field_path") == "reference_product.dose" and str(cc.get("status") or "OPEN") == "OPEN":
                    cc["status"] = "RESOLVED_BY_EXPERT"
                    cc["resolved_by_decision_id"] = did
                    cc["selected_value"] = payload.selected_option
                updated.append(cc)
            pkg.conflicts = updated
            put_package(pkg)

    snap = None
    if payload.status == "APPROVED":
        snap = create_snapshot(
            db,
            study_id,
            created_by=auth.email if auth else "expert",
            organization_id=auth.organization_id if auth else None,
            based_on_decision_ids=[did],
            reason="expert_decision_approved",
            idempotency_key=f"snap-{did}" if did else idempotency_key,
        )
    append_audit(
        study_id,
        event="EXPERT_DECISION",
        who=auth.email if auth else "expert",
        what=did,
        new_value=payload.selected_option,
        reason=payload.rationale,
    )
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    return {"decision_id": did, "status": payload.status, "snapshot": snap, "study_mutated": False}


@router.post("/studies/{study_id}/documents/upload")
async def upload_document(
    study_id: str,
    file: UploadFile = File(...),
    document_type: str = Form("OTHER"),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    auth = _auth_for_study(study_id, permission="upload_documents", authorization=authorization, db=db)
    content = await file.read()
    try:
        out = store_study_document(
            db,
            study_key=study_id,
            filename=file.filename or "upload.bin",
            content=content,
            document_type=document_type,
            mime_type=file.content_type,
            uploaded_by=auth.email if auth else "anonymous",
            organization_id=auth.organization_id if auth else None,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": e.message, "field": e.field}) from e
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    return out


@router.get("/studies/{study_id}/documents")
def list_documents(
    study_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    return {"study_id": study_id, "documents": list_study_documents(db, study_id)}


@router.post("/studies/{study_id}/workflow/run")
def run_workflow(
    study_id: str,
    payload: WorkflowIn | None = None,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    auth = _auth_for_study(study_id, permission="generate_protocol", authorization=authorization, db=db)
    payload = payload or WorkflowIn()
    role = auth.role if auth else payload.role
    perm = require(role, "generate_protocol")
    if not perm["allowed"]:
        raise HTTPException(status_code=403, detail=perm)

    idem = payload.idempotency_key or idempotency_key
    if idem:
        prior = find_by_idempotency(db, study_id, idem)
        if prior and prior.get("status") == "COMPLETE":
            ensure_db_authoritative(db, study_id)
            return {
                "workflow_id": prior["workflow_id"],
                "study_id": study_id,
                "idempotent_replay": True,
                "persisted": True,
                "legacy_protocol_path": False,
                "result_summary": prior.get("result_summary"),
                "steps": prior.get("steps"),
                "study_mutated": False,
                "automatic_medical_decisions": 0,
                "guards": {
                    "auto_approve_decisions": False,
                    "auto_resolve_conflicts": False,
                    "dose_conflict_auto_resolved": False,
                },
                "workspace": read_workspace_summary(db, study_id),
                "readiness": (prior.get("result_summary") or {}).get("readiness"),
                "preflight": (prior.get("result_summary") or {}).get("preflight"),
            }

    try:
        out = run_protocol_workflow(
            study_id,
            use_golden_fixture=payload.use_golden_fixture,
            run_research=payload.run_research,
            prepare_protocol_draft=payload.prepare_protocol_draft,
            auto_approve_decisions=payload.auto_approve_decisions,
            auto_resolve_conflicts=payload.auto_resolve_conflicts,
            auto_approve_sample_size=payload.auto_approve_sample_size,
            auto_approve_statistics=payload.auto_approve_statistics,
            created_by=auth.email if auth else payload.created_by,
        )
    except ValidationError as e:
        save_workflow_run(
            db,
            study_key=study_id,
            workflow_id=f"FAILED-{study_id}",
            stage="FAILED",
            status="FAILED",
            error=str(e),
            organization_id=auth.organization_id if auth else None,
            idempotency_key=idem,
        )
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e

    create_snapshot(
        db,
        study_id,
        created_by=auth.email if auth else payload.created_by,
        organization_id=auth.organization_id if auth else None,
        reason="workflow_complete",
        idempotency_key=f"wf-snap-{idem}" if idem else f"wf-snap-{out['workflow_id']}",
    )
    if payload.persist:
        after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    save_workflow_run(
        db,
        study_key=study_id,
        workflow_id=out["workflow_id"],
        stage="COMPLETE",
        status="COMPLETE",
        steps=out.get("steps"),
        result_summary={"readiness": out.get("readiness"), "preflight": out.get("preflight")},
        organization_id=auth.organization_id if auth else None,
        idempotency_key=idem,
    )
    out["persisted"] = True
    out["legacy_protocol_path"] = False
    out["db_authoritative"] = True
    return out


@router.get("/workflows/{workflow_id}")
def get_workflow(
    workflow_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.domain.auth_service import resolve_auth

    resolve_auth(db, authorization, required=None)
    row = get_workflow_run(db, workflow_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return row


@router.post("/studies/{study_id}/workspace/hydrate")
def hydrate(
    study_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ok = ensure_db_authoritative(db, study_id)
    return {"hydrated": ok, "workspace": read_workspace_summary(db, study_id) if ok else None, "db_authoritative": True}


@router.get("/workspace/roles")
def list_roles() -> dict[str, Any]:
    return {
        "roles": list(ROLES),
        "note": "Phase 17.5 — canonical tenant Organization + membership RBAC",
        "organization_model": "Organization (tenant) / StudyParty (project-party)",
    }


@router.post("/workspace/roles/check")
def check_role(payload: RoleCheckIn) -> dict[str, Any]:
    return require(payload.role, payload.permission)


@router.post("/studies/{study_id}/audit")
def post_audit(
    study_id: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    auth = _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    entry = append_audit(
        study_id,
        event=str(payload.get("event") or "NOTE"),
        who=str(payload.get("who") or (auth.email if auth else "user")),
        what=str(payload.get("what") or ""),
        old_value=payload.get("old_value"),
        new_value=payload.get("new_value"),
        reason=payload.get("reason"),
        source=payload.get("source"),
    )
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    return entry
