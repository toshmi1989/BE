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
from app.domain.workspace_documents import list_study_documents, store_study_document, update_document_classification
from app.domain.workspace_protocol import (
    build_preview_from_draft,
    generate_docx_artifact,
    get_artifact,
    list_artifacts,
    read_artifact_bytes,
)
from app.domain.workspace_progress import (
    build_field_detail,
    compute_writer_progress,
    dependency_impact_for_decision,
)
from app.domain.workspace_rbac import ROLES, require
from app.domain.workspace_snapshots import create_snapshot, list_snapshots
from app.domain.workspace_workflow import find_by_idempotency, get_workflow_run, save_workflow_run
from app.models.workspace_persistence import WorkspaceDecisionRecord
from app.schemas.writer_phase28 import (
    CanonicalFactDetailResponse,
    PreflightResponse,
    ProtocolArtifactItem,
    ProtocolArtifactsListResponse,
    ProtocolPreviewResponse,
    StudyCatalogListResponse,
    WorkflowRunResponse,
    WorkspaceSummaryResponse,
    WriterProgressResponse,
)

router = APIRouter(tags=["study-workspace"])


class WorkflowIn(BaseModel):
    use_golden_fixture: bool = False
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


@router.get("/studies/{study_id}/workspace", response_model=WorkspaceSummaryResponse)
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


@router.get("/studies/{study_id}/preflight", response_model=PreflightResponse)
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


@router.get("/studies/{study_id}/protocol/preview", response_model=ProtocolPreviewResponse)
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


@router.get("/studies/{study_id}/protocol/artifacts", response_model=ProtocolArtifactsListResponse)
def protocol_artifacts(
    study_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    return {"study_id": study_id, "artifacts": list_artifacts(db, study_id)}


@router.get("/studies/{study_id}/protocol/artifacts/{artifact_id}", response_model=ProtocolArtifactItem)
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
    impact = dependency_impact_for_decision(payload.question)
    return {
        "decision_id": did,
        "status": payload.status,
        "snapshot": snap,
        "study_mutated": False,
        "auto_approved": False,
        "affects": impact,
        "recalculation_required": bool(impact),
        "message": "Decision approved" if payload.status == "APPROVED" else f"Decision {payload.status}",
        "affected_protocol_sections": ["Protocol sections linked to decision domain"],
    }


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


class ClassifyDocumentIn(BaseModel):
    document_type: str
    actor: str = "writer"


@router.post("/studies/{study_id}/documents/{document_id}/classify")
def classify_document(
    study_id: str,
    document_id: str,
    payload: ClassifyDocumentIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    auth = _auth_for_study(study_id, permission="upload_documents", authorization=authorization, db=db)
    try:
        out = update_document_classification(
            db,
            study_key=study_id,
            document_id=document_id,
            document_type=payload.document_type,
            actor=auth.email if auth else payload.actor,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": e.message, "field": e.field}) from e
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    return out


@router.get("/studies/{study_id}/writer-progress", response_model=WriterProgressResponse)
def writer_progress(
    study_id: str,
    package_id: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    return compute_writer_progress(db, study_id, package_id=package_id)


@router.get(
    "/studies/{study_id}/canonical-facts/{field_path:path}/detail",
    response_model=CanonicalFactDetailResponse,
)
def canonical_fact_detail(
    study_id: str,
    field_path: str,
    package_id: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    return build_field_detail(study_id, field_path, package_id=package_id)


@router.post("/studies/{study_id}/workflow/run", response_model=WorkflowRunResponse)
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

    snap = create_snapshot(
        db,
        study_id,
        created_by=auth.email if auth else payload.created_by,
        organization_id=auth.organization_id if auth else None,
        reason="workflow_complete",
        idempotency_key=f"wf-snap-{idem}" if idem else f"wf-snap-{out['workflow_id']}",
    )
    from app.domain.study_workspace import patch_protocol_draft_based_on

    draft_info = (out.get("protocol_draft") or {}) if isinstance(out, dict) else {}
    patch_protocol_draft_based_on(
        study_id,
        protocol_id=draft_info.get("protocol_id"),
        snapshot_id=snap.get("snapshot_id"),
        decisions=draft_info.get("based_on_decisions"),
        statistics=draft_info.get("based_on_statistics"),
        sample_size=draft_info.get("based_on_sample_size"),
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


class CreateStudyIn(BaseModel):
    study_key: str | None = None
    title: str | None = None
    sponsor: str | None = None
    product: str | None = None
    dose: str | None = None
    is_demo: bool = False


class FactReviewIn(BaseModel):
    field: str
    old_value: Any = None
    new_value: Any = None
    reason: str
    actor: str = "writer"
    action: str = "REVIEW"  # REVIEW | EDIT_PROPOSAL


class DecisionEvidenceRequestIn(BaseModel):
    decision_id: str | None = None
    question: str | None = None
    reason: str
    actor: str = "writer"


@router.get("/studies", response_model=StudyCatalogListResponse)
def list_workspace_studies(
    q: str | None = None,
    lifecycle: str | None = None,
    readiness: str | None = None,
    offset: int = 0,
    limit: int = 20,
    sort: str = "-updated_at",
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Authorized study catalog — primary Writer entry point."""
    from app.core.config import get_settings
    from app.domain.auth_service import resolve_auth
    from app.domain.workspace_study_service import (
        get_or_create_dev_organization,
        list_studies_for_org,
    )

    settings = get_settings()
    auth = resolve_auth(db, authorization, required=settings.auth_required)
    if auth:
        auth.require("view")
        if auth.organization_id is None:
            raise HTTPException(status_code=403, detail="No organization context")
        org_id = auth.organization_id
    else:
        org_id = get_or_create_dev_organization(db).id
    return list_studies_for_org(
        db,
        organization_id=org_id,
        q=q,
        lifecycle=lifecycle,
        readiness=readiness,
        offset=offset,
        limit=limit,
        sort=sort,
    )


@router.post("/studies/create")
def create_workspace_study(
    payload: CreateStudyIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a persistent WorkspaceStudy for writer workflow — no Legacy console."""
    from app.core.config import get_settings
    from app.domain.auth_service import resolve_auth
    from app.domain.workspace_study_service import (
        create_canonical_study,
        get_or_create_dev_organization,
        study_to_catalog_dict,
    )

    if payload.is_demo:
        raise HTTPException(status_code=400, detail="Use demo workflow for demo studies")
    settings = get_settings()
    auth = resolve_auth(db, authorization, required=settings.auth_required)
    if auth:
        auth.require("create_study")
        if auth.organization_id is None:
            raise HTTPException(status_code=403, detail="No organization context")
        org_id = auth.organization_id
        user_id = auth.user_id
        who = auth.email
    else:
        org_id = get_or_create_dev_organization(db).id
        user_id = None
        who = "writer"

    row = create_canonical_study(
        db,
        organization_id=org_id,
        created_by_user_id=user_id,
        study_key=payload.study_key,
        title=payload.title,
        sponsor=payload.sponsor,
        product=payload.product,
        dose=payload.dose,
        is_demo=False,
    )
    append_audit(
        row.study_key,
        event="STUDY_CREATED",
        who=who,
        what=row.study_key,
        new_value={
            "title": row.title,
            "sponsor": row.sponsor,
            "product": row.product,
            "dose": row.dose,
            "is_demo": False,
            "organization_id": str(org_id),
        },
        reason="new_study_ux",
    )
    after_mutation(db, row.study_key, organization_id=org_id)
    catalog = study_to_catalog_dict(row)
    return {
        **catalog,
        "is_demo": False,
        "next": "upload_documents",
        "legacy_required": False,
    }


@router.post("/studies/{study_id}/canonical-facts/review")
def review_canonical_fact(
    study_id: str,
    payload: FactReviewIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record field review/edit proposal with audit — never silently mutates verified SoT."""
    auth = _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    if not str(payload.reason or "").strip():
        raise HTTPException(status_code=400, detail="reason required")
    ensure_db_authoritative(db, study_id)
    entry = append_audit(
        study_id,
        event="CANONICAL_FACT_REVIEW" if payload.action == "REVIEW" else "CANONICAL_FACT_EDIT_PROPOSAL",
        who=auth.email if auth else payload.actor,
        what=payload.field,
        old_value=payload.old_value,
        new_value=payload.new_value,
        reason=payload.reason,
    )
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    return {
        "ok": True,
        "silent_mutation": False,
        "study_mutated": False,
        "audit": entry,
        "note": "Verified Study facts are not silently overwritten; expert decision may still be required",
    }


class GapManualIn(BaseModel):
    value: Any = None
    rationale: str
    unit: str | None = None
    pk_parameter: str | None = None
    source_note: str | None = None
    actor: str | None = None
    package_id: str | None = None


class GapResearchIn(BaseModel):
    active_substance: str | None = None
    dosage_form: str | None = None
    dose: str | None = None
    use_mock_provider: bool | None = None
    package_id: str | None = None


class GapVerifyIn(BaseModel):
    claim_id: str
    reviewer: str | None = None
    applicability: str = "DIRECT"
    applicability_reason: str | None = None
    package_id: str | None = None


def _gaps_panel(db: Session, study_id: str, package_id: str | None) -> dict[str, Any]:
    """Read the panel after a mutation: after_mutation drops the process cache."""
    from app.domain.workspace_gaps import collect_study_gaps

    ensure_db_authoritative(db, study_id)
    return collect_study_gaps(study_id, package_id=package_id)


def _search_provider(payload: GapResearchIn):
    """Pick the provider server-side. Mock only when the caller asks for it.

    Returns (provider, unavailable_message). A None provider means the search
    cannot run at all — the writer must be told, not left with a silent button.
    """
    from app.domain.research_http import research_http_settings
    from app.domain.research_mock_provider import MockResearchProvider
    from app.domain.research_real_web import RealWebResearchProvider

    if payload.use_mock_provider:
        return MockResearchProvider(), None
    if not research_http_settings()["enabled"]:
        return None, (
            "Поиск в открытых источниках отключён на сервере "
            "(research_web_enabled=false). Внесите значение вручную."
        )
    return RealWebResearchProvider(), None


PROVIDER_LABEL_RU: dict[str, str] = {
    "MOCK": "демонстрационный набор источников",
    "WEB": "поиск в открытых источниках",
    "LOCAL_DOCUMENTS": "только загруженные документы",
}


@router.get("/studies/{study_id}/gaps")
def list_study_gaps(
    study_id: str,
    package_id: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Inputs the documents did not provide, each with the one place to close it."""
    from app.domain.workspace_gaps import collect_study_gaps

    _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)
    return collect_study_gaps(study_id, package_id=package_id)


@router.post("/studies/{study_id}/gaps/{code}/research")
def research_study_gap(
    study_id: str,
    code: str,
    payload: GapResearchIn | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Search open sources for a missing value. Result stays PROPOSED until verified."""
    from app.domain.research_evidence_engine import create_tasks_from_gaps, run_research_task
    from app.domain.research_http import ResearchHttpError
    from app.domain.workspace_gaps import GAP_CATALOG, RESEARCH, count_gap_proposals

    payload = payload or GapResearchIn()
    auth = _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    ensure_db_authoritative(db, study_id)

    meta = GAP_CATALOG.get(code)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Неизвестный пробел: {code}")
    if RESEARCH not in meta["resolution"]:
        raise HTTPException(
            status_code=422,
            detail=f"«{meta['title']}» не ищется в источниках — это экспертное решение",
        )

    provider, unavailable = _search_provider(payload)
    if provider is None:
        panel = _gaps_panel(db, study_id, payload.package_id)
        return {
            "code": code,
            "research_task_id": None,
            "provider": None,
            "status": "SEARCH_UNAVAILABLE",
            "found": 0,
            "awaiting_verification": 0,
            "sources": [],
            "message": unavailable,
            "gap": next((g for g in panel["gaps"] if g["code"] == code), None),
            "auto_verified": False,
            "study_mutated": False,
        }

    tasks = create_tasks_from_gaps(
        study_id,
        [{"code": code, "title": meta["title"]}],
        package_id=payload.package_id,
        context={
            "active_substance": payload.active_substance,
            "analyte": payload.active_substance,
            "dose": payload.dose,
            "dosage_form": payload.dosage_form,
        },
    )
    if not tasks:
        raise HTTPException(status_code=422, detail="Не удалось создать исследовательскую задачу")
    task = tasks[0]
    where = PROVIDER_LABEL_RU.get(provider.kind, provider.kind)
    context = {
        "active_substance": payload.active_substance,
        "analyte": payload.active_substance,
        "dose": payload.dose,
        "dosage_form": payload.dosage_form,
    }
    before = count_gap_proposals(study_id, code)
    status = "OK"
    message: str | None = None
    sources: list[dict[str, Any]] = []

    if provider.kind == "WEB":
        # Real path: registers sources, extracts from snippets, reports its own status
        from app.domain.research_real_search import run_real_search

        out = run_real_search(task.id, provider=provider, extras=context)
        sources = [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "source_type": r.get("source_type"),
            }
            for r in (out.get("results") or [])[:8]
        ]
        if str(out.get("status")) == "RESEARCH_FAILED":
            status = "SEARCH_FAILED"
            message = (
                f"Поиск не удался: {'; '.join(out.get('errors') or ['внешние источники недоступны'])}. "
                "Значение можно внести вручную."
            )
    else:
        try:
            run_research_task(task.id, provider=provider, context=context)
        except ResearchHttpError as exc:
            status = "SEARCH_FAILED"
            message = (
                f"Поиск не удался ({exc.kind}): внешние источники недоступны. "
                "Значение можно внести вручную."
            )

    append_audit(
        study_id,
        event="GAP_RESEARCH_RUN",
        who=auth.email if auth else "writer",
        what=code,
        reason=f"Поиск недостающего значения: {where}",
        new_value={"research_task_id": task.id, "provider": provider.kind, "status": status},
    )
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    panel = _gaps_panel(db, study_id, payload.package_id)
    gap = next((g for g in panel["gaps"] if g["code"] == code), None)
    awaiting = len(gap["proposals"]) if gap else 0
    found = max(awaiting - before, 0)
    if status == "OK":
        if found:
            message = f"{where}: новых предложений — {found}. Нужна проверка эксперта."
        elif sources:
            status = "SOURCES_ONLY"
            message = (
                f"Нашли источников: {len(sources)}, но значение из выдачи извлечь не удалось. "
                "Откройте источник и внесите значение вручную."
            )
        else:
            status = "NOTHING_FOUND"
            message = (
                f"{where}: пригодных значений не нашли. Платформа ничего не подставляет — "
                "внесите значение вручную с указанием источника."
            )
        if not found and awaiting:
            message += f" Ранее найденные предложения ждут проверки: {awaiting}."
    return {
        "code": code,
        "research_task_id": task.id,
        "provider": provider.kind,
        "status": status,
        "found": found,
        "awaiting_verification": awaiting,
        "sources": sources,
        "message": message,
        "gap": gap,
        "auto_verified": False,
        "study_mutated": False,
    }


@router.post("/studies/{study_id}/gaps/{code}/verify")
def verify_study_gap(
    study_id: str,
    code: str,
    payload: GapVerifyIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Expert confirms a proposed value. Only then do dependent steps use it."""
    from app.domain.research_evidence_engine import verify_claim
    from app.domain.workspace_gaps import apply_verified_evidence

    auth = _auth_for_study(
        study_id, permission="approve_decisions", authorization=authorization, db=db
    )
    ensure_db_authoritative(db, study_id)
    reviewer = payload.reviewer or (auth.email if auth else "")
    if not str(reviewer or "").strip():
        raise HTTPException(status_code=400, detail="Требуется имя проверяющего")
    try:
        claim = verify_claim(
            payload.claim_id,
            reviewer=reviewer,
            applicability=payload.applicability,
            applicability_reason=payload.applicability_reason
            or "Проверено экспертом для этого исследования",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    applied = apply_verified_evidence(study_id, package_id=payload.package_id)
    append_audit(
        study_id,
        event="GAP_VALUE_VERIFIED",
        who=reviewer,
        what=code,
        new_value={"claim_id": claim.id, "value": claim.value, "unit": claim.unit},
        reason=payload.applicability_reason or "Экспертное подтверждение значения",
    )
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    panel = _gaps_panel(db, study_id, payload.package_id)
    return {
        "code": code,
        "claim": claim.to_dict(),
        "applied_fields": applied["applied_fields"],
        "recomputed_domains": applied["recomputed_domains"],
        "gaps": panel["gaps"],
        "counts": panel["counts"],
        "study_mutated": False,
    }


@router.post("/studies/{study_id}/gaps/{code}/resolve-manual")
def resolve_study_gap_manually(
    study_id: str,
    code: str,
    payload: GapManualIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Expert enters a missing value directly, with a rationale. Never silent."""
    from app.domain.workspace_gaps import resolve_gap_manually

    auth = _auth_for_study(
        study_id, permission="approve_decisions", authorization=authorization, db=db
    )
    ensure_db_authoritative(db, study_id)
    actor = payload.actor or (auth.email if auth else "")
    try:
        result = resolve_gap_manually(
            study_id,
            code,
            value=payload.value,
            rationale=payload.rationale,
            actor=actor,
            unit=payload.unit,
            pk_parameter=payload.pk_parameter,
            source_note=payload.source_note,
            package_id=payload.package_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    append_audit(
        study_id,
        event="GAP_RESOLVED_BY_EXPERT",
        who=actor,
        what=code,
        new_value={"value": payload.value, "unit": payload.unit},
        reason=payload.rationale,
    )
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    panel = _gaps_panel(db, study_id, payload.package_id)
    return {**result, "gaps": panel["gaps"], "counts": panel["counts"]}


@router.post("/studies/{study_id}/decisions/request-evidence")
def request_decision_evidence(
    study_id: str,
    payload: DecisionEvidenceRequestIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Writer requests additional evidence — does not auto-approve or resolve conflicts."""
    auth = _auth_for_study(study_id, permission="view", authorization=authorization, db=db)
    if not str(payload.reason or "").strip():
        raise HTTPException(status_code=400, detail="reason required")
    ensure_db_authoritative(db, study_id)
    entry = append_audit(
        study_id,
        event="EVIDENCE_REQUESTED",
        who=auth.email if auth else payload.actor,
        what=payload.decision_id or payload.question or "decision",
        reason=payload.reason,
        new_value={"decision_id": payload.decision_id, "question": payload.question},
    )
    after_mutation(db, study_id, organization_id=auth.organization_id if auth else None)
    return {"ok": True, "auto_approved": False, "audit": entry}
