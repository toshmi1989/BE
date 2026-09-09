#!/usr/bin/env python3
"""Phase 18 — Backup / restore smoke check for workspace bags + artifacts metadata.

Usage (local SQLite file or Postgres URL):
  DATABASE_URL=sqlite:///./beta_backup_test.db python scripts/beta_backup_restore_check.py

Does not require Docker. Validates that persist → clear memory → hydrate restores
workspace drafts/audit and that artifact metadata rows survive.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'backend' / 'beta_backup_test.db'}")
os.environ.setdefault("AI_ENABLED", "false")
os.environ.setdefault("AUTH_REQUIRED", "false")


def main() -> int:
    from app.core.config import get_settings
    from app.core.db import Base, configure_engine, get_engine
    from app.core import db as db_module
    import app.models  # noqa: F401
    from app.domain.protocol_workflow import run_protocol_workflow
    from app.domain.study_workspace import list_protocol_drafts
    from app.domain.workspace_authority import ensure_db_authoritative, invalidate_study_cache
    from app.domain.workspace_persistence import persist_workspace_bundle
    from app.domain.workspace_snapshots import list_snapshots

    get_settings.cache_clear()
    url = os.environ["DATABASE_URL"]
    configure_engine(url)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    study = "UPDCB-02-BE-2026"
    out = run_protocol_workflow(study, use_golden_fixture=True, created_by="backup-check")
    db = db_module.SessionLocal()
    persist_workspace_bundle(db, study)
    drafts_before = list_protocol_drafts(study)
    snaps_before = list_snapshots(db, study)
    assert drafts_before, "expected protocol drafts before backup"
    assert snaps_before, "expected snapshots before backup"

    invalidate_study_cache(study)
    assert list_protocol_drafts(study) == []

    ok = ensure_db_authoritative(db, study)
    assert ok, "hydrate failed after simulated restore"
    drafts_after = list_protocol_drafts(study)
    assert len(drafts_after) == len(drafts_before)
    assert drafts_after[0]["protocol_id"] == drafts_before[0]["protocol_id"]
    snaps_after = list_snapshots(db, study)
    assert len(snaps_after) == len(snaps_before)
    db.close()
    print("BACKUP_RESTORE_OK", {"drafts": len(drafts_after), "snapshots": len(snaps_after), "workflow": out["workflow_id"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
