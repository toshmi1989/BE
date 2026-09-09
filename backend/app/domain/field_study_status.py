"""Phase 21 — Field-study data quality and status (no silent drops)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.field_study import (
    MIN_PAIRED_FOR_AGGREGATE,
    aggregate_timing_metrics,
    list_events,
    list_pairs,
    list_sessions,
)
from app.domain.field_study_intake import intake_status_summary, list_intake_cases
from app.domain.real_package_registry import REPO_ROOT, list_real_packages, population_status

OPS_EVIDENCE_PATHS = (
    REPO_ROOT / "fixtures" / "field_study" / "phase24_postgres_evidence.json",
    REPO_ROOT / "fixtures" / "field_study" / "phase21_ops_evidence.json",
    REPO_ROOT / "fixtures" / "field_study" / "phase20_ops_evidence.json",
)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_session_integrity(session: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Chronology, non-negative duration, required events."""
    issues: list[str] = []
    required = {"CASE_STARTED", "SESSION_STARTED", "SESSION_COMPLETED", "CASE_COMPLETED"}
    names = {e["event"] for e in events}
    missing_req = sorted(required - names)
    if missing_req:
        issues.append(f"missing_required_events:{','.join(missing_req)}")

    stamps = [_parse_ts(e.get("timestamp")) for e in events]
    if any(t is None for t in stamps) and events:
        issues.append("unparseable_event_timestamp")
    valid_stamps = [t for t in stamps if t is not None]
    for i in range(1, len(valid_stamps)):
        if valid_stamps[i] < valid_stamps[i - 1]:
            issues.append("event_chronology_violation")
            break

    start = _parse_ts(session.get("start_time") or session.get("started_at"))
    end = _parse_ts(session.get("end_time") or session.get("ended_at"))
    if start and end and end < start:
        issues.append("negative_session_duration")

    for key in ("T_manual_minutes", "T_system_minutes", "T_review_minutes", "T_total_minutes"):
        v = session.get(key)
        if v is not None and float(v) < 0:
            issues.append(f"negative_duration:{key}")

    return {
        "session_id": session.get("session_id"),
        "ok": len(issues) == 0,
        "issues": issues,
    }


def detect_impossible_overlaps(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same writer overlapping open intervals → invalid."""
    problems: list[dict[str, Any]] = []
    by_writer: dict[str, list[dict[str, Any]]] = {}
    for s in sessions:
        by_writer.setdefault(str(s.get("writer_id")), []).append(s)
    for wid, rows in by_writer.items():
        intervals = []
        for s in rows:
            a = _parse_ts(s.get("start_time") or s.get("started_at"))
            b = _parse_ts(s.get("end_time") or s.get("ended_at")) or a
            if a and b:
                intervals.append((a, b, s.get("session_id")))
        intervals.sort()
        for i in range(1, len(intervals)):
            prev_a, prev_b, prev_id = intervals[i - 1]
            cur_a, cur_b, cur_id = intervals[i]
            if cur_a < prev_b:
                problems.append(
                    {
                        "writer_id": wid,
                        "session_a": prev_id,
                        "session_b": cur_id,
                        "issue": "overlapping_impossible_interval",
                    }
                )
    return problems


def data_quality_check() -> dict[str, Any]:
    """Validate observations; exclude invalid with explicit reasons (never silent)."""
    sessions = list_sessions()
    pairs = list_pairs()
    pop = population_status()
    real_ids = {p["case_id"] for p in list_real_packages(include_partial=True)}
    intake_ids = {c["case_id"] for c in list_intake_cases()}
    allowed = real_ids | intake_ids

    included: list[str] = []
    excluded: list[dict[str, Any]] = []

    seen_sessions: set[str] = set()
    for s in sessions:
        sid = s.get("session_id")
        reasons: list[str] = []
        if sid in seen_sessions:
            reasons.append("duplicate_session")
        seen_sessions.add(str(sid))

        if not (s.get("start_time") or s.get("started_at")):
            reasons.append("timestamp_missing_start")
        if s.get("writer_id") in (None, ""):
            reasons.append("writer_id_invalid")
        if s.get("case_id") not in allowed:
            reasons.append("package_not_real_or_intake")
        # sanitization
        intake = next((c for c in list_intake_cases() if c["case_id"] == s.get("case_id")), None)
        if intake and intake.get("sanitization_status") not in {"yes", "pending"}:
            if intake.get("sanitization_status") == "no":
                reasons.append("sanitization_failed")
        if s.get("timing_observed_directly") is False and s.get("time_saving_percent") is not None:
            reasons.append("estimated_time_present")

        ev = list_events(str(sid))
        integ = validate_session_integrity(s, ev)
        if not integ["ok"]:
            reasons.extend(integ["issues"])

        if reasons:
            excluded.append({"session_id": sid, "case_id": s.get("case_id"), "reasons": reasons})
        else:
            included.append(str(sid))

    overlaps = detect_impossible_overlaps(sessions)
    for o in overlaps:
        excluded.append({"session_id": o.get("session_b"), "reasons": [o["issue"]], **o})

    # Pair DQ
    pair_included: list[str] = []
    pair_excluded: list[dict[str, Any]] = []
    for p in pairs:
        reasons = []
        if not p.get("roi_eligible") and p.get("complete"):
            # complete but not roi-eligible may still be structural
            pass
        if p.get("case_id") not in allowed:
            reasons.append("package_not_real")
        m_ok = p.get("manual_session_id") in included or p.get("manual_session_id") in {
            e.get("session_id") for e in excluded
        }
        if reasons:
            pair_excluded.append({"pair_id": p.get("pair_id"), "reasons": reasons})
        else:
            pair_included.append(str(p.get("pair_id")))

    return {
        "sessions_total": len(sessions),
        "sessions_included": included,
        "sessions_excluded": excluded,
        "pairs_total": len(pairs),
        "pairs_included": pair_included,
        "pairs_excluded": pair_excluded,
        "overlaps": overlaps,
        "silent_drops": False,
        "note": "Invalid observations excluded with explicit reasons; never silently dropped",
        "registry_meets_10": pop.get("meets_minimum_10_full_real"),
    }


def load_ops_evidence() -> dict[str, Any]:
    for path in OPS_EVIDENCE_PATHS:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            data["_path"] = str(path.as_posix())
            return data
    return {"postgres_status": "UNKNOWN", "backup_status": "UNKNOWN"}


def field_study_status() -> dict[str, Any]:
    """GET /api/field-study/status — real counters only."""
    from app.core.config import get_settings

    pop = population_status()
    intake = intake_status_summary()
    sessions = list_sessions()
    pairs = list_pairs()
    writers = sorted({str(s.get("writer_id")) for s in sessions if s.get("writer_id")})
    completed = [s for s in sessions if s.get("ended_at") or s.get("end_time")]
    complete_pairs = [p for p in pairs if p.get("complete")]
    ops = load_ops_evidence()
    settings = get_settings()

    postgres_status = ops.get("postgres_status") or ops.get("B-005_execution", {}).get("postgres_compose")
    if ops.get("POSTGRES_EXECUTION_BLOCKED"):
        postgres_status = "POSTGRES_EXECUTION_BLOCKED"
    elif ops.get("postgres_native") and not ops.get("POSTGRES_EXECUTION_BLOCKED"):
        postgres_status = "EXECUTED"
    elif postgres_status in (None, "UNKNOWN"):
        postgres_status = ops.get("docker_compose_beta") or "UNKNOWN"

    # File DB backup is supplemental — do not present as Postgres beta proof
    backup_status = "UNKNOWN"
    if ops.get("BACKUP_RESTORE_OK") and ops.get("postgres_native"):
        backup_status = "OK"
    elif ops.get("POSTGRES_EXECUTION_BLOCKED"):
        backup_status = "BLOCKED"
    elif ops.get("B-005_execution", {}).get("file_db_backup_restore") == "EXECUTED_OK":
        backup_status = "FILE_DB_SUPPLEMENTAL_ONLY"

    restart_test = ops.get("restart_durability") or ops.get("steps", {}).get("restart_durability", {})
    if isinstance(restart_test, dict):
        restart_label = "OK" if restart_test.get("ok") else "UNKNOWN"
        if ops.get("POSTGRES_EXECUTION_BLOCKED") and not ops.get("postgres_native"):
            restart_label = "FILE_DB_SUPPLEMENTAL_ONLY"
    else:
        restart_label = str(restart_test)

    dq = data_quality_check()
    timing = aggregate_timing_metrics()

    packages_ok = bool(pop.get("meets_minimum_10_full_real"))
    pairs_ok = len(complete_pairs) >= 5
    postgres_ok = postgres_status == "EXECUTED"
    gate = "CONTROLLED BETA" if (packages_ok and pairs_ok and postgres_ok) else "NOT READY"

    reasons: list[str] = []
    if (pop.get("real_full_sanitized") or 0) < 10:
        reasons.append(f"only {pop.get('real_full_sanitized')} full real package")
    if len(writers) == 0:
        reasons.append("0 writers")
    if len(complete_pairs) == 0:
        reasons.append("0 paired sessions")
    if postgres_status != "EXECUTED":
        reasons.append("Postgres not executed")

    beta_label = "BETA READY" if gate == "CONTROLLED BETA" else "BETA NOT READY"

    return {
        "beta_label": beta_label,
        "reasons": reasons,
        "environment": {
            "app_version": settings.app_version,
            "ai_enabled": settings.ai_enabled,
        },
        "database": {
            "url_scheme": (settings.database_url or "").split(":", 1)[0],
            "postgres_required_for_beta": True,
        },
        "auth": {
            "auth_required": bool(settings.auth_required),
            "auth_secret_configured": bool(settings.auth_secret),
            "secret_value_exposed": False,
        },
        "real_packages": (pop.get("real_full_sanitized") or 0) + (pop.get("real_partial_sanitized") or 0),
        "real_full_packages": pop.get("real_full_sanitized"),
        "real_partial_packages": pop.get("real_partial_sanitized"),
        "full_packages": pop.get("real_full_sanitized"),
        "partial_packages": pop.get("real_partial_sanitized"),
        "synthetic_excluded_from_counters": True,
        "writers": len(writers),
        "writer_pseudonyms": writers,
        "sessions": len(sessions),
        "paired_sessions": len(pairs),
        "paired_sessions_complete": len(complete_pairs),
        "completed_sessions": len(completed),
        "completed_cases": len(completed),
        "postgres_ops": postgres_status,
        "postgres_status": postgres_status,
        "backup_restore": backup_status,
        "backup_status": backup_status,
        "restart_test": restart_label,
        "open_P1": [x for x in [
            "B-002-PACK" if (pop.get("real_full_sanitized") or 0) < 10 else None,
            "B-003" if len(complete_pairs) < 5 else None,
            "B-005" if postgres_status != "EXECUTED" else None,
        ] if x],
        "production_gate": gate,
        "intake": intake,
        "data_quality": {
            "sessions_included": len(dq["sessions_included"]),
            "sessions_excluded": len(dq["sessions_excluded"]),
            "silent_drops": False,
        },
        "timing_aggregates_published": timing.get("aggregates_published"),
        "min_paired_for_aggregate": MIN_PAIRED_FOR_AGGREGATE,
        "production_gate_inputs": {
            "full_packages_ge_10": packages_ok,
            "paired_sessions_ge_5": pairs_ok,
            "postgres_execution_completed": postgres_ok,
        },
    }
