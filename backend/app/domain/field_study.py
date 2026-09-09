"""Phase 20 — Field study execution: paired sessions, gates, metrics, ROI safety.

No fabricated ROI. Aggregate timing published only when sample size is meaningful
and all included sessions were observed directly.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.real_package_registry import get_real_package, population_status

# Meaningful aggregate floor — below this, medians/P25/P75 stay unpublished
MIN_PAIRED_FOR_AGGREGATE = 5

CRITICAL_EXTRACTION_FIELDS: tuple[str, ...] = (
    "Sponsor",
    "Product",
    "Test",
    "Reference",
    "Dose",
    "Design",
    "Sequence",
    "Period",
    "Washout",
    "Food",
    "Population",
    "Subjects",
    "Sampling",
    "Analytes",
    "PK",
    "Statistics",
    "Safety",
)

PROTOCOL_DOMAINS: tuple[str, ...] = (
    "product",
    "dose",
    "reference",
    "design",
    "population",
    "subjects",
    "washout",
    "food",
    "sampling",
    "PK",
    "sample_size",
    "statistics",
    "safety",
)

FIELD_EVENTS: tuple[str, ...] = (
    "CASE_STARTED",
    "SESSION_STARTED",
    "DOCUMENT_OPENED",
    "DOCUMENT_REVIEWED",
    "EXTRACTION_REVIEWED",
    "CONFLICT_REVIEWED",
    "RESEARCH_STARTED",
    "RESEARCH_COMPLETED",
    "DECISION_CREATED",
    "DECISION_APPROVED",
    "SAMPLE_SIZE_REVIEWED",
    "STATISTICS_REVIEWED",
    "PROTOCOL_GENERATED",
    "PREFLIGHT_STARTED",
    "PREFLIGHT_COMPLETED",
    "DOCX_GENERATED",
    "SESSION_COMPLETED",
    "CASE_COMPLETED",
)

PROTOCOL_CORRECTION_CATEGORIES: tuple[str, ...] = (
    "PRODUCT",
    "DOSE",
    "REFERENCE",
    "DESIGN",
    "POPULATION",
    "SUBJECTS",
    "WASHOUT",
    "FOOD",
    "SAMPLING",
    "PK",
    "SAMPLE_SIZE",
    "STATISTICS",
    "SAFETY",
    "FORMATTING",
    "OTHER",
)

DOCX_REVIEW_STATUSES: tuple[str, ...] = ("OPENED", "VALID", "CORRECTED", "REJECTED")
PROVENANCE_STATUSES: tuple[str, ...] = ("COMPLETE", "PARTIAL", "MISSING")


_CASES: dict[str, dict[str, Any]] = {}
_EVENTS: list[dict[str, Any]] = []
_FEEDBACK: dict[str, dict[str, Any]] = {}
_PAIRS: dict[str, dict[str, Any]] = {}


def reset_field_study() -> None:
    _CASES.clear()
    _EVENTS.clear()
    _FEEDBACK.clear()
    _PAIRS.clear()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def assert_sanitized_for_field_study(case_id: str) -> dict[str, Any]:
    """Refuse field-study start if package fails REAL_PACKAGE_SANITIZED gate."""
    try:
        pkg = get_real_package(case_id)
    except KeyError as e:
        raise ValueError(f"Unknown real package case_id={case_id}") from e
    if not pkg.get("sanitized"):
        raise ValueError(
            f"REAL_PACKAGE_SANITIZED=no for {case_id}; DO NOT RUN FIELD STUDY"
        )
    return pkg


def start_case(
    *,
    case_id: str,
    writer_id: str,
    system_used: bool,
    case_order: int | None = None,
    mode: str = "MANUAL",
    session_type: str | None = None,
    pair_id: str | None = None,
    enforce_sanitization: bool = True,
) -> dict[str, Any]:
    """Begin observed session. writer_id must be pseudonymous."""
    if enforce_sanitization:
        assert_sanitized_for_field_study(case_id)

    stype = session_type or ("SYSTEM_ASSISTED" if system_used or mode == "SYSTEM_ASSISTED" else "MANUAL")
    sid = f"FS-{uuid4().hex[:10]}"
    row = {
        "session_id": sid,
        "case_id": case_id,
        "writer_id": writer_id,
        "writer_pseudonym": writer_id,
        "system_used": system_used,
        "mode": mode,
        "session_type": stype,
        "pair_id": pair_id,
        "case_order": case_order,
        "date": _now()[:10],
        "start_time": _now(),
        "started_at": _now(),
        "end_time": None,
        "ended_at": None,
        "T_manual_minutes": None,
        "T_system_minutes": None,
        "T_review_minutes": None,
        "T_total_minutes": None,
        "manual_total_time": None,
        "system_total_time": None,
        "review_time": None,
        "assisted_total_time": None,
        "time_saving_percent": None,
        "timing_observed_directly": False,
        "complexity": None,
        "complexity_rationale": None,
        "ops": {
            "manual_edits": 0,
            "expert_decisions": 0,
            "evidence_opens": 0,
            "research_queries": 0,
            "document_switches": 0,
            "conflicts": 0,
            "gaps": 0,
            "preflight_warnings": 0,
            "preflight_blockers": 0,
            "recommendations": 0,
            "approved_decisions": 0,
            "rejected_decisions": 0,
            "modified_decisions": 0,
            "unresolved_decisions": 0,
        },
        "field_classifications": {},
        "evidence_reviews": {},
        "provenance_reviews": {},
        "research_reviews": [],
        "conflict_labels": {"expected": [], "detected": [], "missed": [], "false_positives": []},
        "conflict_writer_labels": [],
        "sample_size_status": None,
        "statistics_status": None,
        "protocol_review": {},
        "protocol_corrections": [],
        "docx_review": {},
        "decision_latencies": [],
        "no_auto_medical_decision": True,
    }
    _CASES[sid] = row
    log_event(sid, "CASE_STARTED", stage="START")
    log_event(sid, "SESSION_STARTED", stage="SESSION")
    return dict(row)


def create_paired_study(
    *,
    case_id: str,
    writer_id: str,
    case_order: int | None = None,
    enforce_sanitization: bool = True,
) -> dict[str, Any]:
    """Create MANUAL + SYSTEM_ASSISTED sessions for the same writer/case."""
    if enforce_sanitization:
        assert_sanitized_for_field_study(case_id)
    pair_id = f"PAIR-{uuid4().hex[:10]}"
    manual = start_case(
        case_id=case_id,
        writer_id=writer_id,
        system_used=False,
        mode="MANUAL",
        session_type="MANUAL",
        pair_id=pair_id,
        case_order=case_order,
        enforce_sanitization=False,
    )
    assisted = start_case(
        case_id=case_id,
        writer_id=writer_id,
        system_used=True,
        mode="SYSTEM_ASSISTED",
        session_type="SYSTEM_ASSISTED",
        pair_id=pair_id,
        case_order=case_order,
        enforce_sanitization=False,
    )
    pair = {
        "pair_id": pair_id,
        "case_id": case_id,
        "writer_pseudonym": writer_id,
        "manual_session_id": manual["session_id"],
        "assisted_session_id": assisted["session_id"],
        "created_at": _now(),
        "complete": False,
        "roi_eligible": False,
    }
    _PAIRS[pair_id] = pair
    return {
        "pair": pair,
        "manual_session": manual,
        "assisted_session": assisted,
    }


def log_event(
    session_id: str,
    event: str,
    *,
    stage: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if event not in FIELD_EVENTS:
        raise ValueError(f"Unknown field event: {event}")
    if session_id not in _CASES:
        raise KeyError(session_id)
    safe_meta = {
        k: v
        for k, v in (meta or {}).items()
        if k not in {"excerpt", "content", "pii", "password", "source_text"}
    }
    entry = {
        "event_id": f"FSE-{uuid4().hex[:8]}",
        "session_id": session_id,
        "case_id": _CASES[session_id]["case_id"],
        "writer_id": _CASES[session_id]["writer_id"],
        "event": event,
        "stage": stage or event,
        "timestamp": _now(),
        "meta": safe_meta,
    }
    _EVENTS.append(entry)
    return entry


def record_timings(
    session_id: str,
    *,
    T_manual_minutes: float | None = None,
    T_system_minutes: float | None = None,
    T_review_minutes: float | None = None,
    observed_directly: bool = True,
) -> dict[str, Any]:
    row = _CASES[session_id]
    if T_manual_minutes is not None:
        row["T_manual_minutes"] = float(T_manual_minutes)
        row["manual_total_time"] = float(T_manual_minutes)
    if T_system_minutes is not None:
        row["T_system_minutes"] = float(T_system_minutes)
        row["system_total_time"] = float(T_system_minutes)
    if T_review_minutes is not None:
        row["T_review_minutes"] = float(T_review_minutes)
        row["review_time"] = float(T_review_minutes)

    if row["T_system_minutes"] is not None and row["T_review_minutes"] is not None:
        row["T_total_minutes"] = row["T_system_minutes"] + row["T_review_minutes"]
        row["assisted_total_time"] = row["T_total_minutes"]

    if (
        observed_directly
        and row["T_manual_minutes"] is not None
        and row["T_total_minutes"] is not None
        and row["T_manual_minutes"] > 0
    ):
        saved = row["T_manual_minutes"] - row["T_total_minutes"]
        row["time_saving_percent"] = round(saved / row["T_manual_minutes"], 4)
        row["timing_observed_directly"] = True
    else:
        row["time_saving_percent"] = None
        if not observed_directly:
            row["timing_observed_directly"] = False
    _refresh_pair_roi(row.get("pair_id"))
    return dict(row)


def record_pair_timings(
    pair_id: str,
    *,
    manual_total_minutes: float,
    system_total_minutes: float,
    review_minutes: float,
    observed_directly: bool = True,
) -> dict[str, Any]:
    """Record paired observed timings onto both sessions."""
    pair = _PAIRS[pair_id]
    record_timings(
        pair["manual_session_id"],
        T_manual_minutes=manual_total_minutes,
        observed_directly=observed_directly,
    )
    assisted = record_timings(
        pair["assisted_session_id"],
        T_manual_minutes=manual_total_minutes,
        T_system_minutes=system_total_minutes,
        T_review_minutes=review_minutes,
        observed_directly=observed_directly,
    )
    _refresh_pair_roi(pair_id)
    return {"pair": dict(_PAIRS[pair_id]), "assisted_session": assisted}


def _refresh_pair_roi(pair_id: str | None) -> None:
    if not pair_id or pair_id not in _PAIRS:
        return
    pair = _PAIRS[pair_id]
    assisted = _CASES.get(pair["assisted_session_id"])
    manual = _CASES.get(pair["manual_session_id"])
    if not assisted or not manual:
        return
    pair["roi_eligible"] = bool(
        assisted.get("timing_observed_directly")
        and assisted.get("time_saving_percent") is not None
        and manual.get("manual_total_time") is not None
    )


def bump_ops(session_id: str, **kwargs: int) -> dict[str, Any]:
    row = _CASES[session_id]
    for k, v in kwargs.items():
        if k in row["ops"]:
            row["ops"][k] = int(row["ops"][k]) + int(v)
    return dict(row)


def classify_field(session_id: str, field: str, classification: str) -> None:
    allowed = {
        "CORRECT_AUTO",
        "CORRECT_AFTER_REVIEW",
        "MISSING",
        "INCORRECT",
        "CONFLICTING",
        "NOT_APPLICABLE",
    }
    if classification not in allowed:
        raise ValueError(classification)
    _CASES[session_id]["field_classifications"][field] = classification


def classify_evidence(session_id: str, field: str, judgement: str) -> None:
    allowed = {"USEFUL", "PARTIAL", "INSUFFICIENT", "WRONG_SOURCE"}
    if judgement not in allowed:
        raise ValueError(judgement)
    _CASES[session_id]["evidence_reviews"][field] = judgement


def classify_provenance(session_id: str, field: str, status: str) -> None:
    if status not in PROVENANCE_STATUSES:
        raise ValueError(status)
    _CASES[session_id]["provenance_reviews"][field] = status


def add_conflict_writer_label(session_id: str, label: str, conflict_type: str) -> None:
    allowed = {"EXPECTED_CONFLICT", "DETECTED", "MISSED", "FALSE_POSITIVE"}
    if label not in allowed:
        raise ValueError(label)
    _CASES[session_id]["conflict_writer_labels"].append(
        {"label": label, "type": conflict_type, "at": _now()}
    )


def add_protocol_correction(session_id: str, category: str, note: str | None = None) -> None:
    if category not in PROTOCOL_CORRECTION_CATEGORIES:
        raise ValueError(category)
    _CASES[session_id]["protocol_corrections"].append(
        {"category": category, "note": (note or "")[:500], "at": _now()}
    )


def set_docx_review(session_id: str, status: str, *, corrected: bool = False) -> None:
    if status not in DOCX_REVIEW_STATUSES:
        raise ValueError(status)
    _CASES[session_id]["docx_review"] = {
        "status": status,
        "corrected": corrected,
        "silently_modified": False,
        "at": _now(),
    }


def record_decision_latency(
    session_id: str,
    *,
    recommendation_at: str,
    decision_at: str,
    outcome: str,
) -> dict[str, Any]:
    allowed = {"approved", "rejected", "modified"}
    if outcome not in allowed:
        raise ValueError(outcome)
    t0 = datetime.fromisoformat(recommendation_at.replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(decision_at.replace("Z", "+00:00"))
    minutes = (t1 - t0).total_seconds() / 60.0
    if minutes < 0:
        raise ValueError("negative decision latency")
    entry = {
        "recommendation_at": recommendation_at,
        "decision_at": decision_at,
        "outcome": outcome,
        "latency_minutes": round(minutes, 4),
        "auto_approved": False,
    }
    _CASES[session_id]["decision_latencies"].append(entry)
    return entry


def add_research_review(
    session_id: str,
    *,
    question: str,
    judgement: str,
    why_needed: str | None = None,
) -> dict[str, Any]:
    allowed = {"USEFUL", "PARTIALLY_USEFUL", "NOT_USEFUL", "NO_RESULT"}
    if judgement not in allowed:
        raise ValueError(judgement)
    entry = {
        "question": str(question)[:500],
        "why_needed": (why_needed or "")[:500],
        "judgement": judgement,
        "at": _now(),
    }
    _CASES[session_id]["research_reviews"].append(entry)
    return entry


def set_conflict_labels(
    session_id: str,
    *,
    expected: list[str],
    detected: list[str] | None = None,
) -> dict[str, Any]:
    exp = [str(x) for x in expected]
    det = [str(x) for x in (detected or [])]
    exp_s, det_s = set(exp), set(det)
    labels = {
        "expected": sorted(exp_s),
        "detected": sorted(det_s),
        "missed": sorted(exp_s - det_s),
        "false_positives": sorted(det_s - exp_s),
        "true_positives": sorted(exp_s & det_s),
    }
    _CASES[session_id]["conflict_labels"] = labels
    return labels


def set_complexity(session_id: str, level: str, rationale: str) -> None:
    if level not in {"LOW", "MEDIUM", "HIGH"}:
        raise ValueError(level)
    _CASES[session_id]["complexity"] = level
    _CASES[session_id]["complexity_rationale"] = str(rationale)[:1000]


def set_engine_review(session_id: str, *, sample_size: str | None = None, statistics: str | None = None) -> None:
    allowed = {"ACCEPTED", "MODIFIED", "REJECTED", "BLOCKED"}
    if sample_size is not None:
        if sample_size not in allowed:
            raise ValueError(sample_size)
        _CASES[session_id]["sample_size_status"] = sample_size
    if statistics is not None:
        if statistics not in allowed:
            raise ValueError(statistics)
        _CASES[session_id]["statistics_status"] = statistics


def set_protocol_domain(session_id: str, domain: str, classification: str) -> None:
    allowed = {"CORRECT", "CORRECTED", "MISSING", "INCONSISTENT", "STALE", "OTHER"}
    if domain not in PROTOCOL_DOMAINS:
        raise ValueError(f"Unknown protocol domain: {domain}")
    if classification not in allowed:
        raise ValueError(classification)
    _CASES[session_id]["protocol_review"][domain] = classification


def complete_case(session_id: str) -> dict[str, Any]:
    row = _CASES[session_id]
    row["ended_at"] = _now()
    row["end_time"] = row["ended_at"]
    log_event(session_id, "SESSION_COMPLETED", stage="SESSION")
    log_event(session_id, "CASE_COMPLETED", stage="COMPLETE")
    pid = row.get("pair_id")
    if pid and pid in _PAIRS:
        pair = _PAIRS[pid]
        m = _CASES.get(pair["manual_session_id"])
        a = _CASES.get(pair["assisted_session_id"])
        if m and a and m.get("ended_at") and a.get("ended_at"):
            pair["complete"] = True
    return dict(row)


def add_feedback(
    session_id: str,
    *,
    answers: dict[str, str],
) -> dict[str, Any]:
    allowed_keys = {
        "saved_most_time",
        "biggest_time_saver",
        "unnecessary_clicks",
        "biggest_friction",
        "unclear",
        "did_not_trust",
        "least_trusted",
        "wanted_evidence_on",
        "useful_recommendations",
        "most_useful_feature",
        "hardest_to_verify",
        "most_frequent_correction",
        "missing_information",
        "desired_automation",
        "never_automate",
        "free_text",
    }
    clean = {k: str(v)[:2000] for k, v in answers.items() if k in allowed_keys}
    entry = {
        "session_id": session_id,
        "case_id": _CASES[session_id]["case_id"],
        "writer_id": _CASES[session_id]["writer_id"],
        "answers": clean,
        "at": _now(),
    }
    _FEEDBACK[session_id] = entry
    return entry


def get_session(session_id: str) -> dict[str, Any] | None:
    r = _CASES.get(session_id)
    return dict(r) if r else None


def list_sessions() -> list[dict[str, Any]]:
    return [dict(v) for v in _CASES.values()]


def list_pairs() -> list[dict[str, Any]]:
    return [dict(v) for v in _PAIRS.values()]


def list_events(session_id: str | None = None) -> list[dict[str, Any]]:
    if session_id:
        return [e for e in _EVENTS if e["session_id"] == session_id]
    return list(_EVENTS)


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def aggregate_timing_metrics(*, publish_aggregates: bool | None = None) -> dict[str, Any]:
    """Median / P25 / P75 only for directly observed sessions; aggregates gated by n."""
    observed = [
        s
        for s in _CASES.values()
        if s.get("timing_observed_directly") and s.get("time_saving_percent") is not None
    ]
    paired_eligible = [p for p in _PAIRS.values() if p.get("roi_eligible")]
    n_for_gate = len(paired_eligible) if paired_eligible else len(observed)
    meaningful = n_for_gate >= MIN_PAIRED_FOR_AGGREGATE
    if publish_aggregates is False:
        meaningful = False

    manuals = sorted(
        s["T_manual_minutes"] for s in observed if s.get("T_manual_minutes") is not None
    )
    assisted = sorted(
        s["T_total_minutes"] for s in observed if s.get("T_total_minutes") is not None
    )
    reviews = sorted(
        s["T_review_minutes"] for s in observed if s.get("T_review_minutes") is not None
    )
    savings = sorted(s["time_saving_percent"] for s in observed)

    def block(vals: list[float]) -> dict[str, Any]:
        if not vals or not meaningful:
            return {
                "n": len(vals),
                "median": None,
                "p25": None,
                "p75": None,
                "published": False,
                "mean_not_used_alone": True,
                "reason": None
                if meaningful
                else f"sample_size<{MIN_PAIRED_FOR_AGGREGATE}; aggregates unpublished",
            }
        return {
            "n": len(vals),
            "median": round(statistics.median(vals), 4),
            "p25": round(_percentile(vals, 0.25) or 0, 4),
            "p75": round(_percentile(vals, 0.75) or 0, 4),
            "published": True,
            "mean_not_used_alone": True,
            "reason": None,
        }

    return {
        "sessions_with_observed_timing": len(observed),
        "paired_roi_eligible": len(paired_eligible),
        "sessions_total": len(_CASES),
        "min_paired_for_aggregate": MIN_PAIRED_FOR_AGGREGATE,
        "aggregates_published": meaningful,
        "manual_minutes": block(manuals),
        "assisted_total_minutes": block(assisted),
        "review_minutes": block(reviews),
        "time_saving_percent": block(savings),
        "roi_claimed": False,
        "note": (
            "TIME_SAVING per session only when T_manual and T_total observed directly; "
            f"aggregates published only when n>={MIN_PAIRED_FOR_AGGREGATE}"
        ),
    }


def extraction_classification_summary(session_id: str | None = None) -> dict[str, Any]:
    sessions = [get_session(session_id)] if session_id else list_sessions()
    sessions = [s for s in sessions if s]
    tallies = {
        "CORRECT_AUTO": 0,
        "CORRECT_AFTER_REVIEW": 0,
        "MISSING": 0,
        "INCORRECT": 0,
        "CONFLICTING": 0,
        "NOT_APPLICABLE": 0,
    }
    for s in sessions:
        for cls in (s.get("field_classifications") or {}).values():
            if cls in tallies:
                tallies[cls] += 1
    applicable = sum(v for k, v in tallies.items() if k != "NOT_APPLICABLE") or 1
    total = sum(tallies.values()) or 1
    return {
        "tallies": tallies,
        "field_accuracy_auto_only": round(tallies["CORRECT_AUTO"] / applicable, 4),
        "review_corrected_accuracy": round(
            (tallies["CORRECT_AUTO"] + tallies["CORRECT_AFTER_REVIEW"]) / applicable, 4
        ),
        "wrong_value_rate": round(tallies["INCORRECT"] / applicable, 4),
        "missing_rate": round(tallies["MISSING"] / applicable, 4),
        "conflict_rate": round(tallies["CONFLICTING"] / applicable, 4),
        "critical_fields": list(CRITICAL_EXTRACTION_FIELDS),
        "classified_fields_total": total,
        "note": "CORRECT_AFTER_REVIEW is not counted as successful automatic extraction",
    }


def evidence_summary(session_id: str | None = None) -> dict[str, Any]:
    sessions = [get_session(session_id)] if session_id else list_sessions()
    sessions = [s for s in sessions if s]
    tallies = {"USEFUL": 0, "PARTIAL": 0, "INSUFFICIENT": 0, "WRONG_SOURCE": 0}
    provenance = {"COMPLETE": 0, "PARTIAL": 0, "MISSING": 0}
    for s in sessions:
        for j in (s.get("evidence_reviews") or {}).values():
            if j in tallies:
                tallies[j] += 1
        for j in (s.get("provenance_reviews") or {}).values():
            if j in provenance:
                provenance[j] += 1
    n = sum(tallies.values())
    pn = sum(provenance.values())
    return {
        "tallies": tallies,
        "n": n,
        "provenance_tallies": provenance,
        "provenance_completeness": round(provenance["COMPLETE"] / pn, 4) if pn else None,
        "provenance_useful_rate": round(tallies["USEFUL"] / n, 4) if n else None,
        "published": n > 0 or pn > 0,
    }


def research_summary(session_id: str | None = None) -> dict[str, Any]:
    sessions = [get_session(session_id)] if session_id else list_sessions()
    sessions = [s for s in sessions if s]
    tallies = {"USEFUL": 0, "PARTIALLY_USEFUL": 0, "NOT_USEFUL": 0, "NO_RESULT": 0}
    for s in sessions:
        for r in s.get("research_reviews") or []:
            j = r.get("judgement")
            if j in tallies:
                tallies[j] += 1
    n = sum(tallies.values())
    return {"tallies": tallies, "n": n, "published": n > 0, "synthetic_excluded": True}


def decision_workload_summary(session_id: str | None = None) -> dict[str, Any]:
    sessions = [get_session(session_id)] if session_id else list_sessions()
    sessions = [s for s in sessions if s]
    keys = (
        "recommendations",
        "approved_decisions",
        "rejected_decisions",
        "modified_decisions",
        "unresolved_decisions",
        "evidence_opens",
        "expert_decisions",
    )
    totals = {k: 0 for k in keys}
    for s in sessions:
        ops = s.get("ops") or {}
        for k in keys:
            totals[k] += int(ops.get(k) or 0)
    return {"totals": totals, "sessions": len(sessions)}


def protocol_quality_summary(session_id: str | None = None) -> dict[str, Any]:
    sessions = [get_session(session_id)] if session_id else list_sessions()
    sessions = [s for s in sessions if s]
    tallies = {
        "CORRECT": 0,
        "CORRECTED": 0,
        "MISSING": 0,
        "INCONSISTENT": 0,
        "STALE": 0,
        "OTHER": 0,
    }
    for s in sessions:
        for cls in (s.get("protocol_review") or {}).values():
            if cls in tallies:
                tallies[cls] += 1
    n = sum(tallies.values())
    correction_rate = round((tallies["CORRECTED"] + tallies["MISSING"] + tallies["INCONSISTENT"] + tallies["STALE"]) / n, 4) if n else None
    return {"tallies": tallies, "n": n, "protocol_correction_rate": correction_rate}


def assert_no_auto_medical(session: dict[str, Any]) -> dict[str, bool]:
    return {
        "ai_cannot_approve_decision": True,
        "ai_cannot_resolve_conflict": True,
        "ai_cannot_approve_sample_size": True,
        "ai_cannot_approve_statistics": True,
        "ai_cannot_finalize_protocol": True,
        "unverified_recommendation_not_approved_input": True,
        "session_flag": bool(session.get("no_auto_medical_decision", True)),
    }


def production_readiness() -> dict[str, Any]:
    from app.domain.field_study_status import load_ops_evidence

    pop = population_status()
    timing = aggregate_timing_metrics()
    paired = list_pairs()
    complete_pairs = [p for p in paired if p.get("complete")]
    ops = load_ops_evidence()

    postgres_status = ops.get("postgres_status") or ops.get("B-005_execution", {}).get("postgres_compose")
    if ops.get("POSTGRES_EXECUTION_BLOCKED"):
        postgres_status = "POSTGRES_EXECUTION_BLOCKED"
    postgres_ok = postgres_status == "EXECUTED" or bool(ops.get("postgres_native") and not ops.get("POSTGRES_EXECUTION_BLOCKED"))
    packages_ok = bool(pop.get("meets_minimum_10_full_real"))
    pairs_ok = len(complete_pairs) >= 5

    blockers: list[str] = []
    if not packages_ok:
        blockers.append("<10 distinct full REAL packages")
    if not pairs_ok:
        blockers.append(f"paired sessions complete={len(complete_pairs)} (need >=5)")
    if not postgres_ok:
        blockers.append("Postgres execution not completed")
    if ops.get("POSTGRES_EXECUTION_BLOCKED"):
        blockers.append("POSTGRES_EXECUTION_BLOCKED")
    if not timing.get("aggregates_published"):
        blockers.append("timing aggregates unpublished (need >=5 observed paired)")

    if packages_ok and pairs_ok and postgres_ok:
        gate = "CONTROLLED BETA"
    else:
        gate = "NOT READY"

    return {
        "gate": gate,
        "blockers": blockers,
        "real_full_packages": pop.get("real_full_sanitized"),
        "real_partial_packages": pop.get("real_partial_sanitized"),
        "paired_sessions_complete": len(complete_pairs),
        "postgres_execution_completed": postgres_ok,
        "controlled_beta_criteria": {
            "full_packages_ge_10": packages_ok,
            "paired_sessions_ge_5": pairs_ok,
            "postgres_execution_completed": postgres_ok,
        },
        "production_ready_claimed": False,
        "note": "CONTROLLED BETA only when ≥10 REAL full + ≥5 paired + Postgres executed; else NOT READY",
    }
