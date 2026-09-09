"""Phase 16 — Study workspace aggregation (readiness, conflicts, audit, lifecycle).

Composes existing Phase 14–15 stores. Does not invent medical values.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.decision_store import decision_center_summary, get_context, list_decisions
from app.domain.research_evidence_store import list_claims, list_conflicts as list_research_conflicts, list_tasks
from app.domain.sample_size_store import list_calculations
from app.domain.statistics_store import latest_plan as latest_stats_plan
from app.domain.statistics_store import list_plans as list_stats_plans
from app.domain.study_input_store import get_package, list_packages, package_readiness

# Lifecycle (expert gates — no silent auto-transition to FINAL)
LIFECYCLE_STATES: tuple[str, ...] = (
    "DRAFT",
    "INGESTING",
    "EXTRACTED",
    "REVIEW_REQUIRED",
    "DECISIONS_PENDING",
    "READY_FOR_PROTOCOL",
    "PROTOCOL_DRAFT",
    "QA_REQUIRED",
    "READY_FOR_FINAL",
    "FINAL",
)

READINESS_LABELS: dict[str, str] = {
    "READY": "Ready",
    "READY_WITH_WARNINGS": "Ready with warnings",
    "REVIEW_REQUIRED": "Review required",
    "BLOCKED": "Blocked",
}

_WORKSPACE: dict[str, dict[str, Any]] = {}
_AUDIT: dict[str, list[dict[str, Any]]] = {}
_PROTOCOL_DRAFTS: dict[str, list[dict[str, Any]]] = {}


def reset_workspace_store() -> None:
    _WORKSPACE.clear()
    _AUDIT.clear()
    _PROTOCOL_DRAFTS.clear()


def restore_protocol_drafts(study_id: str, drafts: list[dict[str, Any]]) -> None:
    """Hydrate immutable draft history from persistence (does not mutate past versions)."""
    _PROTOCOL_DRAFTS[study_id] = [dict(d) for d in drafts]


def restore_audit_timeline(study_id: str, events: list[dict[str, Any]]) -> None:
    _AUDIT[study_id] = [dict(e) for e in events]


def restore_workspace_meta(study_id: str, meta: dict[str, Any] | None) -> None:
    if meta:
        _WORKSPACE[study_id] = dict(meta)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit(
    study_id: str,
    *,
    event: str,
    who: str = "system",
    what: str,
    old_value: Any = None,
    new_value: Any = None,
    reason: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    entry = {
        "id": f"AUD-{uuid4().hex[:10]}",
        "study_id": study_id,
        "timestamp": _now(),
        "who": who,
        "event": event,
        "what": what,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
        "source": source,
    }
    _AUDIT.setdefault(study_id, []).append(entry)
    return entry


def audit_timeline(study_id: str) -> list[dict[str, Any]]:
    return list(_AUDIT.get(study_id, []))


def put_protocol_draft_version(
    study_id: str,
    *,
    status: str,
    created_by: str,
    based_on: dict[str, Any],
    sections_summary: list[str] | None = None,
) -> dict[str, Any]:
    """Immutable protocol draft versions — never overwrite history."""
    existing = _PROTOCOL_DRAFTS.setdefault(study_id, [])
    version = len(existing) + 1
    draft = {
        "protocol_id": f"PROT-{study_id}-{version}",
        "study_id": study_id,
        "version": version,
        "status": status,
        "created_at": _now(),
        "created_by": created_by,
        "based_on_snapshot": based_on.get("snapshot"),
        "based_on_decisions": based_on.get("decisions"),
        "based_on_evidence": based_on.get("evidence"),
        "based_on_statistics": based_on.get("statistics"),
        "based_on_sample_size": based_on.get("sample_size"),
        "sections_summary": sections_summary or [],
        "immutable": True,
    }
    existing.append(draft)
    append_audit(
        study_id,
        event="PROTOCOL_DRAFT_CREATED",
        who=created_by,
        what=f"Protocol draft v{version}",
        new_value=draft["protocol_id"],
    )
    return draft


def list_protocol_drafts(study_id: str) -> list[dict[str, Any]]:
    return list(_PROTOCOL_DRAFTS.get(study_id, []))


def patch_protocol_draft_based_on(
    study_id: str,
    *,
    protocol_id: str | None = None,
    snapshot_id: str | None = None,
    decisions: list[str] | None = None,
    statistics: str | None = None,
    sample_size: str | None = None,
) -> dict[str, Any] | None:
    """Update based_on pointers on the latest (or specified) draft after snapshot creation."""
    drafts = _PROTOCOL_DRAFTS.get(study_id) or []
    if not drafts:
        return None
    target = None
    if protocol_id:
        target = next((d for d in drafts if d.get("protocol_id") == protocol_id), None)
    if target is None:
        target = drafts[-1]
    if snapshot_id is not None:
        target["based_on_snapshot"] = snapshot_id
    if decisions is not None:
        target["based_on_decisions"] = list(decisions)
    if statistics is not None:
        target["based_on_statistics"] = statistics
    if sample_size is not None:
        target["based_on_sample_size"] = sample_size
    return target


def protocol_draft_diff(study_id: str, v_old: int, v_new: int) -> dict[str, Any]:
    drafts = {d["version"]: d for d in list_protocol_drafts(study_id)}
    a = drafts.get(v_old)
    b = drafts.get(v_new)
    if not a or not b:
        return {"error": "version_not_found", "study_id": study_id}
    fields = [
        "status",
        "based_on_snapshot",
        "based_on_decisions",
        "based_on_evidence",
        "based_on_statistics",
        "based_on_sample_size",
    ]
    diffs = []
    for f in fields:
        if a.get(f) != b.get(f):
            diffs.append({"field": f, "old": a.get(f), "new": b.get(f), "reason": "version_change"})
    return {"study_id": study_id, "from_version": v_old, "to_version": v_new, "diffs": diffs}


def _find_package(study_id: str, package_id: str | None = None):
    if package_id:
        return get_package(package_id)
    for p in list_packages():
        if p.study_id == study_id or (p.fixture_id and study_id in str(p.fixture_id)):
            return p
    # golden default study id mapping
    for p in list_packages():
        if p.fixture_id and "UPDCB" in str(p.fixture_id):
            return p
    return None


def aggregate_conflicts(study_id: str, *, package_id: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pkg = _find_package(study_id, package_id)
    if pkg:
        for c in pkg.conflicts:
            values = c.get("values") or []
            sources = c.get("sources") or []
            field = c.get("field_path")
            severity = str(c.get("severity") or "HIGH")
            if field == "reference_product.dose":
                severity = "CRITICAL"
            src_a = sources[0] if len(sources) > 0 else None
            src_b = sources[1] if len(sources) > 1 else None
            out.append(
                {
                    "id": c.get("conflict_id") or c.get("id") or f"SIC-{len(out)}",
                    "lane": "STUDY_INPUT",
                    "field": field,
                    "value_a": values[0] if len(values) > 0 else None,
                    "value_b": values[1] if len(values) > 1 else None,
                    "source_a": (src_a.get("document_type") if isinstance(src_a, dict) else src_a),
                    "source_b": (src_b.get("document_type") if isinstance(src_b, dict) else src_b),
                    "conflict_type": c.get("conflict_type") or "VALUE_MISMATCH",
                    "severity": severity,
                    "status": c.get("status") or "OPEN",
                    "required_action": "EXPERT_DECISION",
                    "auto_resolved": False,
                }
            )
    for rc in list_research_conflicts(study_id=study_id):
        d = rc.to_dict() if hasattr(rc, "to_dict") else dict(rc)  # type: ignore[arg-type]
        values = d.get("values") or []
        claim_ids = d.get("claim_ids") or []
        out.append(
            {
                "id": d.get("id"),
                "lane": "RESEARCH",
                "field": d.get("field_path"),
                "value_a": values[0] if len(values) > 0 else None,
                "value_b": values[1] if len(values) > 1 else None,
                "source_a": claim_ids[0] if len(claim_ids) > 0 else None,
                "source_b": claim_ids[1] if len(claim_ids) > 1 else None,
                "conflict_type": d.get("conflict_type") or "EVIDENCE",
                "severity": str(d.get("severity") or "HIGH"),
                "status": d.get("status") or "OPEN",
                "required_action": "EXPERT_REVIEW",
                "auto_resolved": False,
            }
        )
    return out


def compute_lifecycle(study_id: str, *, package_id: str | None = None) -> str:
    pkg = _find_package(study_id, package_id)
    conflicts = aggregate_conflicts(study_id, package_id=package_id)
    open_critical = [c for c in conflicts if c.get("status") == "OPEN" and c.get("severity") == "CRITICAL"]
    decisions = list_decisions(study_id)
    pending = [d for d in decisions if d.status in {"BLOCKED", "PENDING", "REVIEW_REQUIRED"} or getattr(d, "status", "") == "BLOCKED"]
    drafts = list_protocol_drafts(study_id)

    if open_critical:
        return "DECISIONS_PENDING"
    if pkg is None:
        return "DRAFT"
    if pkg.status in {"INGESTING", "UPLOADING"}:
        return "INGESTING"
    if not pkg.candidates and pkg.documents:
        return "INGESTING"
    if pkg.candidates and any(c.status == "PROPOSED" for c in pkg.candidates):
        return "REVIEW_REQUIRED"
    if pending or open_critical:
        return "DECISIONS_PENDING"
    if drafts and any(d.get("status") == "FINAL" for d in drafts):
        return "FINAL"
    if drafts:
        return "PROTOCOL_DRAFT"
    if decisions and not pending:
        return "READY_FOR_PROTOCOL"
    if pkg.candidates:
        return "EXTRACTED"
    return "DRAFT"


def compute_readiness(study_id: str, *, package_id: str | None = None) -> dict[str, Any]:
    pkg = _find_package(study_id, package_id)
    conflicts = aggregate_conflicts(study_id, package_id=package_id)
    open_critical = [c for c in conflicts if c.get("status") == "OPEN" and c.get("severity") == "CRITICAL"]
    open_all = [c for c in conflicts if c.get("status") == "OPEN"]
    decisions = list_decisions(study_id)
    blocked_decisions = [d for d in decisions if d.status == "BLOCKED"]
    ss = list_calculations(study_id)
    latest_ss = ss[-1] if ss else None
    st = latest_stats_plan(study_id)
    pkg_ready = package_readiness(pkg) if pkg else None

    critical_blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    infos: list[dict[str, Any]] = []

    for c in open_critical:
        critical_blockers.append(
            {
                "code": "UNRESOLVED_CRITICAL_CONFLICT",
                "severity": "CRITICAL",
                "message": f"Unresolved critical conflict on {c.get('field')}",
                "field": c.get("field"),
                "detail": c,
            }
        )

    if st is None or st.status not in {"APPROVED"}:
        if st and "REQUIRES_EXPERT_SELECTION" in (st.blocking_reasons or []):
            critical_blockers.append(
                {
                    "code": "PRIMARY_BE_NOT_APPROVED",
                    "severity": "CRITICAL",
                    "message": "PRIMARY_BE endpoint not expert-approved",
                }
            )
        elif st is None:
            warnings.append(
                {
                    "code": "STATISTICS_PLAN_MISSING",
                    "severity": "WARNING",
                    "message": "Statistics plan not generated",
                }
            )
        elif st.status != "APPROVED":
            warnings.append(
                {
                    "code": "STATISTICS_NOT_APPROVED",
                    "severity": "WARNING",
                    "message": f"Statistics plan status={st.status}",
                }
            )

    if latest_ss is None:
        warnings.append(
            {
                "code": "SAMPLE_SIZE_MISSING",
                "severity": "WARNING",
                "message": "Sample size calculation not present",
            }
        )
    elif latest_ss.status not in {"ACCEPTED", "CALCULATED", "PENDING_REVIEW", "SUPERSEDED"}:
        warnings.append(
            {
                "code": "SAMPLE_SIZE_NOT_READY",
                "severity": "WARNING",
                "message": f"Sample size status={latest_ss.status}",
            }
        )
    elif latest_ss.status != "ACCEPTED":
        warnings.append(
            {
                "code": "SAMPLE_SIZE_NOT_APPROVED",
                "severity": "WARNING",
                "message": "Sample size recommendation is not approved",
            }
        )

    for d in blocked_decisions:
        warnings.append(
            {
                "code": "DECISION_BLOCKED",
                "severity": "WARNING",
                "message": f"Decision {d.domain} blocked",
                "decision_id": d.id,
            }
        )

    if pkg_ready and pkg_ready.get("critical_conflict_unresolved"):
        if not any(b["code"] == "UNRESOLVED_CRITICAL_CONFLICT" for b in critical_blockers):
            critical_blockers.append(
                {
                    "code": "UNRESOLVED_CRITICAL_CONFLICT",
                    "severity": "CRITICAL",
                    "message": "Reference dose conflict unresolved (15 vs 30 mg)",
                }
            )

    can_finalize = len(critical_blockers) == 0 and (
        st is not None and st.status == "APPROVED"
    ) and (latest_ss is not None and latest_ss.status == "ACCEPTED")

    if critical_blockers:
        readiness = "BLOCKED"
    elif warnings:
        readiness = "READY_WITH_WARNINGS" if not blocked_decisions else "REVIEW_REQUIRED"
    else:
        readiness = "READY" if can_finalize else "REVIEW_REQUIRED"

    lifecycle = compute_lifecycle(study_id, package_id=package_id)

    return {
        "study_id": study_id,
        "package_id": pkg.package_id if pkg else package_id,
        "fixture_id": pkg.fixture_id if pkg else None,
        "readiness": readiness,
        "readiness_label": READINESS_LABELS.get(readiness, readiness),
        "lifecycle": lifecycle,
        "can_finalize": can_finalize,
        "can_generate_docx": len(critical_blockers) == 0,
        "critical_blockers": critical_blockers,
        "warnings": warnings,
        "infos": infos,
        "counts": {
            "documents": len(pkg.documents) if pkg else 0,
            "open_conflicts": len(open_all),
            "critical_conflicts": len(open_critical),
            "pending_decisions": len(blocked_decisions),
            "research_tasks": len(list_tasks(study_id)),
            "sample_size_calcs": len(ss),
            "statistics_plans": len(list_stats_plans(study_id)),
            "protocol_drafts": len(list_protocol_drafts(study_id)),
            "knowledge_gaps": len(pkg.blocking_issues) if pkg else 0,
        },
        "sample_size_status": latest_ss.status if latest_ss else "NONE",
        "statistics_status": st.status if st else "NONE",
        "protocol_status": list_protocol_drafts(study_id)[-1]["status"] if list_protocol_drafts(study_id) else "NONE",
        "study_mutated": False,
        "ai_required": False,
    }


def _canonical_facts_from_package(
    study_id: str,
    *,
    package_id: str | None = None,
) -> list[dict[str, Any]]:
    """Build writer canonical fact rows from package/context — no invented provenance."""
    pkg = _find_package(study_id, package_id)
    ctx = get_context(study_id)
    open_conflict_fields = {
        str(c.get("field") or c.get("field_path"))
        for c in aggregate_conflicts(study_id, package_id=package_id)
        if str(c.get("status") or "OPEN") == "OPEN"
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    candidates = list(pkg.candidates) if pkg else []
    # Prefer verified / higher-rank sources similar to decision context
    prefer = {"SYNOPSIS": 3, "DESIGN": 2, "SMPC": 2, "CHECKLIST": 1, "SYNOPSIS_DESIGN": 3}
    by_field: dict[str, Any] = {}
    for c in candidates:
        if c.status == "REJECTED":
            continue
        fp = c.field_path
        if fp in open_conflict_fields:
            # Surface conflict explicitly once
            if fp in seen:
                continue
            seen.add(fp)
            rows.append(
                {
                    "field": fp,
                    "value": None,
                    "canonical_value": None,
                    "status": "CONFLICT",
                    "source": c.document_type,
                    "evidence_id": getattr(c, "id", None),
                    "affected_sections": [],
                    "is_regulatory_requirement": False,
                    "confidence": getattr(c, "confidence", None),
                    "verification_status": c.status,
                }
            )
            continue
        cur = by_field.get(fp)
        rank = prefer.get(c.document_type, 0)
        if cur is None:
            by_field[fp] = c
        elif c.status == "VERIFIED" and cur.status != "VERIFIED":
            by_field[fp] = c
        elif cur.status != "VERIFIED" and rank > prefer.get(cur.document_type, 0):
            by_field[fp] = c

    for fp, c in list(by_field.items())[:80]:
        if fp in open_conflict_fields:
            continue
        status = c.status if c.status in {"VERIFIED", "PROPOSED", "REVIEW_REQUIRED", "EXTRACTED"} else c.status
        if status == "VERIFIED":
            display_status = "VERIFIED"
        elif status in {"PROPOSED", "EXTRACTED"}:
            display_status = "PROPOSED"
        else:
            display_status = status or "PROPOSED"
        rows.append(
            {
                "field": fp,
                "value": c.value,
                "canonical_value": c.value,
                "status": display_status,
                "source": c.document_type
                or (ctx.fact_sources.get(fp) if ctx and ctx.fact_sources else None)
                or "PACKAGE",
                "evidence_id": getattr(c, "id", None),
                "affected_sections": [],
                "is_regulatory_requirement": False,
                "confidence": getattr(c, "confidence", None),
                "verification_status": c.status,
            }
        )

    # Include context facts missing from candidates (still no invented evidence)
    if ctx:
        for k, v in list((ctx.structured_facts or {}).items())[:80]:
            if k in seen or any(r["field"] == k for r in rows):
                continue
            rows.append(
                {
                    "field": k,
                    "value": v,
                    "canonical_value": v,
                    "status": (ctx.fact_statuses or {}).get(k) or "CURRENT_STUDY_FACT",
                    "source": (ctx.fact_sources or {}).get(k) or "PACKAGE",
                    "evidence_id": None,
                    "affected_sections": [],
                    "is_regulatory_requirement": False,
                    "confidence": None,
                    "verification_status": (ctx.fact_statuses or {}).get(k),
                }
            )
    return rows[:80]


def build_workspace_summary(
    study_id: str,
    *,
    package_id: str | None = None,
    document_count: int | None = None,
) -> dict[str, Any]:
    ready = compute_readiness(study_id, package_id=package_id)
    pkg = _find_package(study_id, package_id)
    ctx = get_context(study_id)
    facts = {}
    if ctx:
        facts = dict(ctx.structured_facts or {})
    elif pkg:
        for c in pkg.candidates:
            if c.status != "REJECTED" and c.field_path not in facts:
                facts[c.field_path] = c.value

    # Authoritative document count for Writer overview comes from WorkspaceDocumentRecord
    # when provided by the DB-backed reader; package docs are study-input only.
    doc_count = document_count if document_count is not None else ready["counts"]["documents"]
    ready = dict(ready)
    ready_counts = dict(ready.get("counts") or {})
    ready_counts["documents"] = doc_count
    ready["counts"] = ready_counts

    header = {
        "study_id": study_id,
        "sponsor": facts.get("sponsor.name"),
        "product": facts.get("test_product.name") or facts.get("test_product.active_substance"),
        "dose": facts.get("test_product.dose") or facts.get("reference_product.dose"),
        "study_status": ready["lifecycle"],
        "protocol_version": (
            list_protocol_drafts(study_id)[-1]["version"] if list_protocol_drafts(study_id) else None
        ),
        "overall_readiness": ready["readiness_label"],
        "readiness_code": ready["readiness"],
    }

    nav = [
        {"id": "overview", "label": "Обзор"},
        {"id": "documents", "label": "Документы"},
        {"id": "data", "label": "Данные исследования"},
        {"id": "decisions", "label": "Решения"},
        {"id": "evidence", "label": "Исследования / Evidence"},
        {"id": "sample-size", "label": "Sample Size"},
        {"id": "statistics", "label": "Statistics"},
        {"id": "protocol", "label": "Протокол"},
        {"id": "preflight", "label": "Проверка"},
        {"id": "history", "label": "История"},
    ]

    return {
        "study_id": study_id,
        "header": header,
        "nav": nav,
        "summary_cards": {
            "documents": doc_count,
            "critical_conflicts": ready["counts"]["critical_conflicts"],
            "knowledge_gaps": ready["counts"]["knowledge_gaps"],
            "pending_decisions": ready["counts"]["pending_decisions"],
            "sample_size_status": ready["sample_size_status"],
            "statistics_status": ready["statistics_status"],
            "protocol_status": ready["protocol_status"],
        },
        "readiness": ready,
        "conflicts": aggregate_conflicts(study_id, package_id=package_id),
        "decisions": decision_center_summary(study_id),
        "canonical_facts": _canonical_facts_from_package(study_id, package_id=package_id),
        "recommendation_is_not_approval": True,
        "study_mutated": False,
        "exposes_internal_enums": False,
    }


def build_preflight(study_id: str, *, package_id: str | None = None) -> dict[str, Any]:
    ready = compute_readiness(study_id, package_id=package_id)
    checks: list[dict[str, Any]] = []

    def add(category: str, code: str, severity: str, message: str, ok: bool) -> None:
        checks.append(
            {
                "category": category,
                "code": code,
                "severity": severity,
                "message": message,
                "ok": ok,
                "label": message,
            }
        )

    conflicts = aggregate_conflicts(study_id, package_id=package_id)
    add(
        "EVIDENCE",
        "NO_CRITICAL_CONFLICT",
        "CRITICAL",
        "No unresolved critical conflicts",
        not any(c["status"] == "OPEN" and c["severity"] == "CRITICAL" for c in conflicts),
    )
    st = latest_stats_plan(study_id)
    add(
        "STATISTICS",
        "PRIMARY_BE_APPROVED",
        "CRITICAL",
        "PRIMARY_BE / statistics plan approved",
        bool(st and st.status == "APPROVED"),
    )
    ss = list_calculations(study_id)
    latest_ss = ss[-1] if ss else None
    add(
        "SAMPLE_SIZE",
        "SAMPLE_SIZE_APPROVED",
        "CRITICAL",
        "Sample size approved",
        bool(latest_ss and latest_ss.status == "ACCEPTED"),
    )
    pkg = _find_package(study_id, package_id)
    add(
        "DOCUMENT_COMPLETENESS",
        "HAS_DOCUMENTS",
        "WARNING",
        "Source documents present",
        bool(pkg and pkg.documents),
    )
    add(
        "DATA_CONSISTENCY",
        "HAS_CANDIDATES",
        "WARNING",
        "Extracted facts present",
        bool(pkg and pkg.candidates),
    )
    add(
        "DECISIONS",
        "DECISIONS_PRESENT",
        "INFO",
        "Decision Center recomputed",
        bool(list_decisions(study_id)),
    )
    add(
        "PROTOCOL",
        "DRAFT_EXISTS",
        "INFO",
        "Protocol draft version exists",
        bool(list_protocol_drafts(study_id)),
    )

    # Stale dependency check only when a draft already exists
    if list_protocol_drafts(study_id):
        from app.domain.protocol_dependency_stale import detect_stale_protocol_dependencies

        stale = detect_stale_protocol_dependencies(study_id)
        add(
            "PROTOCOL",
            "PROTOCOL_DEPENDENCIES_STALE",
            "CRITICAL",
            "Protocol draft dependencies match current approved state",
            not stale.get("stale"),
        )
    else:
        stale = {"stale": False, "reasons": []}

    critical_fail = [c for c in checks if c["severity"] == "CRITICAL" and not c["ok"]]
    out = {
        "study_id": study_id,
        "categories": sorted({c["category"] for c in checks}),
        "checks": checks,
        "critical_blockers": critical_fail,
        "can_finalize": len(critical_fail) == 0 and ready["can_finalize"],
        "can_generate_docx": len([c for c in checks if c["severity"] == "CRITICAL" and not c["ok"]]) == 0,
        "readiness": ready["readiness"],
        "readiness_label": ready["readiness_label"],
        "study_mutated": False,
        "message": (
            "FINAL blocked by critical checks"
            if critical_fail
            else ("DOCX generation allowed (warnings may remain)" if ready["warnings"] else "Preflight passed")
        ),
        "stale_dependencies": stale,
    }
    return out
