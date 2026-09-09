"""In-memory research evidence store — Phase 15.2."""

from __future__ import annotations

from typing import Any

from app.domain.research_evidence_models import (
    EvidenceConflictRecord,
    RegisteredSource,
    ResearchClaim,
    ResearchCoverage,
    ResearchQuery,
    ResearchTask,
    SourceResult,
)

_TASKS: dict[str, ResearchTask] = {}
_QUERIES: dict[str, ResearchQuery] = {}
_RESULTS: dict[str, SourceResult] = {}
_CLAIMS: dict[str, ResearchClaim] = {}
_CONFLICTS: dict[str, EvidenceConflictRecord] = {}
_SOURCES: dict[str, RegisteredSource] = {}
_BY_STUDY_TASKS: dict[str, list[str]] = {}


def clear_research_evidence_store() -> None:
    _TASKS.clear()
    _QUERIES.clear()
    _RESULTS.clear()
    _CLAIMS.clear()
    _CONFLICTS.clear()
    _SOURCES.clear()
    _BY_STUDY_TASKS.clear()


def put_task(task: ResearchTask) -> ResearchTask:
    _TASKS[task.id] = task
    if task.study_id:
        _BY_STUDY_TASKS.setdefault(task.study_id, [])
        if task.id not in _BY_STUDY_TASKS[task.study_id]:
            _BY_STUDY_TASKS[task.study_id].append(task.id)
    return task


def get_task(task_id: str) -> ResearchTask | None:
    return _TASKS.get(task_id)


def list_tasks(study_id: str) -> list[ResearchTask]:
    ids = _BY_STUDY_TASKS.get(study_id, [])
    return [_TASKS[i] for i in ids if i in _TASKS]


def put_query(q: ResearchQuery) -> ResearchQuery:
    _QUERIES[q.id] = q
    return q


def list_queries(task_id: str) -> list[ResearchQuery]:
    return [q for q in _QUERIES.values() if q.research_task_id == task_id]


def put_result(r: SourceResult) -> SourceResult:
    _RESULTS[r.id] = r
    return r


def list_results(task_id: str) -> list[SourceResult]:
    return [r for r in _RESULTS.values() if r.research_task_id == task_id]


def put_claim(c: ResearchClaim) -> ResearchClaim:
    _CLAIMS[c.id] = c
    return c


def get_claim(claim_id: str) -> ResearchClaim | None:
    return _CLAIMS.get(claim_id) or next(
        (c for c in _CLAIMS.values() if c.claim_id == claim_id), None
    )


def list_claims(task_id: str | None = None, *, study_id: str | None = None) -> list[ResearchClaim]:
    out = list(_CLAIMS.values())
    if task_id:
        out = [c for c in out if c.research_task_id == task_id]
    if study_id:
        out = [c for c in out if c.study_id == study_id]
    return out


def put_conflict(c: EvidenceConflictRecord) -> EvidenceConflictRecord:
    _CONFLICTS[c.id] = c
    return c


def list_conflicts(task_id: str | None = None, *, study_id: str | None = None) -> list[EvidenceConflictRecord]:
    out = list(_CONFLICTS.values())
    if task_id:
        out = [c for c in out if c.research_task_id == task_id]
    if study_id:
        out = [c for c in out if c.study_id == study_id]
    return out


def put_source(s: RegisteredSource) -> RegisteredSource:
    _SOURCES[s.id] = s
    return s


def get_source(source_id: str) -> RegisteredSource | None:
    return _SOURCES.get(source_id)


def list_sources(study_id: str | None = None) -> list[RegisteredSource]:
    if study_id:
        return [s for s in _SOURCES.values() if s.study_id == study_id]
    return list(_SOURCES.values())


def find_source_by_locator_or_id(locator: str | None, identifier: str | None) -> RegisteredSource | None:
    for s in _SOURCES.values():
        if locator and s.locator == locator:
            return s
        if identifier and s.content_hash == identifier:
            return s
        if identifier and identifier in (s.locator or ""):
            return s
    return None


def coverage_for_gap(study_id: str, gap_code: str) -> ResearchCoverage:
    tasks = [t for t in list_tasks(study_id) if t.knowledge_gap_code == gap_code]
    if not tasks:
        return ResearchCoverage(knowledge_gap_code=gap_code, study_id=study_id, status="NO_TASK")
    task = tasks[0]
    results = list_results(task.id)
    claims = list_claims(task.id)
    verified = [c for c in claims if c.verification_status == "VERIFIED"]
    usable = [c for c in claims if c.usability == "USABLE_FOR_DECISION"]
    status = task.status
    if claims and not verified:
        status = "REVIEW_REQUIRED"
    if verified and usable and task.status == "COMPLETED":
        status = "COMPLETED"
    return ResearchCoverage(
        knowledge_gap_code=gap_code,
        task_present=True,
        search_done=bool(results) or task.status in {
            "RESULTS_AVAILABLE", "REVIEW_REQUIRED", "COMPLETED"
        },
        sources_count=len(results),
        candidate_claims=len(claims),
        verified_claims=len(verified),
        usable_evidence=len(usable),
        status=status,
        study_id=study_id,
    )


def research_center_summary(study_id: str) -> dict[str, Any]:
    tasks = list_tasks(study_id)
    claims = list_claims(study_id=study_id)
    return {
        "study_id": study_id,
        "tasks": [t.to_dict() for t in tasks],
        "task_count": len(tasks),
        "candidate_claims": len(claims),
        "verified_claims": sum(1 for c in claims if c.verification_status == "VERIFIED"),
        "usable_evidence": sum(1 for c in claims if c.usability == "USABLE_FOR_DECISION"),
        "conflicts": [c.to_dict() for c in list_conflicts(study_id=study_id)],
        "study_mutated": False,
        "automatic_medical_decisions": 0,
    }
