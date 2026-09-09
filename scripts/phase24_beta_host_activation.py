#!/usr/bin/env python3
"""Phase 24 — Beta host activation probe.

Writes honest evidence only. Never fabricates Postgres/backup/session success.
Exit 0 if BETA_READY criteria met; 2 if BETA_NOT_READY.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

EVIDENCE = ROOT / "fixtures" / "field_study" / "phase24_postgres_evidence.json"
ACTIVATION = ROOT / "fixtures" / "field_study" / "phase24_activation_result.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    from app.domain.beta_entry_gate import beta_gate_checks, evaluate_entry_criteria
    from app.domain.real_package_registry import list_real_packages, population_status
    from app.domain.controlled_beta import intake_slots_dashboard, writer_session_dashboard

    docker = shutil.which("docker")
    blockers: list[str] = []
    steps: dict = {}

    if not docker:
        blockers.append("Docker CLI not available")
        steps["docker"] = {"result": "BLOCK", "detail": "docker not on PATH"}
    else:
        steps["docker"] = {"result": "PASS", "detail": docker}
        # Attempt compose only if docker exists
        try:
            proc = subprocess.run(
                ["docker", "compose", "-f", "docker-compose.beta.yml", "ps"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            steps["compose_ps"] = {
                "result": "PASS" if proc.returncode == 0 else "BLOCK",
                "returncode": proc.returncode,
                "stdout_tail": (proc.stdout or "")[-500:],
                "stderr_tail": (proc.stderr or "")[-500:],
            }
            if proc.returncode != 0:
                blockers.append("docker compose ps failed")
        except Exception as e:  # noqa: BLE001
            steps["compose_ps"] = {"result": "BLOCK", "detail": type(e).__name__}
            blockers.append(f"compose probe failed: {type(e).__name__}")

    # Do NOT start compose or invent backup if docker missing
    postgres_executed = False
    backup_ok = False
    restore_ok = False
    restart_ok = False

    if docker and not blockers:
        # Host has docker — operator may have stack up; probe health only
        import urllib.request

        base = os.environ.get("BETA_API_BASE", "http://127.0.0.1:8000")
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=3) as resp:
                steps["health"] = {"result": "PASS" if resp.status == 200 else "WARN", "status": resp.status}
            with urllib.request.urlopen(f"{base}/api/ready", timeout=3) as resp:
                steps["readiness"] = {"result": "PASS" if resp.status == 200 else "WARN", "status": resp.status}
        except Exception:
            steps["health"] = {"result": "BLOCK", "detail": "API not reachable — start compose first"}
            steps["readiness"] = {"result": "BLOCK", "detail": "API not reachable"}
            blockers.append("health/readiness unreachable")
    else:
        steps["health"] = {"result": "BLOCK", "detail": "skipped — Docker unavailable"}
        steps["readiness"] = {"result": "BLOCK", "detail": "skipped — Docker unavailable"}
        steps["compose_up"] = {
            "result": "BLOCK",
            "detail": "docker compose -f docker-compose.beta.yml up -d NOT executed",
        }
        steps["backup"] = {"result": "BLOCK", "detail": "not executed"}
        steps["restore"] = {"result": "BLOCK", "detail": "not executed"}
        steps["restart"] = {"result": "BLOCK", "detail": "not executed"}

    auth_required = os.environ.get("AUTH_REQUIRED", "").lower() in {"1", "true", "yes"}
    if not auth_required:
        blockers.append("AUTH_REQUIRED is not true")

    pop = population_status()
    pkgs = list_real_packages(include_partial=True)
    diversity = []
    for p in pkgs:
        diversity.append(
            {
                "case_id": p.get("case_id"),
                "origin": p.get("origin"),
                "study_type": p.get("study_type"),
                "design_pattern": list(p.get("patterns") or []),
                "food_condition": (
                    "fed"
                    if "fed" in " ".join(p.get("patterns") or []).lower()
                    else ("fasting_like" if "fasting" in " ".join(p.get("patterns") or []).lower() or "crossover" in " ".join(p.get("patterns") or []) else "unspecified")
                ),
                "document_completeness": {
                    "available": list(p.get("available_documents") or []),
                    "missing": list(p.get("missing_documents") or []),
                },
                "special_complexity": p.get("complexity_notes"),
                "sanitized": bool(p.get("sanitized")),
            }
        )

    evidence = {
        "phase": 24,
        "executed_at": _now(),
        "fabricated": False,
        "POSTGRES_EXECUTION_BLOCKED": not postgres_executed,
        "postgres_status": "EXECUTED" if postgres_executed else "POSTGRES_EXECUTION_BLOCKED",
        "postgres_native": False,
        "docker_available": bool(docker),
        "docker_compose_beta": "EXECUTED" if postgres_executed else "NOT_EXECUTED",
        "BACKUP_OK": backup_ok,
        "RESTORE_OK": restore_ok,
        "RESTART_OK": restart_ok,
        "BACKUP_RESTORE_OK": bool(backup_ok and restore_ok),
        "RESTART_DURABILITY_OK": restart_ok,
        "auth_required_env": auth_required,
        "steps": steps,
        "blockers": blockers,
        "note": (
            "File DB supplemental scripts must not be treated as Postgres beta proof. "
            "This evidence file is written only from actual probe results."
        ),
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    gate = beta_gate_checks()
    entry = evaluate_entry_criteria()
    intake = intake_slots_dashboard()
    sessions = writer_session_dashboard()

    activation = {
        "phase": 24,
        "executed_at": _now(),
        "fabricated": False,
        "beta_gate": entry["state"],
        "classification": entry["classification"],
        "entry_ready": entry["entry_ready"],
        "gate_overall": gate["overall"],
        "blockers": entry["blockers"] + blockers,
        "real_full_packages": pop.get("real_full_sanitized"),
        "real_partial_packages": pop.get("real_partial_sanitized"),
        "writers": sessions.get("writers"),
        "paired_sessions_complete": sessions.get("paired_complete"),
        "intake_display": intake.get("display"),
        "diversity": diversity,
        "postgres_evidence_path": EVIDENCE.as_posix(),
        "advanced_to_BETA_READY": False,
        "advanced_to_CONTROLLED_BETA_RUNNING": False,
        "reason_not_advanced": "entry criteria not satisfied — refusing to mark BETA_READY",
        "roi_published": False,
        "secrets_exposed": False,
    }

    # Only advance if truly ready — never fabricate
    if entry["entry_ready"] and postgres_executed and backup_ok and restore_ok and restart_ok:
        from app.domain.beta_entry_gate import save_gate_runtime_state

        save_gate_runtime_state("BETA_READY", note="Phase 24 activation — entry criteria met")
        activation["advanced_to_BETA_READY"] = True
        save_gate_runtime_state(
            "CONTROLLED_BETA_RUNNING",
            note="Phase 24 entered controlled beta running",
        )
        activation["advanced_to_CONTROLLED_BETA_RUNNING"] = True
        activation["reason_not_advanced"] = None
        activation["beta_gate"] = "CONTROLLED_BETA_RUNNING"

    ACTIVATION.write_text(json.dumps(activation, indent=2) + "\n", encoding="utf-8")
    print("PHASE24_ACTIVATION", activation["beta_gate"])
    print("WROTE", EVIDENCE.as_posix())
    print("WROTE", ACTIVATION.as_posix())
    for b in activation["blockers"][:20]:
        print("  blocker:", b)
    return 0 if activation.get("advanced_to_BETA_READY") else 2


if __name__ == "__main__":
    raise SystemExit(main())
