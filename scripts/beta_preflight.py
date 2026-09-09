#!/usr/bin/env python3
"""Phase 22 — Controlled beta environment preflight.

Outputs PASS / WARN / BLOCK per check. Never prints secret values.
Exit code 0 if no BLOCK; 2 if any BLOCK.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _secret_strength(secret: str | None) -> tuple[str, str]:
    if not secret:
        return "BLOCK", "AUTH_SECRET not set"
    if secret in {"dev-only-change-me-phase17", "change-me", "secret", "password"}:
        return "BLOCK", "AUTH_SECRET is a known default / weak placeholder"
    if len(secret) < 24:
        return "BLOCK", "AUTH_SECRET too short (need >=24 chars)"
    return "PASS", "AUTH_SECRET present and length OK (value not shown)"


def run_preflight() -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    docker = shutil.which("docker")
    if docker:
        checks.append({"id": "docker", "result": "PASS", "detail": "docker CLI found"})
    else:
        checks.append(
            {
                "id": "docker",
                "result": "BLOCK",
                "detail": "Docker CLI not available — Postgres compose cannot run on this host",
            }
        )

    # Postgres / DB URL
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgresql"):
        checks.append({"id": "postgres_url", "result": "PASS", "detail": "DATABASE_URL is postgres"})
    elif db_url.startswith("sqlite"):
        checks.append(
            {
                "id": "postgres_url",
                "result": "BLOCK",
                "detail": "DATABASE_URL is sqlite — beta requires Postgres (file DB is supplemental only)",
            }
        )
    else:
        checks.append(
            {
                "id": "postgres_url",
                "result": "WARN" if not docker else "BLOCK",
                "detail": "DATABASE_URL not set to Postgres",
            }
        )

    # Auth
    auth_req = os.environ.get("AUTH_REQUIRED", "false").lower() in {"1", "true", "yes"}
    if auth_req:
        checks.append({"id": "auth_required", "result": "PASS", "detail": "AUTH_REQUIRED=true"})
    else:
        checks.append({"id": "auth_required", "result": "BLOCK", "detail": "AUTH_REQUIRED is not true"})

    strength, detail = _secret_strength(os.environ.get("AUTH_SECRET"))
    checks.append({"id": "auth_secret", "result": strength, "detail": detail})

    # Storage
    doc_root = Path(os.environ.get("DOCUMENT_STORAGE_ROOT", str(ROOT / "backend" / "data" / "documents")))
    try:
        doc_root.mkdir(parents=True, exist_ok=True)
        probe = doc_root / ".beta_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks.append({"id": "upload_writable", "result": "PASS", "detail": f"writable: {doc_root.as_posix()}"})
    except OSError as e:
        checks.append({"id": "upload_writable", "result": "BLOCK", "detail": f"not writable: {e}"})

    # Migrations / app import (best-effort)
    try:
        os.environ.setdefault("AI_ENABLED", "false")
        from app.core.config import get_settings
        from app.core.db import configure_engine, get_engine

        get_settings.cache_clear()
        settings = get_settings()
        url = os.environ.get("DATABASE_URL") or settings.database_url
        configure_engine(url)
        eng = get_engine()
        with eng.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        checks.append({"id": "db_reachable", "result": "PASS", "detail": "SELECT 1 OK"})
    except Exception as e:  # noqa: BLE001 — preflight must not crash
        checks.append({"id": "db_reachable", "result": "BLOCK", "detail": f"DB not reachable: {type(e).__name__}"})

    # Health/ready via optional base URL
    base = os.environ.get("BETA_API_BASE", "http://127.0.0.1:8000")
    try:
        import urllib.request

        with urllib.request.urlopen(f"{base}/api/health", timeout=3) as resp:
            if resp.status == 200:
                checks.append({"id": "health", "result": "PASS", "detail": f"{base}/api/health"})
            else:
                checks.append({"id": "health", "result": "WARN", "detail": f"status={resp.status}"})
        with urllib.request.urlopen(f"{base}/api/ready", timeout=3) as resp:
            if resp.status == 200:
                checks.append({"id": "readiness", "result": "PASS", "detail": f"{base}/api/ready"})
            else:
                checks.append({"id": "readiness", "result": "WARN", "detail": f"status={resp.status}"})
    except Exception:
        checks.append(
            {
                "id": "health",
                "result": "WARN",
                "detail": "API not reachable (start backend for health/ready checks)",
            }
        )
        checks.append({"id": "readiness", "result": "WARN", "detail": "API not reachable"})

    # Migrations current — informational if alembic present
    alembic_ini = ROOT / "backend" / "alembic.ini"
    if alembic_ini.exists():
        checks.append({"id": "migrations_config", "result": "PASS", "detail": "alembic.ini present"})
    else:
        checks.append({"id": "migrations_config", "result": "WARN", "detail": "alembic.ini missing"})

    # Real package honesty
    try:
        from app.domain.real_package_registry import population_status

        pop = population_status()
        if pop.get("synthetic_counted_as_real"):
            checks.append({"id": "real_packages", "result": "BLOCK", "detail": "synthetic counted as REAL"})
        else:
            n = pop.get("real_full_sanitized") or 0
            level = "PASS" if n >= 10 else "WARN"
            checks.append(
                {
                    "id": "real_packages",
                    "result": level,
                    "detail": f"full_real={n} (Controlled Beta needs >=10; not fabricated)",
                }
            )
    except Exception as e:  # noqa: BLE001
        checks.append({"id": "real_packages", "result": "WARN", "detail": type(e).__name__})

    blocks = [c for c in checks if c["result"] == "BLOCK"]
    warns = [c for c in checks if c["result"] == "WARN"]
    overall = "BLOCK" if blocks else ("WARN" if warns else "PASS")
    return {
        "overall": overall,
        "checks": checks,
        "block_count": len(blocks),
        "warn_count": len(warns),
        "pass_count": sum(1 for c in checks if c["result"] == "PASS"),
        "secrets_exposed": False,
        "note": "File DB evidence is supplemental and does not satisfy Postgres beta preflight",
    }


def main() -> int:
    report = run_preflight()
    print(f"BETA_PREFLIGHT {report['overall']}")
    for c in report["checks"]:
        print(f"  [{c['result']}] {c['id']}: {c['detail']}")
    print(f"summary pass={report['pass_count']} warn={report['warn_count']} block={report['block_count']}")
    return 2 if report["overall"] == "BLOCK" else 0


if __name__ == "__main__":
    raise SystemExit(main())
