"""Phase 18 — Beta observability (workflow timing / stage metrics)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_RUNS: dict[str, dict[str, Any]] = {}


def reset_beta_observability() -> None:
    _RUNS.clear()


def start_beta_run(
    *,
    study_id: str,
    case_id: str | None = None,
    organization_id: str | None = None,
) -> str:
    wid = f"BETA-{uuid4().hex[:12]}"
    _RUNS[wid] = {
        "workflow_id": wid,
        "study_id": study_id,
        "case_id": case_id,
        "organization_id": organization_id,
        "stage": "START",
        "status": "RUNNING",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "duration_ms": None,
        "stages": [],
        "errors": [],
        "final_status": None,
    }
    return wid


def mark_stage(workflow_id: str, stage: str, *, error: str | None = None, meta: dict | None = None) -> None:
    run = _RUNS.get(workflow_id)
    if not run:
        return
    entry = {
        "stage": stage,
        "at": datetime.now(timezone.utc).isoformat(),
        "error": error,
        "meta": meta or {},
    }
    run["stages"].append(entry)
    run["stage"] = stage
    if error:
        run["errors"].append({"stage": stage, "error": error})


def finish_beta_run(workflow_id: str, *, status: str = "COMPLETE") -> dict[str, Any]:
    run = _RUNS.get(workflow_id)
    if not run:
        return {}
    ended = datetime.now(timezone.utc)
    run["ended_at"] = ended.isoformat()
    started = datetime.fromisoformat(run["started_at"])
    run["duration_ms"] = int((ended - started).total_seconds() * 1000)
    run["status"] = status
    run["final_status"] = status
    return dict(run)


def get_beta_run(workflow_id: str) -> dict[str, Any] | None:
    r = _RUNS.get(workflow_id)
    return dict(r) if r else None


def list_beta_runs() -> list[dict[str, Any]]:
    return [dict(v) for v in _RUNS.values()]
