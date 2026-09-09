"""Research audit log — Phase 15.3."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_AUDIT: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ResearchAuditEvent:
    action: str
    id: str = field(default_factory=lambda: f"RAE-{uuid4().hex[:10]}")
    study_id: str | None = None
    task_id: str | None = None
    actor: str | None = None
    provider: str | None = None
    query: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    at: str = field(default_factory=_now)
    study_mutated: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["study_mutated"] = False
        return d


def audit_log(
    action: str,
    *,
    study_id: str | None = None,
    task_id: str | None = None,
    actor: str | None = None,
    provider: str | None = None,
    query: str | None = None,
    details: dict[str, Any] | None = None,
) -> ResearchAuditEvent:
    ev = ResearchAuditEvent(
        action=action,
        study_id=study_id,
        task_id=task_id,
        actor=actor,
        provider=provider,
        query=query,
        details=details or {},
    )
    _AUDIT.append(ev.to_dict())
    return ev


def list_audit(*, task_id: str | None = None, study_id: str | None = None) -> list[dict[str, Any]]:
    out = list(_AUDIT)
    if task_id:
        out = [e for e in out if e.get("task_id") == task_id]
    if study_id:
        out = [e for e in out if e.get("study_id") == study_id]
    return out


def clear_audit() -> None:
    _AUDIT.clear()
