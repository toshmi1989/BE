"""Study Input Package API — Phase 14.

Extraction → candidates → review. Never mutates Study from extraction/AI.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.domain.study_input_binary_ingest import validate_binary_upload
from app.domain.study_input_canonical import resolve_to_canonical_projection
from app.domain.study_input_conflicts import FieldConflict, detect_candidate_conflicts, resolve_conflict
from app.domain.study_input_coverage import build_input_coverage
from app.domain.exceptions import ValidationError
from app.domain.study_input_golden import (
    DESIGN_ONLY_EXPECTATIONS,
    UPDCB_SEMANTIC_EXPECTATIONS,
    compare_semantic,
)
from app.domain.study_input_package import reject_candidate, verify_candidate
from app.domain.study_input_pipeline import (
    apply_ai_candidates,
    attach_document,
    create_package,
    load_design_only_fixture,
    load_real_fixture_package,
    reclassify_document,
    run_extraction,
)
from app.domain.study_input_store import get_package, list_packages, package_readiness, put_package


router = APIRouter(prefix="/study-input", tags=["study-input"])


class CreatePackageIn(BaseModel):
    study_id: str | None = None
    project_id: str | None = None
    fixture_id: str | None = None


class ClassifyIn(BaseModel):
    document_type: str
    user_selected: bool = True


class ReviewCandidateIn(BaseModel):
    action: str = Field(description="VERIFY|REJECT")
    reviewer: str
    notes: str | None = None


class ResolveConflictIn(BaseModel):
    reviewer: str
    outcome: str
    reason: str
    selected_candidate_id: str | None = None
    status: str = "RESOLVED"


class AiProposeIn(BaseModel):
    proposals: list[dict[str, Any]]


def _pkg(package_id: str):
    pkg = get_package(package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


@router.post("/packages", status_code=201)
def api_create_package(payload: CreatePackageIn | None = None) -> dict[str, Any]:
    payload = payload or CreatePackageIn()
    pkg = create_package(
        study_id=payload.study_id,
        project_id=payload.project_id,
        fixture_id=payload.fixture_id,
    )
    put_package(pkg)
    return pkg.to_dict()


@router.get("/packages")
def api_list_packages() -> list[dict[str, Any]]:
    return [p.to_dict() for p in list_packages()]


@router.get("/packages/{package_id}")
def api_get_package(package_id: str) -> dict[str, Any]:
    return _pkg(package_id).to_dict()


@router.post("/packages/{package_id}/documents", status_code=201)
async def api_upload_document(
    package_id: str,
    file: UploadFile = File(...),
    document_type: str | None = Form(None),
    role: str = Form("INPUT"),
) -> dict[str, Any]:
    pkg = _pkg(package_id)
    content = await file.read()
    try:
        safe = validate_binary_upload(
            filename=file.filename or "upload.bin",
            mime_type=file.content_type,
            content=content,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    suffix = Path(safe).suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        doc = attach_document(
            pkg,
            path=tmp_path,
            document_type=document_type,
            user_selected=bool(document_type),
            role=role,
            prefer_text_dump=False,
        )
        doc.relative_path = str(tmp_path)
        doc.original_filename = safe
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    put_package(pkg)
    return {
        **doc.to_dict(),
        "ingestion_observability": (pkg.ingestion_runs[-1] if pkg.ingestion_runs else {}),
        "study_mutated": False,
    }


@router.post("/packages/{package_id}/documents/{document_id}/ingest")
def api_ingest_document(package_id: str, document_id: str) -> dict[str, Any]:
    """Re-ingest binary from stored path (binary-first)."""
    pkg = _pkg(package_id)
    doc = next((d for d in pkg.documents if d.document_id == document_id), None)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = Path(doc.relative_path or "")
    if not path.exists():
        raise HTTPException(status_code=400, detail="Binary path missing")
    # Replace attach with fresh binary ingest preserving ids
    from app.domain.study_input_binary_ingest import ingest_binary_file

    ing = ingest_binary_file(
        path,
        source_id=doc.source_id,
        source_version_id=doc.source_version_id,
        document_type=doc.document_type,
        filename=doc.original_filename,
    )
    doc.ingestion_status = ing.extraction_status
    doc.ingestion_warnings = list(ing.warnings)
    doc.content_hash = ing.content_hash
    doc.file_size = ing.file_size
    doc.page_count = ing.page_count
    doc.paragraph_count = ing.paragraph_count
    doc.table_count = ing.table_count
    if not hasattr(pkg, "_ingest_cache"):
        setattr(pkg, "_ingest_cache", {})
    getattr(pkg, "_ingest_cache")[doc.document_id] = {
        "text": ing.extracted_text,
        "pages": ing.pages or None,
        "tables": ing.tables or None,
    }
    pkg.ingestion_runs.append({**ing.observability(), "document_id": doc.document_id})
    put_package(pkg)
    return {
        "document": doc.to_dict(),
        "ingestion": ing.observability(),
        "study_mutated": False,
    }


@router.post("/packages/{package_id}/documents/{document_id}/classify")
def api_classify(package_id: str, document_id: str, payload: ClassifyIn) -> dict[str, Any]:
    pkg = _pkg(package_id)
    try:
        doc = reclassify_document(
            pkg,
            document_id,
            document_type=payload.document_type,
            user_selected=payload.user_selected,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    put_package(pkg)
    return doc.to_dict()


@router.get("/packages/{package_id}/documents")
def api_list_documents(package_id: str) -> list[dict[str, Any]]:
    return [d.to_dict() for d in _pkg(package_id).documents]


@router.post("/packages/{package_id}/extract")
def api_extract(package_id: str) -> dict[str, Any]:
    pkg = _pkg(package_id)
    run_extraction(pkg)
    put_package(pkg)
    return {
        "package_id": pkg.package_id,
        "status": pkg.status,
        "candidate_count": len(pkg.candidates),
        "conflict_count": len(pkg.conflicts),
        "study_mutated": False,
        "package": pkg.to_dict(),
    }


@router.get("/packages/{package_id}/candidates")
def api_candidates(package_id: str) -> list[dict[str, Any]]:
    return [c.to_dict() for c in _pkg(package_id).candidates]


@router.get("/packages/{package_id}/conflicts")
def api_conflicts(package_id: str) -> list[dict[str, Any]]:
    return list(_pkg(package_id).conflicts)


@router.get("/packages/{package_id}/missing")
def api_missing(package_id: str) -> dict[str, Any]:
    pkg = _pkg(package_id)
    return {"knowledge_gaps": pkg.knowledge_gaps, "research_tasks": pkg.research_tasks}


@router.get("/packages/{package_id}/coverage")
def api_coverage(package_id: str) -> dict[str, Any]:
    pkg = _pkg(package_id)
    pkg.coverage = build_input_coverage(pkg)
    return pkg.coverage


@router.post("/packages/{package_id}/candidates/{candidate_id}/review")
def api_review_candidate(package_id: str, candidate_id: str, payload: ReviewCandidateIn) -> dict[str, Any]:
    pkg = _pkg(package_id)
    cand = next((c for c in pkg.candidates if c.id == candidate_id), None)
    if cand is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    action = payload.action.upper()
    try:
        if action == "VERIFY":
            verify_candidate(cand, reviewer=payload.reviewer)
        elif action == "REJECT":
            reject_candidate(cand, reviewer=payload.reviewer, notes=payload.notes)
        else:
            raise HTTPException(status_code=400, detail="action must be VERIFY or REJECT")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    pkg.conflicts = [c.to_dict() for c in detect_candidate_conflicts(pkg.candidates)]
    pkg.coverage = build_input_coverage(pkg)
    put_package(pkg)
    return {
        "candidate": cand.to_dict(),
        "audit": {
            "action": action,
            "reviewer": payload.reviewer,
            "candidate_id": candidate_id,
            "status": cand.status,
        },
        "study_mutated": False,
    }


@router.post("/packages/{package_id}/conflicts/{conflict_id}/resolve")
def api_resolve_conflict(package_id: str, conflict_id: str, payload: ResolveConflictIn) -> dict[str, Any]:
    pkg = _pkg(package_id)
    raw = next((c for c in pkg.conflicts if c.get("conflict_id") == conflict_id), None)
    if raw is None:
        raise HTTPException(status_code=404, detail="Conflict not found")
    conflict = FieldConflict(
        conflict_id=str(raw["conflict_id"]),
        field_path=str(raw["field_path"]),
        candidate_ids=list(raw.get("candidate_ids") or []),
        values=list(raw.get("values") or []),
        sources=list(raw.get("sources") or []),
        status=str(raw.get("status") or "OPEN"),
        outcome=raw.get("outcome"),
        severity=str(raw.get("severity") or "HIGH"),
    )
    try:
        resolve_conflict(
            conflict,
            reviewer=payload.reviewer,
            outcome=payload.outcome,
            reason=payload.reason,
            selected_candidate_id=payload.selected_candidate_id,
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Replace in package
    pkg.conflicts = [conflict.to_dict() if c.get("conflict_id") == conflict_id else c for c in pkg.conflicts]
    pkg.coverage = build_input_coverage(pkg)
    put_package(pkg)
    return {"conflict": conflict.to_dict(), "study_mutated": False}


@router.get("/packages/{package_id}/readiness")
def api_readiness(package_id: str) -> dict[str, Any]:
    return package_readiness(_pkg(package_id))


@router.get("/packages/{package_id}/canonical-projection")
def api_canonical(package_id: str) -> dict[str, Any]:
    pkg = _pkg(package_id)
    result = resolve_to_canonical_projection(pkg.candidates, conflicts=pkg.conflicts, require_verified=True)
    return result.to_dict()


@router.post("/packages/{package_id}/ai-propose")
def api_ai_propose(package_id: str, payload: AiProposeIn) -> dict[str, Any]:
    pkg = _pkg(package_id)
    created = apply_ai_candidates(pkg, payload.proposals)
    put_package(pkg)
    return {
        "created": [c.to_dict() for c in created],
        "rejected_malformed": len(payload.proposals) - len(created),
        "study_mutated": False,
        "note": "AI proposals are PROPOSED only; cannot verify claims or resolve conflicts",
    }


@router.post("/fixtures/updcb-real/load", status_code=201)
def api_load_real_fixture() -> dict[str, Any]:
    pkg = load_real_fixture_package()
    put_package(pkg)
    return pkg.to_dict()


@router.post("/fixtures/design-only/load", status_code=201)
def api_load_design_fixture() -> dict[str, Any]:
    pkg = load_design_only_fixture()
    put_package(pkg)
    return pkg.to_dict()


@router.get("/packages/{package_id}/golden-compare")
def api_golden_compare(package_id: str) -> dict[str, Any]:
    pkg = _pkg(package_id)
    by_path: dict[str, Any] = {}
    dose_all: list[Any] = []
    for c in pkg.candidates:
        if c.status == "REJECTED":
            continue
        # Prefer synopsis/non-checklist for non-conflict fields in comparison map
        if c.field_path not in by_path or c.document_type in {"SYNOPSIS", "DESIGN", "SMPC"}:
            if c.field_path == "reference_product.dose":
                dose_all.append(c.value)
            elif c.field_path not in by_path:
                by_path[c.field_path] = c.value
            elif c.document_type == "SYNOPSIS":
                by_path[c.field_path] = c.value
        else:
            if c.field_path == "reference_product.dose":
                dose_all.append(c.value)
    by_path["reference_product.dose__all"] = dose_all
    # For expected fields use synopsis-preferred values
    for c in pkg.candidates:
        if c.document_type == "SYNOPSIS" and c.field_path not in {
            "reference_product.dose",  # conflict — handled separately
        }:
            by_path[c.field_path] = c.value
    expectations = (
        DESIGN_ONLY_EXPECTATIONS if (pkg.fixture_id or "").startswith("DESIGN") else UPDCB_SEMANTIC_EXPECTATIONS
    )
    report = compare_semantic(
        fixture_id=pkg.fixture_id or pkg.package_id,
        actual_by_path=by_path,
        expectations=expectations,
        conflict_values={"30 mg", "15 mg"} if not (pkg.fixture_id or "").startswith("DESIGN") else None,
    )
    return report.to_dict()
