"""Phase 17 — Immutable canonical snapshot versioning (DB-authoritative, concurrency-safe)."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.study_input_store import list_packages
from app.domain.study_workspace import append_audit
from app.models.workspace_persistence import WorkspaceSnapshotRecord


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _pkg(study_key: str):
    for p in list_packages():
        if p.study_id == study_key:
            return p
    pkgs = list_packages()
    return pkgs[-1] if pkgs else None


def create_snapshot(
    db: Session,
    study_key: str,
    *,
    created_by: str,
    organization_id: UUID | None = None,
    based_on_decision_ids: list[str] | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create immutable snapshot vN with unique(study_key, version) protection."""
    if idempotency_key:
        prior = db.execute(
            select(WorkspaceSnapshotRecord).where(
                WorkspaceSnapshotRecord.study_key == study_key,
                WorkspaceSnapshotRecord.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if prior:
            return _serialize(prior)

    pkg = _pkg(study_key)
    payload = {
        "study_key": study_key,
        "package_id": pkg.package_id if pkg else None,
        "candidates": [c.to_dict() for c in (pkg.candidates if pkg else [])],
        "conflicts": list(pkg.conflicts if pkg else []),
        "documents": [d.to_dict() for d in (pkg.documents if pkg else [])],
        "coverage": dict(pkg.coverage if pkg else {}),
        "decision_ids": list(based_on_decision_ids or []),
        "note": "CURRENT_STUDY_FACT — not regulatory requirement",
    }
    content_hash = _hash(payload)
    existing = (
        db.execute(
            select(WorkspaceSnapshotRecord)
            .where(
                WorkspaceSnapshotRecord.study_key == study_key,
                WorkspaceSnapshotRecord.content_hash == content_hash,
            )
            .order_by(WorkspaceSnapshotRecord.version.desc())
        )
        .scalars()
        .first()
    )
    if existing:
        return _serialize(existing)

    # Retry on unique(study_key, version) race
    last_err: Exception | None = None
    for _ in range(8):
        max_v = db.execute(
            select(func.max(WorkspaceSnapshotRecord.version)).where(
                WorkspaceSnapshotRecord.study_key == study_key
            )
        ).scalar()
        version = int(max_v or 0) + 1
        snap_id = f"SNAP-{study_key}-{version}-{uuid4().hex[:6]}"
        row = WorkspaceSnapshotRecord(
            snapshot_id=snap_id,
            study_key=study_key,
            organization_id=organization_id,
            version=version,
            status="ACTIVE",
            created_by=created_by,
            payload=payload,
            based_on_decision_ids=list(based_on_decision_ids or []),
            content_hash=content_hash,
            idempotency_key=idempotency_key,
        )
        try:
            db.add(row)
            db.commit()
            db.refresh(row)
            append_audit(
                study_key,
                event="SNAPSHOT_CREATED",
                who=created_by,
                what=f"Snapshot v{version}",
                new_value=snap_id,
                reason=reason,
            )
            return _serialize(row)
        except IntegrityError as e:
            db.rollback()
            last_err = e
            # Another worker may have created identical content or same version
            again = (
                db.execute(
                    select(WorkspaceSnapshotRecord)
                    .where(
                        WorkspaceSnapshotRecord.study_key == study_key,
                        WorkspaceSnapshotRecord.content_hash == content_hash,
                    )
                    .order_by(WorkspaceSnapshotRecord.version.desc())
                )
                .scalars()
                .first()
            )
            if again:
                return _serialize(again)
            if idempotency_key:
                prior = db.execute(
                    select(WorkspaceSnapshotRecord).where(
                        WorkspaceSnapshotRecord.study_key == study_key,
                        WorkspaceSnapshotRecord.idempotency_key == idempotency_key,
                    )
                ).scalar_one_or_none()
                if prior:
                    return _serialize(prior)
            time.sleep(0.01)
    raise RuntimeError(f"Failed to allocate snapshot version: {last_err}")


def list_snapshots(db: Session, study_key: str) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(WorkspaceSnapshotRecord)
            .where(WorkspaceSnapshotRecord.study_key == study_key)
            .order_by(WorkspaceSnapshotRecord.version)
        )
        .scalars()
        .all()
    )
    return [_serialize(r) for r in rows]


def get_snapshot(db: Session, snapshot_id: str) -> dict[str, Any] | None:
    row = db.execute(
        select(WorkspaceSnapshotRecord).where(WorkspaceSnapshotRecord.snapshot_id == snapshot_id)
    ).scalar_one_or_none()
    return _serialize(row) if row else None


def latest_snapshot(db: Session, study_key: str) -> dict[str, Any] | None:
    row = (
        db.execute(
            select(WorkspaceSnapshotRecord)
            .where(WorkspaceSnapshotRecord.study_key == study_key)
            .order_by(WorkspaceSnapshotRecord.version.desc())
        )
        .scalars()
        .first()
    )
    return _serialize(row) if row else None


def _serialize(row: WorkspaceSnapshotRecord) -> dict[str, Any]:
    return {
        "snapshot_id": row.snapshot_id,
        "study_id": row.study_key,
        "version": row.version,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "based_on_decision_ids": list(row.based_on_decision_ids or []),
        "content_hash": row.content_hash,
        "idempotency_key": getattr(row, "idempotency_key", None),
        "immutable": True,
        "payload": row.payload,
    }
