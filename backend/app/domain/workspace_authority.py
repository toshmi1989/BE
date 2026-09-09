"""Phase 17.5 — DB-authoritative workspace access (cache is optimization only).

Policy:
- DB is the source of truth for persisted workspace state.
- Process memory may hold a working set after hydrate.
- Every API read that returns canonical state MUST hydrate from DB first
  (for that study), so multi-worker / multi-process cannot serve stale cache.
- After mutations: persist to DB then invalidate the study's process cache.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.decision_store import clear_decision_store, list_decisions
from app.domain.research_evidence_store import clear_research_evidence_store
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.study_input_store import get_package, list_packages
from app.domain.study_workspace import (
    build_preflight,
    build_workspace_summary,
    compute_readiness,
    list_protocol_drafts,
    reset_workspace_store,
    restore_audit_timeline,
    restore_protocol_drafts,
)
from app.domain.workspace_persistence import (
    hydrate_workspace_bundle,
    persist_workspace_bundle,
)


def invalidate_study_cache(study_key: str) -> None:
    """Drop process-local state for one study. Does not touch DB."""
    # Global clears are safe: next read rehydrates from DB for the study in focus.
    # Multi-study workers rehydrate per request anyway.
    reset_workspace_store()
    reset_sample_size_store()
    reset_statistics_store()
    clear_decision_store()
    clear_study_input()
    clear_research_evidence_store()


def ensure_db_authoritative(db: Session, study_key: str) -> bool:
    """Load authoritative state from DB into process memory (DB wins)."""
    return hydrate_workspace_bundle(db, study_key, clear_memory=True)


def read_workspace_summary(
    db: Session,
    study_key: str,
    *,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Canonical workspace read — always DB-first."""
    ensure_db_authoritative(db, study_key)
    from app.domain.workspace_documents import list_study_documents

    docs = list_study_documents(db, study_key)
    return build_workspace_summary(study_key, package_id=package_id, document_count=len(docs))


def read_readiness(db: Session, study_key: str, *, package_id: str | None = None) -> dict[str, Any]:
    ensure_db_authoritative(db, study_key)
    return compute_readiness(study_key, package_id=package_id)


def read_preflight(db: Session, study_key: str, *, package_id: str | None = None) -> dict[str, Any]:
    ensure_db_authoritative(db, study_key)
    return build_preflight(study_key, package_id=package_id)


def after_mutation(
    db: Session,
    study_key: str,
    *,
    organization_id: UUID | None = None,
) -> None:
    """Persist mutation to DB then invalidate process cache (DB remains SoT).

    When persistence tables are unavailable (memory-only fixtures), keep the
    in-process working set instead of wiping it.
    """
    row = persist_workspace_bundle(db, study_key, organization_id=organization_id)
    if row is None:
        return
    try:
        from app.domain.workspace_study_service import sync_study_summary

        sync_study_summary(db, study_key, organization_id=organization_id)
    except Exception:
        # Catalog sync is best-effort; persistence already succeeded.
        pass
    invalidate_study_cache(study_key)
