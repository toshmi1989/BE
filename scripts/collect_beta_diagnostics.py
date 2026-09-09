#!/usr/bin/env python3
"""Collect beta diagnostics — never includes AUTH_SECRET / passwords / tokens."""

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
OUT = ROOT / "fixtures" / "field_study" / "phase25_diagnostics.json"

REDACT_KEYS = {"AUTH_SECRET", "PASSWORD", "TOKEN", "SECRET", "POSTGRES_PASSWORD"}


def _safe_env() -> dict[str, str]:
    out = {}
    for k, v in os.environ.items():
        ku = k.upper()
        if any(x in ku for x in REDACT_KEYS):
            out[k] = "<redacted>" if v else "<unset>"
        elif k in {"DATABASE_URL"} and v:
            # redact password in URL
            if "://" in v and "@" in v:
                scheme, rest = v.split("://", 1)
                if "@" in rest and ":" in rest.split("@", 1)[0]:
                    user = rest.split("@", 1)[0].split(":", 1)[0]
                    host = rest.split("@", 1)[1]
                    out[k] = f"{scheme}://{user}:<redacted>@{host}"
                else:
                    out[k] = "<redacted_url>"
            else:
                out[k] = v
        elif k.startswith(("AUTH_", "POSTGRES_", "DATABASE_", "DOCUMENT_", "AI_", "CORS_", "VITE_")):
            out[k] = v
    return out


def main() -> int:
    from app.core.config import get_settings
    from app.domain.beta_entry_gate import evaluate_entry_criteria
    from app.domain.real_package_registry import population_status

    get_settings.cache_clear()
    settings = get_settings()

    git_rev = None
    try:
        git_rev = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        git_rev = None

    migration_rev = None
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(ROOT / "backend" / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        migration_rev = script.get_current_head()
    except Exception as e:  # noqa: BLE001
        migration_rev = f"unavailable:{type(e).__name__}"

    db_ok = False
    try:
        from app.core.db import configure_engine, get_engine
        from sqlalchemy import text

        configure_engine(settings.database_url)
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:  # noqa: BLE001
        db_ok = False
        db_err = type(e).__name__
    else:
        db_err = None

    entry = evaluate_entry_criteria()
    pop = population_status()

    report = {
        "phase": 25,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "version": settings.app_version,
        "git_revision": git_rev,
        "migration_head": migration_rev,
        "docker_cli": bool(shutil.which("docker")),
        "database_connectivity": "ok" if db_ok else f"fail:{db_err}",
        "database_url_scheme": (settings.database_url or "").split(":", 1)[0],
        "auth_required": bool(settings.auth_required),
        "auth_secret_configured": bool(settings.auth_secret),
        "auth_secret_value": None,  # never
        "ai_enabled": settings.ai_enabled,
        "document_storage_root": settings.document_storage_root,
        "population": {
            "real_full": pop.get("real_full_sanitized"),
            "real_partial": pop.get("real_partial_sanitized"),
            "synthetic_counted_as_real": pop.get("synthetic_counted_as_real"),
        },
        "beta_gate": {
            "state": entry.get("state"),
            "entry_ready": entry.get("entry_ready"),
            "blockers": entry.get("blockers"),
        },
        "safe_env": _safe_env(),
        "secrets_included": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("DIAGNOSTICS_OK", OUT.as_posix())
    print(json.dumps({k: report[k] for k in ("version", "git_revision", "migration_head", "docker_cli", "database_connectivity", "auth_required")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
