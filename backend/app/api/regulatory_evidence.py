"""Regulatory Evidence API — Phase 13.1.

Review actions do not mutate Study / Design / Sampling / PK / Safety / ReferenceProduct.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.domain.production_readiness import build_production_readiness_report
from app.domain.regulatory_claims import (
    EvidenceProvenance,
    RegulatoryEvidenceClaim,
    build_claim,
)
from app.domain.regulatory_conflicts import detect_study_evidence_conflict, detect_value_conflicts
from app.domain.regulatory_evidence_manifest import load_regulatory_manifest
from app.domain.regulatory_evidence_pipeline import run_regulatory_evidence_pipeline
from app.domain.regulatory_evidence_tasks import PRIORITY_RULE_WORKSPACE, tasks_as_dicts
from app.domain.regulatory_interview import interview_claims_as_evidence
from app.domain.regulatory_review_queue import (
    RegulatoryReviewItem,
    RegulatoryReviewQueue,
    approve_review_item,
    enqueue_claim_review,
    enqueue_rule_candidate,
    reject_review_item,
    set_review_status,
)
from app.domain.regulatory_source_classes import (
    CLAIM_KINDS,
    CONFIDENCE_LEVELS,
    CONFLICT_TYPES,
    EVIDENCE_DOMAINS,
    REVIEW_ITEM_STATUSES,
    SOURCE_CLASSES,
    SOURCE_VERIFICATION_STATUSES,
)
from app.domain.regulatory_source_slots import gaps_for_missing_required_slots, refresh_slots
from app.domain.regulatory_source_version import (
    get_source_version,
    get_source_versions_by_source,
    import_regulatory_file,
    list_source_versions,
)
from app.domain.regulatory_verify import (
    VerifyGuardError,
    basis_from_source_version,
    claims_from_import,
    create_rule_candidate_from_claim,
    enqueue_import_for_review,
    reject_claim_explicit,
    review_audit_trail,
    verify_claim_explicit,
)


router = APIRouter(prefix="/regulatory-evidence", tags=["regulatory-evidence"])

# In-memory review queue for API contract (no Study mutation). Additive; not a medical store.
_QUEUE = RegulatoryReviewQueue(queue_id="default-regulatory-review")
_CLAIMS: dict[str, dict[str, Any]] = {}
_CLAIM_OBJS: dict[str, RegulatoryEvidenceClaim] = {}
_BASES: dict[str, dict[str, Any]] = {}
_SOURCES_INDEX: dict[str, dict[str, Any]] = {}


def _store_claim(claim: RegulatoryEvidenceClaim) -> None:
    _CLAIM_OBJS[claim.claim_id] = claim
    _CLAIMS[claim.claim_id] = claim.to_dict()


def _claim_from_store(claim_id: str) -> RegulatoryEvidenceClaim:
    if claim_id in _CLAIM_OBJS:
        return _CLAIM_OBJS[claim_id]
    data = _CLAIMS.get(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail="Claim not found")
    prov = data.get("provenance")
    claim = build_claim(
        claim_id=str(data["claim_id"]),
        claim_kind=str(data.get("claim_kind") or "RAW_EXTRACT"),
        domain=str(data.get("domain") or "REPORTING"),
        field_name=data.get("field_name"),
        raw_extract=data.get("raw_extract"),
        normalized_claim=data.get("normalized_claim"),
        confidence=str(data.get("confidence") or "LOW"),
        verification_status=str(data.get("verification_status") or "UNVERIFIED"),
        source_class=data.get("source_class"),
        related_rule_codes=list(data.get("related_rule_codes") or []),
        source_version_id=data.get("source_version_id"),
        provenance=EvidenceProvenance(**prov) if isinstance(prov, dict) else None,
        allow_verified=str(data.get("verification_status") or "").upper() == "VERIFIED",
    )
    claim.notes = data.get("notes")
    claim.reviewed_by = data.get("reviewed_by")
    claim.reviewed_at = data.get("reviewed_at")
    _CLAIM_OBJS[claim_id] = claim
    return claim


class ClaimReviewRequest(BaseModel):
    claim_id: str
    action: str = Field(description="approve|reject|create_rule_candidate")
    rule_code: str | None = None
    reviewer: str | None = None
    proposed_interpretation: str | None = None


class StudyConflictRequest(BaseModel):
    study_field: str
    canonical_value: Any
    source_value: Any
    source_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


@router.get("/meta")
def regulatory_meta() -> dict[str, Any]:
    return {
        "source_classes": list(SOURCE_CLASSES),
        "verification_statuses": list(SOURCE_VERIFICATION_STATUSES),
        "claim_kinds": list(CLAIM_KINDS),
        "confidence_levels": list(CONFIDENCE_LEVELS),
        "conflict_types": list(CONFLICT_TYPES),
        "review_statuses": list(REVIEW_ITEM_STATUSES),
        "evidence_domains": list(EVIDENCE_DOMAINS),
        "priority_rule_workspace": list(PRIORITY_RULE_WORKSPACE),
        "auto_verify": False,
        "study_mutation_on_approve": False,
    }


@router.get("/manifest")
def get_manifest() -> dict[str, Any]:
    m = load_regulatory_manifest()
    return m.to_dict()


@router.get("/tasks")
def list_evidence_tasks() -> dict[str, Any]:
    return {"tasks": tasks_as_dicts()}


@router.get("/interview-claims")
def list_interview_claims() -> dict[str, Any]:
    claims = interview_claims_as_evidence()
    return {
        "source_type": "EXPERT_INTERVIEW",
        "is_regulatory_document": False,
        "claims": [c.to_dict() for c in claims],
    }


@router.post("/pipeline/run")
def run_pipeline(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    result = run_regulatory_evidence_pipeline(
        canonical_study=body.get("canonical_study"),
        include_interview=bool(body.get("include_interview", True)),
    )
    # Seed in-memory claim index for UI
    for c in result.claims:
        _CLAIMS[str(c.get("claim_id"))] = c
    return result.to_dict()


@router.get("/coverage")
def coverage_report() -> dict[str, Any]:
    result = run_regulatory_evidence_pipeline(include_interview=True)
    return result.coverage


@router.get("/review-queue")
def get_review_queue() -> dict[str, Any]:
    if not _QUEUE.items:
        # Bootstrap pending items from interview + priority rules
        for c in interview_claims_as_evidence():
            enqueue_claim_review(_QUEUE, item_id=f"REV-{c.claim_id}", claim_id=c.claim_id, payload=c.to_dict())
            _CLAIMS[c.claim_id] = c.to_dict()
        for rule_code in PRIORITY_RULE_WORKSPACE:
            enqueue_rule_candidate(_QUEUE, item_id=f"REV-RULE-{rule_code}", rule_code=rule_code)
    return _QUEUE.to_dict()


@router.post("/review-queue/{item_id}/action")
def review_action(item_id: str, body: ClaimReviewRequest) -> dict[str, Any]:
    item = next((i for i in _QUEUE.items if i.item_id == item_id), None)
    if item is None:
        item = RegulatoryReviewItem(item_id=item_id, item_type="claim", claim_id=body.claim_id, status="PENDING")
        _QUEUE.items.append(item)
    action = (body.action or "").lower()
    if action == "approve":
        result = approve_review_item(item)
        # Explicit claim verify only if requested via approve on claim — still no Study mutation
        claim_data = _CLAIMS.get(body.claim_id or item.claim_id or "")
        if claim_data and body.reviewer:
            # Rebuild and verify only interview/normalized — REGULATORY_CLAIM needs provenance
            try:
                claim = build_claim(
                    claim_id=str(claim_data["claim_id"]),
                    claim_kind=str(claim_data.get("claim_kind") or "NORMALIZED_CLAIM"),
                    domain=str(claim_data.get("domain") or "REPORTING"),
                    field_name=claim_data.get("field_name"),
                    raw_extract=claim_data.get("raw_extract"),
                    normalized_claim=claim_data.get("normalized_claim"),
                    confidence=str(claim_data.get("confidence") or "LOW"),
                    verification_status=str(claim_data.get("verification_status") or "UNVERIFIED"),
                    source_class=claim_data.get("source_class"),
                    related_rule_codes=list(claim_data.get("related_rule_codes") or []),
                    provenance=EvidenceProvenance(**claim_data["provenance"])
                    if claim_data.get("provenance")
                    else None,
                )
                if claim.verification_status != "VERIFIED":
                    # Do not auto-verify REGULATORY_CLAIM without complete provenance
                    if claim.is_regulatory_claim():
                        result["claim_verified"] = False
                        result["message"] = "Regulatory claim still requires complete provenance + explicit verify"
                    else:
                        # Interview claims stay UNVERIFIED as regulatory proof even if review APPROVED
                        result["claim_verified"] = False
                        result["message"] = "Review APPROVED (practice) — not regulatory VERIFIED; Study unchanged"
            except Exception as exc:  # noqa: BLE001
                result["error"] = str(exc)
        result["study_mutated"] = False
        return result
    if action == "reject":
        return reject_review_item(item)
    if action == "create_rule_candidate":
        rule_code = body.rule_code or "CANDIDATE-NEW"
        cand = enqueue_rule_candidate(
            _QUEUE,
            item_id=f"REV-RULE-{rule_code}-{item_id}",
            rule_code=rule_code,
            claim_id=body.claim_id or item.claim_id,
        )
        return {
            "status": "PENDING",
            "rule_candidate": cand.to_dict(),
            "study_mutated": False,
            "message": "Rule candidate created — not VERIFIED; Study unchanged",
        }
    return {"error": "Unknown action", "study_mutated": False}


@router.post("/study-conflict/detect")
def study_conflict_detect(body: StudyConflictRequest) -> dict[str, Any]:
    conflict = detect_study_evidence_conflict(
        study_field=body.study_field,
        canonical_value=body.canonical_value,
        source_value=body.source_value,
        source_ids=body.source_ids,
        claim_ids=body.claim_ids,
    )
    return {
        "conflict": conflict.to_dict() if conflict else None,
        "study_mutated": False,
        "auto_resolved": False,
    }


@router.post("/conflicts/detect")
def conflicts_detect(body: dict[str, Any]) -> dict[str, Any]:
    claims = list(body.get("claims") or [])
    conflicts = detect_value_conflicts(claims)
    return {
        "conflicts": [c.to_dict() for c in conflicts],
        "auto_resolved": False,
    }


@router.get("/production-readiness-slice")
def production_readiness_slice() -> dict[str, Any]:
    pipe = run_regulatory_evidence_pipeline(include_interview=True)
    slots = [s.to_dict() for s in refresh_slots()]
    report = build_production_readiness_report(
        classification="TECHNICAL_FIXTURE",
        package_id=pipe.manifest.get("manifest_id"),
        regulatory_evidence_coverage={
            **pipe.coverage,
            "slots": slots,
            "imported_versions": len(list_source_versions()),
        },
        evidence_summary={
            "claims": len(pipe.claims),
            "verified_claims": pipe.coverage.get("verified_claims"),
            "proposed_claims": pipe.coverage.get("proposed_claims"),
            "conflicts": len(pipe.conflicts),
            "open_review_items": pipe.coverage.get("open_review_items"),
            "knowledge_gaps": len(pipe.knowledge_gaps),
        },
        production_blockers=[
            "Official Decision 85 document not present in repository",
            "Regulatory claims not VERIFIED",
        ],
        gate_results={"DRAFT": "READY", "REVIEW": "BLOCKED", "FINAL": "BLOCKED"},
        known_limitations=[
            "Regulatory package PARTIAL/MISSING official files",
            "Interview claims are not regulatory verification",
            "KnowledgeRules remain PROPOSED",
        ],
    )
    return report.to_dict()


# ---- Phase 13.2: import / sources / verify ----


class VerifyBody(BaseModel):
    reviewer: str
    notes: str | None = None
    # Client must NOT be trusted for status=VERIFIED
    status: str | None = None


class RejectBody(BaseModel):
    reviewer: str
    notes: str | None = None
    status: str | None = None


class RuleCandidateBody(BaseModel):
    rule_code: str = "CANDIDATE-FROM-CLAIM"
    reviewer: str | None = None


@router.post("/import")
async def import_source(
    file: UploadFile = File(...),
    source_id: str = Form(...),
    source_class: str = Form("OTHER"),
    title: str | None = Form(None),
    document_identifier: str | None = Form(None),
    issuing_authority: str | None = Form(None),
    jurisdiction: str | None = Form(None),
    language: str | None = Form(None),
    technical_fixture: bool = Form(False),
    project_id: str | None = Form(None),
    domain: str = Form("REPORTING"),
    normalized_claim: str | None = Form(None),
) -> dict[str, Any]:
    content = await file.read()
    result = import_regulatory_file(
        content=content,
        filename=file.filename or "upload.bin",
        source_id=source_id,
        source_class=source_class,
        title=title,
        document_identifier=document_identifier,
        issuing_authority=issuing_authority,
        jurisdiction=jurisdiction,
        language=language,
        mime_type=file.content_type,
        technical_fixture=technical_fixture,
        project_id=project_id,
    )
    claims = []
    bases = []
    if result.source_version and result.status in {"IMPORTED", "VERSION_CONFLICT", "EXISTING_SOURCE_VERSION"}:
        _SOURCES_INDEX[result.source_version.source_id] = result.source_version.to_dict()
        if result.status != "EXISTING_SOURCE_VERSION" or result.pages:
            claims_objs = claims_from_import(
                result,
                domain=domain,
                normalized_claim=normalized_claim,
            )
            for c in claims_objs:
                _store_claim(c)
                claims.append(c.to_dict())
            enqueue_import_for_review(_QUEUE, claims_objs)
            if result.source_version and claims_objs:
                basis = basis_from_source_version(
                    result.source_version,
                    claim_id=claims_objs[0].claim_id,
                    page=claims_objs[0].provenance.page if claims_objs[0].provenance else None,
                )
                _BASES[basis.basis_id] = basis.to_dict()
                bases.append(basis.to_dict())
    slots = [s.to_dict() for s in refresh_slots(project_id=project_id)]
    return {
        **result.to_dict(),
        "claims": claims,
        "regulatory_bases": bases,
        "slots": slots,
        "coverage_hint": {
            "imported_versions": len(list_source_versions(project_id=project_id)),
            "missing_required_gaps": gaps_for_missing_required_slots(refresh_slots(project_id=project_id)),
        },
        "auto_verified": False,
        "study_mutated": False,
    }


@router.get("/sources")
def list_sources(project_id: str | None = None) -> dict[str, Any]:
    versions = list_source_versions(project_id=project_id)
    # Group by source_id
    by_id: dict[str, list] = {}
    for v in versions:
        by_id.setdefault(v.source_id, []).append(v.to_dict())
    return {
        "sources": [
            {"source_id": sid, "versions": vers, "current": next((x for x in vers if x.get("is_current")), None)}
            for sid, vers in sorted(by_id.items())
        ],
        "slots": [s.to_dict() for s in refresh_slots(project_id=project_id)],
    }


@router.get("/sources/{source_id}")
def get_source(source_id: str, project_id: str | None = None) -> dict[str, Any]:
    versions = get_source_versions_by_source(source_id)
    if project_id is not None:
        versions = [v for v in versions if v.project_id in {None, project_id}]
    if not versions:
        raise HTTPException(status_code=404, detail="Source not found")
    return {
        "source_id": source_id,
        "versions": [v.to_dict() for v in versions],
        "current": next((v.to_dict() for v in versions if v.is_current), versions[-1].to_dict()),
    }


@router.get("/sources/{source_id}/claims")
def source_claims(source_id: str) -> dict[str, Any]:
    items = [c for c in _CLAIMS.values() if (c.get("provenance") or {}).get("source_id") == source_id]
    return {"source_id": source_id, "claims": items}


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str) -> dict[str, Any]:
    if claim_id not in _CLAIMS:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _CLAIMS[claim_id]


@router.post("/claims/{claim_id}/review")
def start_claim_review(claim_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    claim = _claim_from_store(claim_id)
    # Reject client status=VERIFIED / APPROVED bypass
    if str(body.get("status") or "").upper() in {"VERIFIED", "APPROVED"}:
        raise HTTPException(
            status_code=422,
            detail="Client cannot set VERIFIED/APPROVED directly — use /verify or review-queue approve",
        )
    claim.verification_status = "REVIEW_REQUIRED"
    _store_claim(claim)
    item = next((i for i in _QUEUE.items if i.claim_id == claim_id), None)
    if item is None:
        enqueue_claim_review(_QUEUE, item_id=f"REV-{claim_id}", claim_id=claim_id, payload=claim.to_dict())
        item = _QUEUE.items[-1]
    set_review_status(item, "IN_REVIEW")
    return {
        "claim_id": claim_id,
        "status": "IN_REVIEW",
        "verification_status": claim.verification_status,
        "study_mutated": False,
    }


@router.post("/claims/{claim_id}/verify")
def verify_claim(claim_id: str, body: VerifyBody) -> dict[str, Any]:
    # Ignore/reject client-supplied VERIFIED status
    if body.status and str(body.status).upper() == "VERIFIED":
        # Still require server-side guard path — do not trust payload alone
        pass
    try:
        claim = _claim_from_store(claim_id)
        verified = verify_claim_explicit(claim, reviewer=body.reviewer, notes=body.notes)
        _store_claim(verified)
        return {
            "claim": verified.to_dict(),
            "study_mutated": False,
            "knowledge_rule_status": "unchanged",
            "audit": review_audit_trail()[-1] if review_audit_trail() else None,
        }
    except VerifyGuardError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "field": exc.field, "code": exc.code},
        ) from exc


@router.post("/claims/{claim_id}/reject")
def reject_claim(claim_id: str, body: RejectBody) -> dict[str, Any]:
    if body.status and str(body.status).upper() in {"VERIFIED", "APPROVED"}:
        raise HTTPException(status_code=422, detail="Invalid status bypass on reject")
    try:
        claim = _claim_from_store(claim_id)
        rejected = reject_claim_explicit(claim, reviewer=body.reviewer, notes=body.notes)
        _store_claim(rejected)
        return {"claim": rejected.to_dict(), "study_mutated": False}
    except VerifyGuardError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc), "field": exc.field}) from exc


@router.post("/claims/{claim_id}/rule-candidate")
def claim_rule_candidate(claim_id: str, body: RuleCandidateBody) -> dict[str, Any]:
    claim = _claim_from_store(claim_id)
    cand = create_rule_candidate_from_claim(claim, rule_code=body.rule_code)
    enqueue_rule_candidate(
        _QUEUE,
        item_id=f"REV-RULE-{body.rule_code}-{claim_id}",
        rule_code=body.rule_code,
        claim_id=claim_id,
    )
    return cand


@router.get("/slots")
def list_slots(project_id: str | None = None) -> dict[str, Any]:
    slots = refresh_slots(project_id=project_id)
    return {
        "slots": [s.to_dict() for s in slots],
        "gaps": gaps_for_missing_required_slots(slots),
    }


@router.get("/audit")
def get_audit() -> dict[str, Any]:
    return {"entries": review_audit_trail()}


# ---- Phase 13.3: Decision 85 ----


class Decision85RunBody(BaseModel):
    verify_first_batch: bool = False
    reviewer: str | None = None
    project_id: str | None = None
    canonical_study: dict[str, Any] | None = None


@router.post("/decision85/import")
def decision85_import(project_id: str | None = None) -> dict[str, Any]:
    from app.domain.decision85_claims import import_decision85_source

    result = import_decision85_source(project_id=project_id)
    for c in result.get("claim_objects") or []:
        _store_claim(c)
    # strip non-JSON objects
    out = {k: v for k, v in result.items() if k != "claim_objects"}
    return out


@router.post("/decision85/pipeline")
def decision85_pipeline(body: Decision85RunBody | None = None) -> dict[str, Any]:
    from app.domain.decision85_pipeline import run_decision85_verification_pipeline

    body = body or Decision85RunBody()
    if body.verify_first_batch and not body.reviewer:
        raise HTTPException(status_code=422, detail="reviewer required when verify_first_batch=true")
    # Reject client bypass flags
    result = run_decision85_verification_pipeline(
        project_id=body.project_id,
        verify_first_batch=body.verify_first_batch,
        reviewer=body.reviewer,
        canonical_study=body.canonical_study,
    )
    for c in result.get("claims") or []:
        if c.get("claim_id"):
            _CLAIMS[str(c["claim_id"])] = c
    return {k: v for k, v in result.items() if k != "claim_objects"}


@router.get("/decision85/claims")
def decision85_claims() -> dict[str, Any]:
    items = [c for cid, c in _CLAIMS.items() if str(cid).startswith("D85-")]
    if not items:
        from app.domain.decision85_claims import import_decision85_source

        imported = import_decision85_source()
        for c in imported.get("claim_objects") or []:
            _store_claim(c)
        items = [c.to_dict() for c in (imported.get("claim_objects") or [])]
    return {
        "claims": items,
        "verified": [c for c in items if c.get("verification_status") == "VERIFIED"],
        "proposed": [c for c in items if c.get("verification_status") != "VERIFIED"],
    }
