"""Validation issue types and severity rules."""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any


SEVERITIES = ("CRITICAL", "ERROR", "WARNING", "INFO")
ISSUE_STATUSES = ("OPEN", "ACKNOWLEDGED", "RESOLVED", "IGNORED")

BLOCKING_SEVERITIES = frozenset({"CRITICAL", "ERROR"})


@dataclass
class IssueDraft:
    category: str
    severity: str
    rule_id: str
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    field: str | None = None
    details: dict[str, Any] = dc_field(default_factory=dict)
    source_ids: list[str] = dc_field(default_factory=list)
    blocking: bool | None = None

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"Invalid severity: {self.severity}")
        if self.blocking is None:
            self.blocking = self.severity in BLOCKING_SEVERITIES


def summarize_issues(issues: list[IssueDraft] | list[dict]) -> dict[str, Any]:
    counts = {"critical": 0, "errors": 0, "warnings": 0, "info": 0}
    blocking = False
    for raw in issues:
        if isinstance(raw, IssueDraft):
            sev = raw.severity
            is_blocking = bool(raw.blocking)
            status = "OPEN"
        else:
            sev = str(raw.get("severity", ""))
            is_blocking = bool(raw.get("blocking"))
            status = str(raw.get("status", "OPEN"))
        key = {
            "CRITICAL": "critical",
            "ERROR": "errors",
            "WARNING": "warnings",
            "INFO": "info",
        }.get(sev)
        if key:
            counts[key] += 1
        if is_blocking and status in {"OPEN", "ACKNOWLEDGED"}:
            blocking = True
    return {**counts, "blocking": blocking}
