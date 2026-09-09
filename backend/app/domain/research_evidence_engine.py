"""Research evidence engine orchestrator — Phase 15.2.

KnowledgeGap → ResearchTask → Query → Search → Source → Claims → Review → Decision bridge.
Never mutates Study. Never auto-verifies. Never auto-approves decisions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from app.domain.research_analogue import enrich_analogue_record
from app.domain.research_conflicts import detect_numeric_conflicts
from app.domain.research_evidence_classes import GAP_TO_TASK, TASK_TYPE_LABELS_RU
from app.domain.research_evidence_models import (
    AnalogueStudyRecord,
    RegisteredSource,
    ResearchClaim,
    ResearchTask,
    SourceResult,
)
from app.domain.research_evidence_store import (
    coverage_for_gap,
    find_source_by_locator_or_id,
    get_claim,
    get_task,
    list_claims,
    list_conflicts,
    list_queries,
    list_results,
    list_tasks,
    put_claim,
    put_conflict,
    put_query,
    put_result,
    put_source,
    put_task,
)
from app.domain.research_extract import extract_claims_from_hit
from app.domain.research_mock_provider import MockResearchProvider
from app.domain.research_provider import NullResearchProvider, ResearchProvider
from app.domain.research_query_gen import generate_research_query
from app.domain.research_usability import apply_usability, can_unblock_decision, compute_usability


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_tasks_from_gaps(
    study_id: str,
    gaps: list[dict[str, Any]],
    *,
    package_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> list[ResearchTask]:
    """Create ResearchTasks from KnowledgeGap codes. Idempotent per gap code."""
    existing = {t.knowledge_gap_code: t for t in list_tasks(study_id)}
    created: list[ResearchTask] = []
    for g in gaps:
        code = str(g.get("code") or g.get("knowledge_gap_code") or "")
        if not code or code not in GAP_TO_TASK:
            continue
        if code in existing:
            created.append(existing[code])
            continue
        meta = GAP_TO_TASK[code]
        task = ResearchTask(
            task_type=meta["task_type"],
            question=g.get("title") or TASK_TYPE_LABELS_RU.get(meta["task_type"], code),
            study_id=study_id,
            knowledge_gap_id=str(g.get("id") or code),
            knowledge_gap_code=code,
            required_field_paths=[meta["field_path"]],
            priority=meta["priority"],
            package_id=package_id,
            status="OPEN",
        )
        put_task(task)
        q = generate_research_query(task, context=context)
        task.query = q.query_text
        task.updated_at = _now()
        put_task(task)
        put_query(q)
        created.append(task)
    return created


def create_tasks_from_decision_gaps(
    study_id: str,
    decisions: list[Any],
    *,
    package_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> list[ResearchTask]:
    gaps: list[dict[str, Any]] = []
    for d in decisions:
        for g in getattr(d, "knowledge_gaps", None) or []:
            gaps.append(g if isinstance(g, dict) else dict(g))
        for t in getattr(d, "research_tasks", None) or []:
            # Map task codes to gap codes when present
            code = (t if isinstance(t, dict) else {}).get("code")
            if code == "FIND_HALF_LIFE_PK":
                gaps.append({"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "Half-life"})
            elif code == "FIND_TMAX_PK":
                gaps.append({"code": "MISSING_TMAX_FOR_SAMPLING", "title": "Tmax"})
            elif code == "FIND_CVINTRA_LITERATURE":
                gaps.append({"code": "MISSING_CVINTRA", "title": "CVintra"})
    # Also ensure meal gap
    return create_tasks_from_gaps(study_id, gaps, package_id=package_id, context=context)


def register_source_from_result(
    result: SourceResult,
    *,
    study_id: str | None = None,
) -> RegisteredSource:
    """Register into Source/SourceVersion vocabulary. Deduplicate by locator/DOI/hash."""
    existing = find_source_by_locator_or_id(result.url_or_source_locator, result.identifier)
    if existing:
        result.registered_source_id = existing.id
        result.registered_source_version_id = existing.version_id
        put_result(result)
        return existing
    content = result.text_excerpt or result.url_or_source_locator or result.title
    h = sha256(content.encode("utf-8")).hexdigest()[:16]
    src = RegisteredSource(
        locator=result.url_or_source_locator or result.title,
        source_type=result.source_type,
        title=result.title,
        content_hash=result.content_hash or h,
        classification=result.source_type,
        study_id=study_id or result.study_id,
    )
    put_source(src)
    result.registered_source_id = src.id
    result.registered_source_version_id = src.version_id
    result.content_hash = src.content_hash
    put_result(result)
    return src


def bump_source_version(source_id: str, *, new_hash: str) -> RegisteredSource:
    """New content → new SourceVersion; stale claims require review."""
    from app.domain.research_evidence_store import get_source

    src = get_source(source_id)
    if src is None:
        raise KeyError("source not found")
    old_version = src.version_id
    src.version_id = f"SV-{sha256(new_hash.encode()).hexdigest()[:10]}"
    src.version = str(int(src.version) + 1) if str(src.version).isdigit() else "2"
    src.content_hash = new_hash
    put_source(src)
    # Mark claims on old version REQUIRES_REVIEW / stale applicability
    for c in list_claims():
        if c.source_id == source_id and c.source_version_id == old_version:
            c.applicability_reason = (c.applicability_reason or "") + f" | STALE version {old_version}"
            c.usability = "REQUIRES_REVIEW"
            if c.verification_status == "VERIFIED":
                c.review_history.append(
                    {
                        "action": "SOURCE_VERSION_CHANGED",
                        "old_version": old_version,
                        "new_version": src.version_id,
                        "at": _now(),
                    }
                )
            put_claim(c)
    return src


def run_research_task(
    task_id: str,
    *,
    provider: ResearchProvider | None = None,
    context: dict[str, Any] | None = None,
    register_sources: bool = True,
) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise KeyError("task not found")
    provider = provider or MockResearchProvider()
    ctx = context or {}
    task.status = "SEARCHING"
    task.updated_at = _now()
    put_task(task)

    queries = list_queries(task.id)
    if not queries:
        q = generate_research_query(task, context=ctx)
        put_query(q)
        queries = [q]
        task.query = q.query_text
    query = queries[-1]

    hits = provider.search(query.query_text, query_type=query.query_type)
    results: list[SourceResult] = []
    claims: list[ResearchClaim] = []
    seen_locators: set[str] = set()

    for hit in hits:
        hit = provider.fetch(hit)
        if hit.locator in seen_locators:
            continue
        seen_locators.add(hit.locator)
        # Deduplicate against existing results for this task
        existing = [
            r
            for r in list_results(task.id)
            if r.url_or_source_locator == hit.locator
            or (hit.identifier and r.identifier == hit.identifier)
        ]
        if existing:
            sr = existing[0]
        else:
            sr = SourceResult(
                research_task_id=task.id,
                provider=provider.kind,
                title=hit.title,
                url_or_source_locator=hit.locator,
                source_type=hit.source_type if hit.source_type in {
                    "SMPC", "REGULATORY", "PUBLICATION", "CLINICAL_STUDY",
                    "PROTOCOL", "REVIEW", "DATABASE", "OTHER",
                } else "OTHER",
                publication_date=hit.publication_date,
                author=hit.author,
                journal=hit.journal,
                identifier=hit.identifier,
                raw_metadata=dict(hit.metadata or {}),
                text_excerpt=(hit.text or "")[:2000],
                study_id=task.study_id,
            )
            put_result(sr)
        if register_sources:
            register_source_from_result(sr, study_id=task.study_id)
        results.append(sr)
        extracted = extract_claims_from_hit(
            hit,
            research_task_id=task.id,
            source_result=sr,
            study_id=task.study_id,
            context=ctx,
        )
        for c in extracted:
            # Deduplicate claims by source+field+value
            dup = any(
                x.source_result_id == c.source_result_id
                and x.field_path == c.field_path
                and x.value == c.value
                for x in list_claims(task.id)
            )
            if dup:
                continue
            c.verification_status = "PROPOSED"  # never auto-verify
            apply_usability(c)
            put_claim(c)
            claims.append(c)

    # Conflicts for half-life / CV / Tmax point values
    for fp in ("pk.t_half", "cv_intra", "pk.Tmax"):
        for conf in detect_numeric_conflicts(
            list_claims(task.id),
            field_path=fp,
            research_task_id=task.id,
            study_id=task.study_id,
        ):
            # avoid duplicate conflict records
            existing_c = [
                x
                for x in list_conflicts(task.id)
                if x.field_path == fp and x.status == "OPEN"
            ]
            if not existing_c:
                put_conflict(conf)

    task.status = "REVIEW_REQUIRED" if claims else "RESULTS_AVAILABLE"
    if not results:
        task.status = "OPEN"
        task.notes = "No sources found — missing external source does not produce synthetic content"
    task.updated_at = _now()
    put_task(task)

    return {
        "task": task.to_dict(),
        "query": query.to_dict(),
        "results": [r.to_dict() for r in results],
        "claims": [c.to_dict() for c in list_claims(task.id)],
        "conflicts": [c.to_dict() for c in list_conflicts(task.id)],
        "study_mutated": False,
        "automatic_verifications": 0,
    }


def verify_claim(
    claim_id: str,
    *,
    reviewer: str,
    applicability: str | None = None,
    applicability_reason: str | None = None,
    actor: str | None = None,
) -> ResearchClaim:
    if actor and str(actor).upper() in {"AI", "MOCKAI", "MOCK_AI"}:
        raise PermissionError("AI cannot verify research claims")
    if not reviewer or not str(reviewer).strip():
        raise ValueError("reviewer required")
    claim = get_claim(claim_id)
    if claim is None:
        raise KeyError("claim not found")
    # Do not rewrite excerpt/source
    excerpt_before = claim.excerpt
    if applicability:
        claim.applicability = applicability
    if applicability_reason is not None:
        claim.applicability_reason = applicability_reason
    claim.verification_status = "VERIFIED"
    claim.review_history.append(
        {"action": "VERIFY", "reviewer": reviewer, "at": _now()}
    )
    apply_usability(claim)
    assert claim.excerpt == excerpt_before
    put_claim(claim)
    _maybe_complete_task(claim.research_task_id)
    return claim


def reject_claim(
    claim_id: str,
    *,
    reviewer: str,
    rationale: str,
    actor: str | None = None,
) -> ResearchClaim:
    if actor and str(actor).upper() in {"AI", "MOCKAI", "MOCK_AI"}:
        raise PermissionError("AI cannot reject as authority without human — blocked for AI actor")
    claim = get_claim(claim_id)
    if claim is None:
        raise KeyError("claim not found")
    claim.verification_status = "REJECTED"
    claim.usability = "NOT_USABLE_FOR_DECISION"
    claim.review_history.append(
        {"action": "REJECT", "reviewer": reviewer, "rationale": rationale, "at": _now()}
    )
    put_claim(claim)
    return claim


def request_more_information(
    claim_id: str,
    *,
    reviewer: str,
    note: str,
) -> ResearchClaim:
    claim = get_claim(claim_id)
    if claim is None:
        raise KeyError("claim not found")
    claim.usability = "REQUIRES_REVIEW"
    claim.review_history.append(
        {"action": "REQUEST_MORE_INFORMATION", "reviewer": reviewer, "note": note, "at": _now()}
    )
    put_claim(claim)
    task = get_task(claim.research_task_id or "")
    if task:
        task.status = "REVIEW_REQUIRED"
        put_task(task)
    return claim


def review_applicability(
    claim_id: str,
    *,
    reviewer: str,
    applicability: str,
    reason: str,
    actor: str | None = None,
) -> ResearchClaim:
    if actor and str(actor).upper() in {"AI", "MOCKAI", "MOCK_AI"}:
        raise PermissionError("AI cannot finalize applicability review")
    claim = get_claim(claim_id)
    if claim is None:
        raise KeyError("claim not found")
    claim.applicability = applicability
    claim.applicability_reason = reason
    claim.review_history.append(
        {
            "action": "APPLICABILITY_REVIEW",
            "reviewer": reviewer,
            "applicability": applicability,
            "reason": reason,
            "at": _now(),
        }
    )
    apply_usability(claim)
    put_claim(claim)
    return claim


def _maybe_complete_task(task_id: str | None) -> None:
    if not task_id:
        return
    task = get_task(task_id)
    if task is None:
        return
    claims = list_claims(task_id)
    required = task.required_field_paths
    verified_usable = [
        c
        for c in claims
        if c.verification_status == "VERIFIED"
        and c.usability == "USABLE_FOR_DECISION"
        and (not required or c.field_path in required)
    ]
    # Cannot COMPLETE when required evidence remains unverified
    if required and not verified_usable:
        task.status = "REVIEW_REQUIRED"
    elif verified_usable:
        # Open conflicts on required fields block completion
        open_conf = [
            c
            for c in list_conflicts(task_id)
            if c.status == "OPEN" and (not required or c.field_path in required)
        ]
        if open_conf:
            task.status = "REVIEW_REQUIRED"
            task.notes = "Open evidence conflicts — do not complete"
        else:
            task.status = "COMPLETED"
    task.updated_at = _now()
    put_task(task)


def ai_extract_proposal(claim: ResearchClaim) -> ResearchClaim:
    """AI extraction remains PROPOSED."""
    claim.extraction_method = "AI"
    claim.verification_status = "PROPOSED"
    claim.usability = "REQUIRES_REVIEW"
    put_claim(claim)
    return claim


def default_provider(*, use_mock: bool = True) -> ResearchProvider:
    return MockResearchProvider() if use_mock else NullResearchProvider()


def task_viewer_payload(task_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise KeyError("task not found")
    return {
        "task": task.to_dict(),
        "queries": [q.to_dict() for q in list_queries(task_id)],
        "results": [r.to_dict() for r in list_results(task_id)],
        "evidence": [c.to_dict() for c in list_claims(task_id)],
        "conflicts": [c.to_dict() for c in list_conflicts(task_id)],
        "coverage": coverage_for_gap(task.study_id or "", task.knowledge_gap_code or "").to_dict()
        if task.knowledge_gap_code
        else None,
        "study_mutated": False,
        "proposed_is_not_approved": True,
    }


def evidence_viewer_payload(claim_id: str) -> dict[str, Any]:
    claim = get_claim(claim_id)
    if claim is None:
        raise KeyError("claim not found")
    results = [r for r in list_results(claim.research_task_id or "") if r.id == claim.source_result_id]
    src = results[0] if results else None
    return {
        "source": src.to_dict() if src else None,
        "title": src.title if src else None,
        "author": src.author if src else None,
        "date": src.publication_date if src else None,
        "source_type": src.source_type if src else None,
        "version": claim.source_version_id,
        "claim": claim.to_dict(),
        "measurement": claim.measurement,
        "context": claim.measurement,
        "excerpt": claim.excerpt,
        "location": claim.location,
        "verification": claim.verification_status,
        "applicability": claim.applicability,
        "usability": claim.usability,
        "conflicts": [
            c.to_dict()
            for c in list_conflicts(claim.research_task_id)
            if claim.claim_id in (c.claim_ids or [])
        ],
        "review_history": claim.review_history,
        "study_mutated": False,
    }
