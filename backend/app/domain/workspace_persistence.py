"""Phase 17 — Flush / hydrate Phase 14–16 stores into DB (survives restart)."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.decision_context import DecisionContext, build_context_from_package
from app.domain.decision_engine import recompute_decisions
from app.domain.decision_store import clear_decision_store, put_context, put_decisions
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_package import StudyInputPackage
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.study_input_store import get_package, list_packages, put_package
from app.domain.study_workspace import (
    audit_timeline,
    list_protocol_drafts,
    reset_workspace_store,
    restore_audit_timeline,
    restore_protocol_drafts,
    restore_workspace_meta,
)
from app.models.workspace_persistence import (
    WorkspaceAuditEvent,
    WorkspaceProtocolDraftRecord,
    WorkspaceStateBag,
)


def _json_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _package_for_study(study_key: str) -> StudyInputPackage | None:
    for p in list_packages():
        if getattr(p, "study_id", None) == study_key:
            return p
    pkgs = list_packages()
    return pkgs[-1] if pkgs else None


def collect_bundle(study_key: str) -> dict[str, Any]:
    pkg = _package_for_study(study_key)
    drafts = list_protocol_drafts(study_key)
    audit = audit_timeline(study_key)
    package_payload = pkg.to_dict() if pkg else None
    bundle = {
        "study_key": study_key,
        "package_payload": package_payload,
        "decisions_payload": [],  # recomputed on hydrate from package (deterministic)
        "context_payload": None,
        "sample_size_payload": [],
        "statistics_payload": [],
        "workspace_meta": {
            "protocol_drafts": drafts,
            "audit": audit,
        },
    }
    bundle["content_hash"] = _json_hash(
        {"package": package_payload, "drafts": drafts, "audit_ids": [a.get("id") for a in audit]}
    )
    return bundle


def persist_workspace_bundle(
    db: Session,
    study_key: str,
    *,
    organization_id: UUID | None = None,
) -> WorkspaceStateBag:
    """Idempotent upsert of workspace bag by content_hash."""
    bundle = collect_bundle(study_key)
    row = db.execute(
        select(WorkspaceStateBag).where(WorkspaceStateBag.study_key == study_key)
    ).scalar_one_or_none()
    # Never clobber a persisted package with None after process-cache invalidation
    if bundle["package_payload"] is None and row is not None and row.package_payload:
        bundle["package_payload"] = row.package_payload
        bundle["content_hash"] = _json_hash(
            {
                "package": bundle["package_payload"],
                "drafts": bundle["workspace_meta"].get("protocol_drafts"),
                "audit_ids": [a.get("id") for a in (bundle["workspace_meta"].get("audit") or [])],
            }
        )
    if row and row.content_hash == bundle["content_hash"]:
        return row
    if row is None:
        row = WorkspaceStateBag(study_key=study_key)
        db.add(row)
    row.organization_id = organization_id or row.organization_id
    row.package_payload = bundle["package_payload"]
    row.decisions_payload = bundle["decisions_payload"]
    row.context_payload = bundle["context_payload"]
    row.sample_size_payload = bundle["sample_size_payload"]
    row.statistics_payload = bundle["statistics_payload"]
    row.workspace_meta = bundle["workspace_meta"]
    row.content_hash = bundle["content_hash"]

    for d in bundle["workspace_meta"].get("protocol_drafts") or []:
        existing = db.execute(
            select(WorkspaceProtocolDraftRecord).where(
                WorkspaceProtocolDraftRecord.protocol_id == d["protocol_id"]
            )
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(
            WorkspaceProtocolDraftRecord(
                protocol_id=d["protocol_id"],
                study_key=study_key,
                organization_id=organization_id,
                version=int(d["version"]),
                snapshot_id=d.get("based_on_snapshot")
                if isinstance(d.get("based_on_snapshot"), str)
                else None,
                status=d.get("status") or "REVIEW",
                created_by=d.get("created_by") or "system",
                based_on={
                    "snapshot": d.get("based_on_snapshot"),
                    "decisions": d.get("based_on_decisions"),
                    "evidence": d.get("based_on_evidence"),
                    "statistics": d.get("based_on_statistics"),
                    "sample_size": d.get("based_on_sample_size"),
                },
                sections_payload=d.get("sections_summary") or [],
                content_hash=_json_hash(d),
            )
        )

    for e in bundle["workspace_meta"].get("audit") or []:
        eid = e.get("id")
        if not eid:
            continue
        exists = db.execute(
            select(WorkspaceAuditEvent).where(WorkspaceAuditEvent.event_id == eid)
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(
            WorkspaceAuditEvent(
                event_id=eid,
                organization_id=organization_id,
                study_key=study_key,
                event_type=e.get("event") or "EVENT",
                entity_type="study",
                entity_id=study_key,
                old_value={"value": e.get("old_value")} if e.get("old_value") is not None else None,
                new_value={"value": e.get("new_value")} if e.get("new_value") is not None else None,
                reason=e.get("reason"),
                who=e.get("who"),
            )
        )

    db.commit()
    db.refresh(row)
    return row


def hydrate_workspace_bundle(db: Session, study_key: str, *, clear_memory: bool = True) -> bool:
    """Load bag from DB into process memory. Returns False if missing."""
    row = db.execute(
        select(WorkspaceStateBag).where(WorkspaceStateBag.study_key == study_key)
    ).scalar_one_or_none()
    if row is None:
        return False
    if clear_memory:
        reset_workspace_store()
        reset_sample_size_store()
        reset_statistics_store()
        clear_decision_store()
        clear_study_input()

    pkg = None
    if row.package_payload:
        pkg = StudyInputPackage.from_dict(row.package_payload)
        put_package(pkg)

    meta = row.workspace_meta or {}
    if meta.get("protocol_drafts"):
        restore_protocol_drafts(study_key, meta["protocol_drafts"])
    if meta.get("audit"):
        restore_audit_timeline(study_key, meta["audit"])
    if meta.get("workspace"):
        restore_workspace_meta(study_key, meta["workspace"])

    # Also hydrate drafts from dedicated table if memory empty
    if not list_protocol_drafts(study_key):
        draft_rows = (
            db.execute(
                select(WorkspaceProtocolDraftRecord)
                .where(WorkspaceProtocolDraftRecord.study_key == study_key)
                .order_by(WorkspaceProtocolDraftRecord.version)
            )
            .scalars()
            .all()
        )
        if draft_rows:
            restore_protocol_drafts(
                study_key,
                [
                    {
                        "protocol_id": r.protocol_id,
                        "study_id": study_key,
                        "version": r.version,
                        "status": r.status,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "created_by": r.created_by,
                        "based_on_snapshot": (r.based_on or {}).get("snapshot"),
                        "based_on_decisions": (r.based_on or {}).get("decisions"),
                        "based_on_evidence": (r.based_on or {}).get("evidence"),
                        "based_on_statistics": (r.based_on or {}).get("statistics"),
                        "based_on_sample_size": (r.based_on or {}).get("sample_size"),
                        "sections_summary": r.sections_payload or [],
                        "immutable": True,
                    }
                    for r in draft_rows
                ],
            )

    # Recompute recommendations from package (deterministic; never auto-APPROVED)
    if pkg:
        ctx = build_context_from_package(pkg, study_id=study_key)
        put_context(study_key, ctx, package_id=pkg.package_id)
        decisions = recompute_decisions(ctx)
        put_decisions(study_key, decisions, package_id=pkg.package_id)

    return True


def simulate_process_restart(db: Session, study_key: str) -> bool:
    """Test helper: clear memory then hydrate from DB."""
    return hydrate_workspace_bundle(db, study_key, clear_memory=True)
