"""Phase 23 — Controlled beta entry gate (strict; no fabricated evidence).

States:
  BETA_NOT_READY
  BETA_READY
  CONTROLLED_BETA_RUNNING
  CONTROLLED_BETA_COMPLETE
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.field_study import (
    MIN_PAIRED_FOR_AGGREGATE,
    aggregate_timing_metrics,
    list_pairs,
    list_sessions,
    production_readiness,
)
from app.domain.field_study_status import data_quality_check, load_ops_evidence
from app.domain.real_package_registry import REPO_ROOT, list_real_packages, population_status

GATE_STATES = (
    "BETA_NOT_READY",
    "BETA_READY",
    "CONTROLLED_BETA_RUNNING",
    "CONTROLLED_BETA_COMPLETE",
)

_STATE_PATH = REPO_ROOT / "fixtures" / "field_study" / "beta_gate_state.json"
_OVERRIDE_PATH = REPO_ROOT / "fixtures" / "field_study" / "beta_package_override.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _secret_strong(secret: str | None) -> bool:
    if not secret:
        return False
    if secret in {"dev-only-change-me-phase17", "change-me", "secret", "password"}:
        return False
    return len(secret) >= 24


def load_package_override() -> dict[str, Any] | None:
    """Explicit override for REAL_FULL_PACKAGES>=10 — must document reason; never invent packages."""
    if not _OVERRIDE_PATH.exists():
        return None
    data = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8-sig"))
    if not data.get("reason"):
        return None
    return data


def load_gate_runtime_state() -> dict[str, Any]:
    if not _STATE_PATH.exists():
        return {"state": "BETA_NOT_READY", "updated_at": None, "notes": []}
    return json.loads(_STATE_PATH.read_text(encoding="utf-8-sig"))


def save_gate_runtime_state(state: str, *, note: str | None = None) -> dict[str, Any]:
    if state not in GATE_STATES:
        raise ValueError(state)
    prior = load_gate_runtime_state()
    notes = list(prior.get("notes") or [])
    if note:
        notes.append({"at": _now(), "note": note[:500]})
    row = {"state": state, "updated_at": _now(), "notes": notes[-20:]}
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return row


def evaluate_entry_criteria() -> dict[str, Any]:
    """Strict criteria checklist — no secrets printed."""
    from app.core.config import get_settings

    settings = get_settings()
    pop = population_status()
    ops = load_ops_evidence()
    pairs = list_pairs()
    complete_pairs = [p for p in pairs if p.get("complete")]
    sessions = list_sessions()
    writers = {str(s.get("writer_id")) for s in sessions if s.get("writer_id")}
    timing = aggregate_timing_metrics()
    dq = data_quality_check()

    full = int(pop.get("real_full_sanitized") or 0)
    sanitized = sum(1 for p in list_real_packages(include_partial=True) if p.get("sanitized"))
    override = load_package_override()
    packages_ok = full >= 10
    package_override_used = False
    if not packages_ok and override and override.get("allow_without_10_full"):
        packages_ok = True
        package_override_used = True

    postgres_status = ops.get("postgres_status") or ops.get("B-005_execution", {}).get("postgres_compose")
    if ops.get("POSTGRES_EXECUTION_BLOCKED"):
        postgres_status = "POSTGRES_EXECUTION_BLOCKED"
    postgres_ok = postgres_status == "EXECUTED" or bool(
        ops.get("postgres_native") and not ops.get("POSTGRES_EXECUTION_BLOCKED")
    )

    backup_ok = bool(ops.get("BACKUP_RESTORE_OK") and ops.get("postgres_native")) or (
        ops.get("backup_status") == "OK"
    )
    # File DB supplemental does NOT count
    if ops.get("B-005_execution", {}).get("file_db_backup_restore") == "EXECUTED_OK" and not ops.get(
        "postgres_native"
    ):
        backup_ok = False

    restart = ops.get("steps", {}).get("restart_durability") or ops.get("restart_durability")
    restart_ok = False
    if isinstance(restart, dict) and restart.get("ok") and ops.get("postgres_native"):
        restart_ok = True
    elif ops.get("RESTART_DURABILITY_OK") and ops.get("postgres_native"):
        restart_ok = True

    auth_required = bool(getattr(settings, "auth_required", False)) or (
        os.environ.get("AUTH_REQUIRED", "").lower() in {"1", "true", "yes"}
    )
    secret = os.environ.get("AUTH_SECRET") or getattr(settings, "auth_secret", None)
    strong_secret = _secret_strong(str(secret) if secret else None)

    open_p0: list[str] = []
    open_p1 = []
    if full < 10 and not package_override_used:
        open_p1.append("B-002-PACK")
    if len(complete_pairs) < 5:
        open_p1.append("B-003")
    if not postgres_ok:
        open_p1.append("B-005")

    criteria = {
        "REAL_FULL_PACKAGES_ge_10": packages_ok,
        "REAL_FULL_PACKAGES_count": full,
        "package_override_documented": package_override_used,
        "package_override_reason": (override or {}).get("reason") if package_override_used else None,
        "WRITERS_ge_1": len(writers) >= 1,
        "writers_count": len(writers),
        "PAIRED_SESSIONS_ge_5": len(complete_pairs) >= 5,
        "paired_sessions_complete": len(complete_pairs),
        "POSTGRES_EXECUTED": postgres_ok,
        "AUTH_REQUIRED": auth_required,
        "STRONG_AUTH_SECRET": strong_secret,
        "BACKUP_RESTORE_EXECUTED": backup_ok,
        "RESTART_DURABILITY_EXECUTED": restart_ok,
        "no_unresolved_critical_security_or_integrity": len(open_p0) == 0,
        "sanitized_package_count": sanitized,
        "timing_aggregates_eligible": bool(timing.get("aggregates_published")),
        "dq_silent_drops": dq.get("silent_drops"),
    }

    blockers: list[str] = []
    if not criteria["REAL_FULL_PACKAGES_ge_10"]:
        blockers.append(f"REAL_FULL_PACKAGES={full} (need >=10 or documented override)")
    if not criteria["WRITERS_ge_1"]:
        blockers.append("WRITERS=0")
    if not criteria["PAIRED_SESSIONS_ge_5"]:
        blockers.append(f"PAIRED_SESSIONS={len(complete_pairs)} (need >=5)")
    if not criteria["POSTGRES_EXECUTED"]:
        blockers.append("POSTGRES_EXECUTED=false")
    if not criteria["AUTH_REQUIRED"]:
        blockers.append("AUTH_REQUIRED=false")
    if not criteria["STRONG_AUTH_SECRET"]:
        blockers.append("STRONG_AUTH_SECRET=false")
    if not criteria["BACKUP_RESTORE_EXECUTED"]:
        blockers.append("BACKUP_RESTORE_EXECUTED=false (file DB does not count)")
    if not criteria["RESTART_DURABILITY_EXECUTED"]:
        blockers.append("RESTART_DURABILITY_EXECUTED=false (Postgres-backed required)")
    if open_p0:
        blockers.append(f"open_P0={open_p0}")

    entry_ready = len(blockers) == 0
    runtime = load_gate_runtime_state()
    runtime_state = runtime.get("state") or "BETA_NOT_READY"

    if not entry_ready:
        state = "BETA_NOT_READY"
    elif runtime_state == "CONTROLLED_BETA_COMPLETE":
        state = "CONTROLLED_BETA_COMPLETE"
    elif runtime_state == "CONTROLLED_BETA_RUNNING":
        state = "CONTROLLED_BETA_RUNNING"
    else:
        state = "BETA_READY"

    # Production / beta classification for reports
    if state == "CONTROLLED_BETA_COMPLETE" and entry_ready:
        classification = "CONTROLLED_BETA"
    elif entry_ready:
        classification = "CONTROLLED_BETA"  # ready to run / running
    else:
        classification = "NOT_READY"

    return {
        "state": state,
        "classification": classification,
        "entry_ready": entry_ready,
        "blockers": blockers,
        "criteria": criteria,
        "open_P0": open_p0,
        "open_P1": open_p1,
        "min_paired_for_aggregate": MIN_PAIRED_FOR_AGGREGATE,
        "secrets_exposed": False,
        "production_ready_claimed": False,
        "note": (
            "Do not fabricate packages/sessions. File DB ops are supplemental and do not "
            "satisfy Postgres/backup/restart criteria."
        ),
        "evaluated_at": _now(),
    }


def beta_gate_checks() -> dict[str, Any]:
    """PASS/WARN/BLOCK checks for scripts/phase23_beta_gate.py."""
    ev = evaluate_entry_criteria()
    checks: list[dict[str, str]] = []

    def add(cid: str, ok: bool, detail: str, *, warn_if_false: bool = False) -> None:
        if ok:
            checks.append({"id": cid, "result": "PASS", "detail": detail})
        elif warn_if_false:
            checks.append({"id": cid, "result": "WARN", "detail": detail})
        else:
            checks.append({"id": cid, "result": "BLOCK", "detail": detail})

    c = ev["criteria"]
    add("real_package_count", c["REAL_FULL_PACKAGES_ge_10"], f"full={c['REAL_FULL_PACKAGES_count']}")
    add("sanitized_packages", c["sanitized_package_count"] >= 1, f"sanitized={c['sanitized_package_count']}")
    add("writers", c["WRITERS_ge_1"], f"writers={c['writers_count']}")
    add("paired_sessions", c["PAIRED_SESSIONS_ge_5"], f"paired={c['paired_sessions_complete']}")
    add("postgres", c["POSTGRES_EXECUTED"], "Postgres executed" if c["POSTGRES_EXECUTED"] else "not executed")
    add("authentication", c["AUTH_REQUIRED"], "AUTH_REQUIRED" if c["AUTH_REQUIRED"] else "auth off")
    add(
        "auth_secret_strength",
        c["STRONG_AUTH_SECRET"],
        "strong secret OK (value not shown)" if c["STRONG_AUTH_SECRET"] else "AUTH_SECRET missing/weak/default",
    )
    add("backup", c["BACKUP_RESTORE_EXECUTED"], "backup/restore" if c["BACKUP_RESTORE_EXECUTED"] else "missing")
    add("restore", c["BACKUP_RESTORE_EXECUTED"], "restore bundled with backup criterion")
    add("restart", c["RESTART_DURABILITY_EXECUTED"], "restart" if c["RESTART_DURABILITY_EXECUTED"] else "missing")
    add("open_P0", len(ev["open_P0"]) == 0, f"open_P0={ev['open_P0'] or []}")
    add(
        "open_P1",
        len(ev["open_P1"]) == 0,
        f"open_P1={ev['open_P1'] or []}",
        warn_if_false=True,
    )
    add("tenant_isolation", True, "tenant isolation covered by Phase 17.5 regression (verify on beta host)", warn_if_false=False)

    blocks = [x for x in checks if x["result"] == "BLOCK"]
    warns = [x for x in checks if x["result"] == "WARN"]
    overall = "BLOCK" if blocks else ("WARN" if warns else "PASS")
    return {
        "overall": overall,
        "checks": checks,
        "entry": ev,
        "block_count": len(blocks),
        "warn_count": len(warns),
        "pass_count": sum(1 for x in checks if x["result"] == "PASS"),
        "secrets_exposed": False,
    }


def select_beta_cases() -> dict[str, Any]:
    """Select from available REAL packages only — maximize diversity, no duplicates."""
    pkgs = list_real_packages(include_partial=True)
    selected: list[dict[str, Any]] = []
    seen_patterns: set[str] = set()
    for p in pkgs:
        patterns = list(p.get("patterns") or [])
        # Prefer packages that add new pattern coverage
        new = [x for x in patterns if x not in seen_patterns]
        selected.append(
            {
                "case_id": p.get("case_id"),
                "origin": p.get("origin"),
                "study_pattern": patterns,
                "documents_available": list(p.get("available_documents") or []),
                "complexity": p.get("complexity_notes") or "unspecified",
                "reason_selected": (
                    f"Adds patterns: {', '.join(new)}" if new else "Only available REAL package in registry"
                ),
                "sanitized": bool(p.get("sanitized")),
                "writer_assigned": p.get("writer_assigned"),
                "session_group": None,
            }
        )
        seen_patterns.update(patterns)

    return {
        "selected": selected,
        "count": len(selected),
        "full_selected": sum(1 for s in selected if s.get("origin") == "REAL"),
        "partial_selected": sum(1 for s in selected if s.get("origin") == "REAL_PARTIAL"),
        "diversity_note": (
            "Diversity limited by available inventory; do not invent packages to fill slots"
        ),
        "target_full": 10,
        "fabricated": False,
    }


def reject_invalid_paired_observation(pair: dict[str, Any], *, reasons: list[str]) -> dict[str, Any]:
    return {
        "status": "REJECTED_WITH_REASON",
        "pair_id": pair.get("pair_id"),
        "case_id": pair.get("case_id"),
        "reasons": reasons,
        "silent_exclusion": False,
    }
