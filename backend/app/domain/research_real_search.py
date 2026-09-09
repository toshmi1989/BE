"""Real search orchestration — Phase 15.3.

Separates MOCK deterministic runs from REAL provider runs.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.domain.research_audit import audit_log
from app.domain.research_conflicts import detect_numeric_conflicts
from app.domain.research_evidence_store import (
    get_task,
    list_claims,
    list_conflicts,
    list_queries,
    put_conflict,
    put_query,
    put_task,
)
from app.domain.research_http import ResearchHttpError
from app.domain.research_provider import ProviderHit, ResearchProvider
from app.domain.research_query_context import generate_contextual_query, smpc_query_variants
from app.domain.research_real_web import RealWebResearchProvider
from app.domain.research_register import maybe_auto_register_official
from app.domain.research_search_result import ResearchRunLog, ResearchSearchResult
from app.domain.research_evidence_engine import run_research_task
from app.domain.research_sanitize import sanitize_url
from app.domain.research_search_result import infer_priority_class


_SEARCH_RESULTS: dict[str, list[ResearchSearchResult]] = {}  # task_id → results
_RUN_LOGS: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clear_real_search_state() -> None:
    _SEARCH_RESULTS.clear()
    _RUN_LOGS.clear()


def list_stored_search_results(task_id: str) -> list[ResearchSearchResult]:
    return list(_SEARCH_RESULTS.get(task_id, []))


def get_search_result(result_id: str) -> ResearchSearchResult | None:
    for results in _SEARCH_RESULTS.values():
        for r in results:
            if r.id == result_id:
                return r
    return None


def store_search_results(task_id: str, results: list[ResearchSearchResult]) -> None:
    _SEARCH_RESULTS[task_id] = list(results)


def run_real_search(
    task_id: str,
    *,
    provider: ResearchProvider | None = None,
    structured_facts: dict[str, Any] | None = None,
    open_conflicts: list[dict[str, Any]] | None = None,
    extras: dict[str, Any] | None = None,
    auto_register_official: bool = True,
    extract_from_snippets: bool = True,
) -> dict[str, Any]:
    """Execute real (or injected) provider search. Never mutates Study. Never auto-verifies."""
    task = get_task(task_id)
    if task is None:
        raise KeyError("task not found")

    provider = provider or RealWebResearchProvider()
    start = _now()
    t0 = time.perf_counter()
    task.status = "SEARCHING"
    task.updated_at = start
    put_task(task)

    q = generate_contextual_query(
        task,
        structured_facts=structured_facts,
        open_conflicts=open_conflicts,
        extras=extras,
    )
    put_query(q)
    task.query = q.query_text
    put_task(task)

    audit_log(
        "SEARCH_STARTED",
        study_id=task.study_id,
        task_id=task.id,
        provider=provider.kind,
        query=q.query_text,
    )

    run_log = ResearchRunLog(
        task_id=task.id,
        query=q.query_text,
        provider=provider.kind,
        start_time=start,
        status="OK",
    )
    errors: list[str] = []
    results: list[ResearchSearchResult] = []

    try:
        queries = [q.query_text]
        if task.task_type == "FIND_SMPC_REFERENCE_PRODUCT":
            extras = extras or {}
            queries = smpc_query_variants(
                extras.get("product") or (structured_facts or {}).get("reference_product.name"),
                extras.get("active_substance"),
            )

        all_hits = []
        seen_urls: set[str] = set()
        accumulated_rs: list = []
        for qt in queries:
            try:
                hits = provider.search(qt, query_type=q.query_type)
            except ResearchHttpError as exc:
                errors.append(f"{exc.kind}: {exc}")
                continue
            if isinstance(provider, RealWebResearchProvider):
                for r in provider.last_results:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        accumulated_rs.append(r)
            for h in hits:
                if h.locator in seen_urls:
                    continue
                seen_urls.add(h.locator)
                all_hits.append(h)

        if accumulated_rs:
            for r in accumulated_rs:
                r.research_task_id = task.id
                r.study_id = task.study_id
                results.append(r)
        elif isinstance(provider, RealWebResearchProvider) and provider.last_results:
            seen_rs: set[str] = set()
            for r in provider.last_results:
                if r.url in seen_rs:
                    continue
                seen_rs.add(r.url)
                r.research_task_id = task.id
                r.study_id = task.study_id
                results.append(r)
        else:
            for h in all_hits:
                try:
                    url = sanitize_url(h.locator) or h.locator
                except ValueError:
                    continue
                stype = (h.metadata or {}).get("real_source_type") or h.source_type or "UNKNOWN"
                if stype not in {
                    "REGULATORY", "SMPC", "PRODUCT_LABEL", "PUBLICATION", "CLINICAL_STUDY",
                    "PROTOCOL", "DATABASE", "GUIDELINE", "REVIEW", "OTHER", "UNKNOWN",
                }:
                    stype = "UNKNOWN"
                results.append(
                    ResearchSearchResult(
                        title=h.title,
                        url=url,
                        provider=provider.kind,
                        snippet=h.text,
                        source_type=stype,
                        publication_date=h.publication_date,
                        authors=h.author,
                        identifier=h.identifier,
                        raw_metadata=dict(h.metadata or {}),
                        priority_class=(h.metadata or {}).get("priority_class")
                        or infer_priority_class(source_type=stype, url=url, title=h.title),
                        research_task_id=task.id,
                        study_id=task.study_id,
                    )
                )

        store_search_results(task.id, results)
        run_log.result_count = len(results)

        if not results and errors:
            run_log.status = "RESEARCH_FAILED"
            task.status = "OPEN"
            task.notes = f"RESEARCH_FAILED: {'; '.join(errors)}"
        elif not results:
            run_log.status = "NO_USABLE_EVIDENCE"
            task.status = "RESULTS_AVAILABLE"
            task.notes = "NO_USABLE_EVIDENCE — search completed with zero results (explicit)"
        else:
            task.status = "RESULTS_AVAILABLE"
            if auto_register_official:
                maybe_auto_register_official(results, research_task_id=task.id, study_id=task.study_id)
            if extract_from_snippets:
                class _SnippetProvider(ResearchProvider):
                    kind = provider.kind

                    def search(self, query: str, *, query_type: str | None = None):
                        return [
                            ProviderHit(
                                title=r.title,
                                locator=r.url,
                                source_type={
                                    "SMPC": "SMPC",
                                    "PUBLICATION": "PUBLICATION",
                                    "CLINICAL_STUDY": "CLINICAL_STUDY",
                                    "REGULATORY": "REGULATORY",
                                    "GUIDELINE": "REGULATORY",
                                    "REVIEW": "REVIEW",
                                }.get(r.source_type, "OTHER"),
                                text=r.snippet or "",
                                author=r.authors,
                                publication_date=r.publication_date,
                                identifier=r.identifier,
                                metadata=dict(r.raw_metadata or {}),
                            )
                            for r in results
                        ]

                if any((r.snippet or "").strip() for r in results):
                    try:
                        run_research_task(
                            task.id,
                            provider=_SnippetProvider(),
                            context=extras or {},
                            register_sources=True,
                        )
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"EXTRACT_PARTIAL: {exc}")
                        run_log.status = "PARTIAL"

            for fp in ("pk.t_half", "cv_intra", "pk.Tmax"):
                for conf in detect_numeric_conflicts(
                    list_claims(task.id),
                    field_path=fp,
                    research_task_id=task.id,
                    study_id=task.study_id,
                ):
                    if not any(
                        x.field_path == fp and x.status == "OPEN" for x in list_conflicts(task.id)
                    ):
                        put_conflict(conf)

            claims = list_claims(task.id)
            if claims:
                task.status = "REVIEW_REQUIRED"
            run_log.claim_count = len(claims)
            run_log.source_count = len({r.registered_source_id for r in results if r.registered_source_id})

    except ResearchHttpError as exc:
        errors.append(f"{exc.kind}: {exc}")
        run_log.status = "RESEARCH_FAILED"
        task.status = "OPEN"
        task.notes = f"RESEARCH_FAILED: {exc.kind}: {exc}"

    end = _now()
    run_log.end_time = end
    run_log.error_count = len(errors)
    run_log.errors = errors
    run_log.duration_ms = (time.perf_counter() - t0) * 1000
    _RUN_LOGS.append(run_log.to_dict())

    task.updated_at = end
    put_task(task)

    audit_log(
        "SEARCH_COMPLETED",
        study_id=task.study_id,
        task_id=task.id,
        provider=provider.kind,
        query=q.query_text,
        details={
            "result_count": run_log.result_count,
            "claim_count": run_log.claim_count,
            "status": run_log.status,
            "error_count": run_log.error_count,
            # do not log full documents
        },
    )

    return {
        "task": task.to_dict(),
        "query": q.to_dict(),
        "results": [r.to_dict() for r in list_stored_search_results(task.id)],
        "claims": [c.to_dict() for c in list_claims(task.id)],
        "conflicts": [c.to_dict() for c in list_conflicts(task.id)],
        "run_log": run_log.to_dict(),
        "status": run_log.status,
        "errors": errors,
        "study_mutated": False,
        "automatic_verifications": 0,
        "automatic_medical_decisions": 0,
    }


def list_run_logs(task_id: str | None = None) -> list[dict[str, Any]]:
    if task_id:
        return [x for x in _RUN_LOGS if x.get("task_id") == task_id]
    return list(_RUN_LOGS)
