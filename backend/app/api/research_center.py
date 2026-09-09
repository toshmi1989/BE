"""Research Center API — Phase 15.2.

Auditable research workflow. Never mutates Study. Never auto-verifies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.decision_store import list_decisions, put_context, put_decisions
from app.domain.research_decision_bridge import (
    apply_verified_research_to_context,
    recompute_affected_decisions,
)
from app.domain.research_evidence_engine import (
    create_tasks_from_decision_gaps,
    create_tasks_from_gaps,
    default_provider,
    evidence_viewer_payload,
    reject_claim,
    request_more_information,
    review_applicability,
    run_research_task,
    task_viewer_payload,
    verify_claim,
)
from app.domain.research_evidence_store import (
    clear_research_evidence_store,
    coverage_for_gap,
    get_claim,
    get_task,
    list_claims,
    list_conflicts,
    list_results,
    list_tasks,
    put_task,
    research_center_summary,
)
from app.domain.research_mock_provider import MockResearchProvider
from app.domain.study_input_pipeline import load_real_fixture_package
from app.domain.decision_engine import recompute_from_package
from app.domain.decision_store import clear_decision_store


router = APIRouter(prefix="/research-center", tags=["research-center"])


class CreateTasksIn(BaseModel):
    package_id: str | None = None
    use_golden_fixture: bool = False
    gaps: list[dict[str, Any]] | None = None
    from_decisions: bool = True
    active_substance: str | None = "upadacitinib"
    dose: str | None = "15 mg"
    dosage_form: str | None = "tablet"


class RunTaskIn(BaseModel):
    use_mock_provider: bool = True
    active_substance: str | None = "upadacitinib"
    dose: str | None = "15 mg"
    dosage_form: str | None = "tablet"


class ReviewIn(BaseModel):
    reviewer: str
    rationale: str | None = None
    note: str | None = None
    applicability: str | None = None
    applicability_reason: str | None = None
    actor: str | None = None


class ApplicabilityIn(BaseModel):
    reviewer: str
    applicability: str
    reason: str
    actor: str | None = None


class ApplyToDecisionsIn(BaseModel):
    package_id: str | None = None
    use_golden_fixture: bool = True


@router.get("/studies/{study_id}/research-tasks")
def api_list_tasks(study_id: str) -> dict[str, Any]:
    return research_center_summary(study_id)


@router.post("/studies/{study_id}/research-tasks", status_code=201)
def api_create_tasks(study_id: str, payload: CreateTasksIn | None = None) -> dict[str, Any]:
    payload = payload or CreateTasksIn()
    ctx_info = {
        "active_substance": payload.active_substance,
        "analyte": payload.active_substance,
        "dose": payload.dose,
        "dosage_form": payload.dosage_form,
    }
    gaps = list(payload.gaps or [])
    package_id = payload.package_id
    if payload.use_golden_fixture or payload.from_decisions:
        clear_decision_store()
        pkg = load_real_fixture_package(prefer_text_dump=False)
        pkg.study_id = study_id
        package_id = pkg.package_id
        _, decisions = recompute_from_package(pkg, study_id=study_id)
        put_decisions(study_id, decisions, package_id=package_id)
        if payload.from_decisions:
            tasks = create_tasks_from_decision_gaps(
                study_id, decisions, package_id=package_id, context=ctx_info
            )
        else:
            # Collect gaps from decisions
            for d in decisions:
                gaps.extend(d.knowledge_gaps)
            # Ensure meal gap
            gaps.append({"code": "MISSING_MEAL_COMPOSITION", "title": "Meal composition"})
            tasks = create_tasks_from_gaps(
                study_id, gaps, package_id=package_id, context=ctx_info
            )
    else:
        tasks = create_tasks_from_gaps(
            study_id, gaps, package_id=package_id, context=ctx_info
        )
    return {
        "study_id": study_id,
        "tasks": [t.to_dict() for t in tasks],
        "study_mutated": False,
    }


@router.get("/research-tasks/{task_id}")
def api_get_task(task_id: str) -> dict[str, Any]:
    try:
        return task_viewer_payload(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/research-tasks/{task_id}/run")
def api_run_task(task_id: str, payload: RunTaskIn | None = None) -> dict[str, Any]:
    payload = payload or RunTaskIn()
    if get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    provider = (
        MockResearchProvider() if payload.use_mock_provider else default_provider(use_mock=False)
    )
    try:
        return run_research_task(
            task_id,
            provider=provider,
            context={
                "active_substance": payload.active_substance,
                "analyte": payload.active_substance,
                "dose": payload.dose,
                "dosage_form": payload.dosage_form,
            },
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/research-tasks/{task_id}/results")
def api_results(task_id: str) -> dict[str, Any]:
    if get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    from app.domain.research_real_search import list_stored_search_results

    search_results = [r.to_dict() for r in list_stored_search_results(task_id)]
    return {
        "task_id": task_id,
        "results": [r.to_dict() for r in list_results(task_id)],
        "search_results": search_results,
        "proposed_is_not_verified": True,
        "study_mutated": False,
    }


@router.get("/research-tasks/{task_id}/evidence")
def api_task_evidence(task_id: str) -> dict[str, Any]:
    if get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "task_id": task_id,
        "evidence": [c.to_dict() for c in list_claims(task_id)],
        "proposed_is_not_approved": True,
    }


@router.get("/research-tasks/{task_id}/conflicts")
def api_task_conflicts(task_id: str) -> dict[str, Any]:
    if get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": task_id, "conflicts": [c.to_dict() for c in list_conflicts(task_id)]}


@router.post("/evidence/{claim_id}/verify")
def api_verify(claim_id: str, payload: ReviewIn) -> dict[str, Any]:
    try:
        c = verify_claim(
            claim_id,
            reviewer=payload.reviewer,
            applicability=payload.applicability,
            applicability_reason=payload.applicability_reason,
            actor=payload.actor,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"claim": c.to_dict(), "study_mutated": False}


@router.post("/evidence/{claim_id}/reject")
def api_reject(claim_id: str, payload: ReviewIn) -> dict[str, Any]:
    try:
        c = reject_claim(
            claim_id,
            reviewer=payload.reviewer,
            rationale=payload.rationale or "rejected",
            actor=payload.actor,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"claim": c.to_dict(), "study_mutated": False}


@router.post("/evidence/{claim_id}/request-review")
def api_request_review(claim_id: str, payload: ReviewIn) -> dict[str, Any]:
    try:
        c = request_more_information(
            claim_id, reviewer=payload.reviewer, note=payload.note or payload.rationale or ""
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"claim": c.to_dict(), "study_mutated": False}


@router.get("/evidence/{claim_id}")
def api_evidence_viewer(claim_id: str) -> dict[str, Any]:
    try:
        return evidence_viewer_payload(claim_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/evidence/{claim_id}/applicability")
def api_get_applicability(claim_id: str) -> dict[str, Any]:
    c = get_claim(claim_id)
    if c is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return {
        "claim_id": claim_id,
        "verification_status": c.verification_status,
        "applicability": c.applicability,
        "applicability_reason": c.applicability_reason,
        "usability": c.usability,
        "note": "verification and applicability are independent",
    }


@router.post("/evidence/{claim_id}/applicability/review")
def api_review_applicability(claim_id: str, payload: ApplicabilityIn) -> dict[str, Any]:
    try:
        c = review_applicability(
            claim_id,
            reviewer=payload.reviewer,
            applicability=payload.applicability,
            reason=payload.reason,
            actor=payload.actor,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"claim": c.to_dict(), "study_mutated": False}


@router.get("/studies/{study_id}/coverage")
def api_coverage(study_id: str) -> dict[str, Any]:
    codes = [
        "MISSING_CVINTRA",
        "MISSING_HALF_LIFE_FOR_WASHOUT",
        "MISSING_TMAX_FOR_SAMPLING",
        "MISSING_MEAL_COMPOSITION",
    ]
    return {
        "study_id": study_id,
        "coverage": [coverage_for_gap(study_id, c).to_dict() for c in codes],
        "study_mutated": False,
    }


@router.post("/studies/{study_id}/apply-to-decisions")
def api_apply_to_decisions(study_id: str, payload: ApplyToDecisionsIn | None = None) -> dict[str, Any]:
    """Apply verified usable research to decision context and recompute affected domains only."""
    payload = payload or ApplyToDecisionsIn()
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.study_id = study_id
    ctx, previous = recompute_from_package(pkg, study_id=study_id)
    previous_existing = list_decisions(study_id, package_id=pkg.package_id) or previous
    ctx, applied = apply_verified_research_to_context(ctx, study_id=study_id)
    result = recompute_affected_decisions(ctx, applied_fields=applied, previous=previous_existing)
    put_context(study_id, ctx, package_id=pkg.package_id)
    decisions = result["decisions"]
    put_decisions(study_id, decisions, package_id=pkg.package_id)
    return {
        "study_id": study_id,
        "applied_fields": applied,
        "recomputed_domains": result["recomputed_domains"],
        "decisions": [d.to_dict(for_ui=True) for d in decisions],
        "study_mutated": False,
        "automatic_medical_decisions": 0,
        "expert_decisions": 0,
    }


@router.post("/fixtures/updcb-real/bootstrap", status_code=201)
def api_golden_bootstrap() -> dict[str, Any]:
    """Create research tasks for golden fixture gaps + optional mock run (no Study mutation)."""
    from app.domain.research_audit import clear_audit
    from app.domain.research_real_search import clear_real_search_state

    clear_research_evidence_store()
    clear_decision_store()
    clear_real_search_state()
    clear_audit()
    pkg = load_real_fixture_package(prefer_text_dump=False)
    study_id = pkg.fixture_id or "UPDCB-02-BE-2026"
    pkg.study_id = study_id
    ctx, decisions = recompute_from_package(pkg, study_id=study_id)
    put_decisions(study_id, decisions, package_id=pkg.package_id)
    put_context(study_id, ctx, package_id=pkg.package_id)
    context = {
        "active_substance": "upadacitinib",
        "analyte": "upadacitinib",
        # dose omitted from forced context when conflict exists — still ok for bootstrap identity
        "dosage_form": "tablet",
        "product": "РАНВЭК",
    }
    # Note: do not silently resolve reference_product.dose conflict
    open_dose = any(
        str(c.get("field_path")) == "reference_product.dose" for c in ctx.open_conflicts
    )
    if not open_dose:
        context["dose"] = "15 mg"
    tasks = create_tasks_from_decision_gaps(
        study_id, decisions, package_id=pkg.package_id, context=context
    )
    create_tasks_from_gaps(
        study_id,
        [{"code": "MISSING_MEAL_COMPOSITION", "title": "Meal composition"}],
        package_id=pkg.package_id,
        context=context,
    )
    create_tasks_from_gaps(
        study_id,
        [{"code": "MISSING_SMPC_REFERENCE_PRODUCT", "title": "SmPC reference product"}],
        package_id=pkg.package_id,
        context=context,
    )
    tasks = list_tasks(study_id)
    return {
        "study_id": study_id,
        "fixture_id": pkg.fixture_id,
        "tasks": [t.to_dict() for t in tasks],
        "open_conflicts": [c.get("field_path") for c in ctx.open_conflicts],
        "dose_conflict_remains_open": open_dose,
        "real_provider_available": True,
        "study_mutated": False,
        "automatic_medical_decisions": 0,
    }


class RunRealSearchIn(BaseModel):
    active_substance: str | None = "upadacitinib"
    product: str | None = "РАНВЭК"
    dose: str | None = None  # omit when conflicted
    dosage_form: str | None = "tablet"
    use_injected_mock_web: bool = False  # for tests only
    auto_register_official: bool = True


class RegisterSourceIn(BaseModel):
    research_task_id: str
    fetch_content: bool = False
    mock_text: str | None = None
    active_substance: str | None = "upadacitinib"
    dose: str | None = None
    dosage_form: str | None = "tablet"


class FetchSourceIn(BaseModel):
    locator: str | None = None
    mock_text: str | None = None


class ConflictResolveIn(BaseModel):
    action: str  # VALUE_A | VALUE_B | KEEP_BOTH | REQUEST_MORE_INFORMATION
    reviewer: str
    rationale: str | None = None
    actor: str | None = None


@router.post("/research-tasks/{task_id}/run-real-search")
def api_run_real_search(task_id: str, payload: RunRealSearchIn | None = None) -> dict[str, Any]:
    from app.domain.research_http import ResearchHttpError
    from app.domain.research_mock_provider import MockResearchProvider
    from app.domain.research_real_search import run_real_search
    from app.domain.research_real_web import RealWebResearchProvider

    payload = payload or RunRealSearchIn()
    if get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")

    if payload.use_injected_mock_web:
        # Deterministic "real path" shape using mock hits mapped through RealWeb search_fn
        mock = MockResearchProvider()

        def _fn(query: str):
            hits = mock.search(query, query_type="PK")
            return [
                {
                    "title": h.title,
                    "url": h.locator.replace("mock://", "https://example.test/"),
                    "snippet": h.text,
                    "source_type": h.source_type,
                    "identifier": h.identifier,
                    "authors": h.author,
                    "publication_date": h.publication_date,
                    "metadata": h.metadata,
                }
                for h in hits
            ]

        provider = RealWebResearchProvider(search_fn=_fn)
    else:
        provider = RealWebResearchProvider()

    extras = {
        "active_substance": payload.active_substance,
        "analyte": payload.active_substance,
        "product": payload.product,
        "dosage_form": payload.dosage_form,
    }
    if payload.dose:
        extras["dose"] = payload.dose

    try:
        return run_real_search(
            task_id,
            provider=provider,
            extras=extras,
            open_conflicts=[{"field_path": "reference_product.dose", "status": "OPEN"}]
            if not payload.dose
            else [],
            auto_register_official=payload.auto_register_official,
        )
    except ResearchHttpError as exc:
        return {
            "task_id": task_id,
            "status": "RESEARCH_FAILED",
            "errors": [f"{exc.kind}: {exc}"],
            "results": [],
            "study_mutated": False,
            "automatic_verifications": 0,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/research-results/{result_id}/register-source")
def api_register_source(result_id: str, payload: RegisterSourceIn) -> dict[str, Any]:
    from app.domain.research_real_search import get_search_result
    from app.domain.research_register import register_search_result_as_source

    r = get_search_result(result_id)
    if r is None:
        raise HTTPException(status_code=404, detail="search result not found")
    try:
        return register_search_result_as_source(
            r,
            research_task_id=payload.research_task_id,
            fetch_content=payload.fetch_content,
            mock_text=payload.mock_text,
            context={
                "active_substance": payload.active_substance,
                "dose": payload.dose,
                "dosage_form": payload.dosage_form,
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sources/{source_id}/fetch")
def api_fetch_source(source_id: str, payload: FetchSourceIn | None = None) -> dict[str, Any]:
    from app.domain.research_evidence_store import get_source
    from app.domain.research_fetch import fetch_and_snapshot
    from app.domain.research_http import ResearchHttpError

    payload = payload or FetchSourceIn()
    src = get_source(source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="source not found")
    locator = payload.locator or src.locator
    try:
        snap, text = fetch_and_snapshot(locator, allow_local_mock_text=payload.mock_text)
    except ResearchHttpError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.kind}: {exc}") from exc
    if snap.content_hash:
        src.content_hash = snap.content_hash
        from app.domain.research_evidence_store import put_source

        put_source(src)
    return {
        "source": src.to_dict(),
        "snapshot": snap.to_dict(),
        "text_length": len(text or ""),
        "study_mutated": False,
    }


@router.get("/sources/{source_id}")
def api_get_source(source_id: str) -> dict[str, Any]:
    from app.domain.research_evidence_store import get_source

    src = get_source(source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="source not found")
    return src.to_dict()


@router.get("/sources/{source_id}/versions")
def api_source_versions(source_id: str) -> dict[str, Any]:
    from app.domain.research_evidence_store import get_source

    src = get_source(source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="source not found")
    return {
        "source_id": source_id,
        "versions": [
            {
                "version_id": src.version_id,
                "version": src.version,
                "content_hash": src.content_hash,
                "retrieved_at": src.retrieved_at,
            }
        ],
        "note": "Historical versions remain auditable; bumps create new version_id",
    }


@router.get("/sources/{source_id}/claims")
def api_source_claims(source_id: str) -> dict[str, Any]:
    claims = [c.to_dict() for c in list_claims() if c.source_id == source_id]
    return {
        "source_id": source_id,
        "claims": claims,
        "proposed_is_not_verified": True,
        "study_mutated": False,
    }


# Spec aliases
@router.post("/claims/{claim_id}/verify")
def api_verify_claim_alias(claim_id: str, payload: ReviewIn) -> dict[str, Any]:
    return api_verify(claim_id, payload)


@router.post("/claims/{claim_id}/reject")
def api_reject_claim_alias(claim_id: str, payload: ReviewIn) -> dict[str, Any]:
    return api_reject(claim_id, payload)


@router.post("/claims/{claim_id}/request-review")
def api_request_claim_alias(claim_id: str, payload: ReviewIn) -> dict[str, Any]:
    return api_request_review(claim_id, payload)


@router.post("/claims/{claim_id}/applicability/review")
def api_claim_appl_alias(claim_id: str, payload: ApplicabilityIn) -> dict[str, Any]:
    return api_review_applicability(claim_id, payload)


@router.post("/conflicts/{conflict_id}/resolve")
def api_resolve_conflict(conflict_id: str, payload: ConflictResolveIn) -> dict[str, Any]:
    from app.domain.research_conflict_resolve import resolve_evidence_conflict

    try:
        c = resolve_evidence_conflict(
            conflict_id,
            action=payload.action,
            reviewer=payload.reviewer,
            actor=payload.actor,
            rationale=payload.rationale,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"conflict": c.to_dict(), "study_mutated": False}
