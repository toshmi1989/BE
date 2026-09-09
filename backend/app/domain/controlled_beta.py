"""Phase 22 — Controlled beta dashboards, session gate, timers, export."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.field_study import (
    complete_case,
    get_session,
    list_events,
    list_pairs,
    list_sessions,
    record_timings,
    start_case,
)
from app.domain.field_study_intake import get_intake_case, list_intake_cases, bootstrap_from_registry
from app.domain.field_study_status import data_quality_check, field_study_status, validate_session_integrity
from app.domain.real_package_registry import get_real_package, list_real_packages, population_status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def session_start_gate(case_id: str, writer_id: str | None = None) -> dict[str, Any]:
    """BLOCK unless REAL, sanitized, intake metadata, writer assigned."""
    reasons: list[str] = []
    bootstrap_from_registry()
    intake = get_intake_case(case_id)
    try:
        pkg = get_real_package(case_id)
    except KeyError:
        pkg = None

    if pkg is None and intake is None:
        reasons.append("case_not_found")
    origin = (pkg or intake or {}).get("origin")
    if origin not in {"REAL", "REAL_PARTIAL"}:
        reasons.append("package_not_REAL")

    sanitized = bool(pkg and pkg.get("sanitized")) or bool(
        intake and intake.get("sanitization_status") == "yes"
    )
    if not sanitized:
        reasons.append("sanitization_not_passed")

    if intake is None:
        reasons.append("intake_metadata_missing")
    else:
        if not intake.get("document_inventory"):
            reasons.append("document_inventory_missing")
        assigned = intake.get("writer_assigned") or writer_id
        if not assigned:
            reasons.append("writer_not_assigned")

    allowed = len(reasons) == 0
    return {
        "allowed": allowed,
        "result": "PASS" if allowed else "BLOCK",
        "reasons": reasons,
        "case_id": case_id,
    }


def intake_slots_dashboard() -> dict[str, Any]:
    """10 slots — EMPTY / INTAKE / SANITIZATION_REVIEW / READY / SESSION_DONE. No fakes."""
    bootstrap_from_registry()
    pop = population_status()
    cases = {c["case_id"]: c for c in list_intake_cases()}
    pkgs = list_real_packages(include_partial=True)

    slots: list[dict[str, Any]] = []
    # Slot 01-02 map to known packages if present; 03-10 empty intake slots
    known_full = [p for p in pkgs if p.get("origin") == "REAL"]
    known_partial = [p for p in pkgs if p.get("origin") == "REAL_PARTIAL"]

    def _slot_state(case_id: str | None) -> str:
        if not case_id:
            return "EMPTY"
        c = cases.get(case_id)
        if not c:
            return "INTAKE"
        st = c.get("state")
        if st == "SESSION_COMPLETE" or st == "QA_REVIEW":
            return "SESSION_DONE"
        if st == "READY_FOR_SESSION" or c.get("ready_for_session"):
            return "READY"
        if st == "SANITIZATION_REVIEW":
            return "SANITIZATION_REVIEW"
        if st in {"SESSION_IN_PROGRESS"}:
            return "READY"
        return "INTAKE"

    # Fixed 10 slots
    filled: list[str | None] = [None] * 10
    i = 0
    for p in known_full + known_partial:
        if i < 10:
            filled[i] = p["case_id"]
            i += 1

    for idx in range(10):
        cid = filled[idx]
        slots.append(
            {
                "slot": f"{idx + 1:02d}",
                "case_id": cid,
                "status": _slot_state(cid),
                "fabricated": False,
            }
        )

    return {
        "title": "REAL PACKAGE INTAKE",
        "display": f"{pop.get('real_full_sanitized') or 0} / 10 REAL PACKAGES",
        "full": pop.get("real_full_sanitized"),
        "partial": pop.get("real_partial_sanitized"),
        "empty": sum(1 for s in slots if s["status"] == "EMPTY"),
        "slots": slots,
        "synthetic_excluded": True,
    }


def writer_session_dashboard() -> dict[str, Any]:
    sessions = list_sessions()
    pairs = list_pairs()
    writers = sorted({str(s.get("writer_id")) for s in sessions if s.get("writer_id")})
    completed = [s for s in sessions if s.get("ended_at") or s.get("end_time")]
    pending = [s for s in sessions if not (s.get("ended_at") or s.get("end_time"))]
    return {
        "writers": len(writers),
        "writer_pseudonyms": writers,
        "sessions": len(sessions),
        "paired": len(pairs),
        "paired_complete": sum(1 for p in pairs if p.get("complete")),
        "completed": len(completed),
        "pending": [{"session_id": s["session_id"], "case_id": s.get("case_id"), "type": s.get("session_type")} for s in pending],
        "fabricated": False,
    }


def start_timed_session(
    *,
    case_id: str,
    writer_id: str,
    session_type: str,
    pair_id: str | None = None,
) -> dict[str, Any]:
    """Start MANUAL or SYSTEM_ASSISTED with automatic CASE_STARTED/SESSION_STARTED."""
    from uuid import uuid4

    from app.domain.field_study import _PAIRS
    from app.domain.field_study_intake import assign_writer, bootstrap_from_registry, get_intake_case

    if session_type not in {"MANUAL", "SYSTEM_ASSISTED"}:
        raise ValueError("session_type must be MANUAL or SYSTEM_ASSISTED")

    bootstrap_from_registry()
    intake = get_intake_case(case_id)
    if intake and not intake.get("writer_assigned"):
        assign_writer(case_id, writer_id)
        # Mark ready if sanitized
        from app.domain.field_study_intake import mark_ready_for_session, transition_state

        try:
            if intake.get("sanitization_status") == "yes" or (
                get_real_package(case_id).get("sanitized")
            ):
                try:
                    mark_ready_for_session(case_id)
                except ValueError:
                    transition_state(case_id, "READY_FOR_SESSION")
        except Exception:
            pass

    gate = session_start_gate(case_id, writer_id)
    if gate["result"] == "BLOCK":
        return {"ok": False, "gate": gate}

    if session_type == "MANUAL" and pair_id is None:
        pair_id = f"PAIR-{uuid4().hex[:10]}"
        row = start_case(
            case_id=case_id,
            writer_id=writer_id,
            system_used=False,
            mode="MANUAL",
            session_type="MANUAL",
            pair_id=pair_id,
        )
        _PAIRS[pair_id] = {
            "pair_id": pair_id,
            "case_id": case_id,
            "writer_pseudonym": writer_id,
            "manual_session_id": row["session_id"],
            "assisted_session_id": None,
            "created_at": _now(),
            "complete": False,
            "roi_eligible": False,
        }
        return {"ok": True, "gate": gate, "session": row, "pair_id": pair_id}

    if session_type == "SYSTEM_ASSISTED":
        if not pair_id:
            raise ValueError("pair_id required for SYSTEM_ASSISTED (link to MANUAL baseline)")
        pair = _PAIRS.get(pair_id)
        if not pair:
            raise KeyError("pair_id not found")
        if pair["case_id"] != case_id:
            raise ValueError("pair case_id mismatch — refuse unrelated pairing")
        if pair.get("writer_pseudonym") and pair["writer_pseudonym"] != writer_id:
            raise ValueError("pair writer mismatch — prefer same writer")
        row = start_case(
            case_id=case_id,
            writer_id=writer_id,
            system_used=True,
            mode="SYSTEM_ASSISTED",
            session_type="SYSTEM_ASSISTED",
            pair_id=pair_id,
        )
        pair["assisted_session_id"] = row["session_id"]
        return {"ok": True, "gate": gate, "session": row, "pair_id": pair_id}

    raise ValueError("unsupported start combination")


def stop_timed_session(session_id: str, *, review_minutes: float | None = None) -> dict[str, Any]:
    """Stop timer from timestamps; persist duration; emit completion events."""
    row = get_session(session_id)
    if not row:
        raise KeyError(session_id)
    start = _parse(row.get("start_time") or row.get("started_at"))
    end = datetime.now(timezone.utc)
    if not start:
        raise ValueError("missing start timestamp")
    minutes = (end - start).total_seconds() / 60.0
    if minutes < 0:
        raise ValueError("negative duration")

    stype = row.get("session_type") or row.get("mode")
    if stype == "MANUAL":
        record_timings(session_id, T_manual_minutes=minutes, observed_directly=True)
    else:
        rev = float(review_minutes) if review_minutes is not None else 0.0
        # system time = wall clock minus review (if provided); else all as system
        if review_minutes is not None:
            sys_m = max(0.0, minutes - rev)
            record_timings(
                session_id,
                T_manual_minutes=None,
                T_system_minutes=sys_m,
                T_review_minutes=rev,
                observed_directly=True,
            )
            # also stash manual from pair if available
            from app.domain.field_study import _PAIRS, _CASES  # noqa: PLC0415

            pid = row.get("pair_id")
            if pid and pid in _PAIRS:
                mid = _PAIRS[pid].get("manual_session_id")
                man = _CASES.get(mid or "")
                if man and man.get("T_manual_minutes") is not None:
                    record_timings(
                        session_id,
                        T_manual_minutes=man["T_manual_minutes"],
                        T_system_minutes=sys_m,
                        T_review_minutes=rev,
                        observed_directly=True,
                    )
        else:
            record_timings(session_id, T_system_minutes=minutes, T_review_minutes=0.0, observed_directly=True)

    completed = complete_case(session_id)
    events = list_events(session_id)
    integ = validate_session_integrity(completed, events)
    if not integ["ok"]:
        return {
            "ok": False,
            "session": completed,
            "integrity": integ,
            "note": "errors returned — not silently corrected",
        }
    return {"ok": True, "session": completed, "elapsed_minutes": round(minutes, 4), "integrity": integ}


def mark_session_complete_with_dq(session_id: str) -> dict[str, Any]:
    """Validate before COMPLETE; return errors instead of silent fix."""
    row = get_session(session_id)
    if not row:
        raise KeyError(session_id)
    errors: list[str] = []
    gate = session_start_gate(row["case_id"], row.get("writer_id"))
    if gate["result"] == "BLOCK":
        errors.extend(gate["reasons"])
    if not (row.get("start_time") or row.get("started_at")):
        errors.append("start_timestamp_missing")
    if not row.get("session_type"):
        errors.append("session_type_missing")
    if row.get("session_type") == "SYSTEM_ASSISTED" and not row.get("pair_id"):
        errors.append("paired_link_required")
    events = list_events(session_id)
    # Temporarily complete to check — actually validate current state first
    integ = validate_session_integrity(row, events)
    # Before complete, SESSION_COMPLETED may be missing — that's OK until stop
    soft_ok = True
    if errors:
        return {"ok": False, "errors": errors, "silent_correction": False}
    completed = complete_case(session_id)
    integ2 = validate_session_integrity(completed, list_events(session_id))
    if not integ2["ok"]:
        return {"ok": False, "errors": integ2["issues"], "session": completed, "silent_correction": False}
    return {"ok": True, "session": completed, "silent_correction": False}


def export_field_study(*, format: str = "json") -> dict[str, Any]:
    """Structured export — no secrets, no document bodies."""
    sessions = list_sessions()
    pairs = list_pairs()
    rows = []
    for s in sessions:
        rows.append(
            {
                "case_id": s.get("case_id"),
                "writer_pseudonym": s.get("writer_pseudonym") or s.get("writer_id"),
                "session_id": s.get("session_id"),
                "session_type": s.get("session_type"),
                "pair_id": s.get("pair_id"),
                "manual_time": s.get("manual_total_time") or s.get("T_manual_minutes"),
                "assisted_time": s.get("assisted_total_time") or s.get("T_total_minutes"),
                "system_time": s.get("system_total_time") or s.get("T_system_minutes"),
                "review_time": s.get("review_time") or s.get("T_review_minutes"),
                "extraction_classifications": s.get("field_classifications") or {},
                "conflict_labels": s.get("conflict_labels") or {},
                "conflict_writer_labels": s.get("conflict_writer_labels") or [],
                "evidence_ratings": s.get("evidence_reviews") or {},
                "provenance": s.get("provenance_reviews") or {},
                "research_usefulness": s.get("research_reviews") or [],
                "decision_metrics": {
                    "ops": s.get("ops") or {},
                    "latencies": s.get("decision_latencies") or [],
                },
                "protocol_corrections": s.get("protocol_corrections") or [],
                "docx_review": s.get("docx_review") or {},
                "sample_size_status": s.get("sample_size_status"),
                "statistics_status": s.get("statistics_status"),
                "timing_observed_directly": s.get("timing_observed_directly"),
            }
        )
    payload = {
        "exported_at": _now(),
        "format": format,
        "pairs": pairs,
        "sessions": rows,
        "feedback_note": "feedback stored per session via feedback API — join by session_id",
        "secrets_included": False,
        "document_contents_included": False,
        "status": field_study_status(),
        "data_quality": data_quality_check(),
    }
    return payload


def beta_readiness_message() -> dict[str, Any]:
    st = field_study_status()
    from app.domain.field_study import production_readiness  # noqa: PLC0415

    gate = production_readiness()
    reasons: list[str] = []
    if (st.get("full_packages") or 0) < 10:
        reasons.append(f"only {st.get('full_packages')} full real package(s)")
    if (st.get("writers") or 0) == 0:
        reasons.append("0 writers")
    if (st.get("paired_sessions_complete") or 0) == 0:
        reasons.append("0 paired sessions")
    if st.get("postgres_status") != "EXECUTED":
        reasons.append(f"Postgres not executed ({st.get('postgres_status')})")

    label = "BETA READY" if gate["gate"] == "CONTROLLED BETA" else "BETA NOT READY"
    return {
        "label": label,
        "gate": gate["gate"],
        "reasons": reasons,
        "status": st,
        "production": gate,
    }
