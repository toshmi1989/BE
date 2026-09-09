"""Document completeness assessment — Phase 12B.4.

Readiness is informational and does NOT replace DRAFT/REVIEW/FINAL gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DocumentCompletenessResult:
    total_sections: int = 0
    resolved_blocks: int = 0
    proposed_blocks: int = 0
    unresolved_blocks: int = 0
    blocked_blocks: int = 0
    static_blocks: int = 0
    conditional_blocks: int = 0
    missing_sources: list[str] = field(default_factory=list)
    critical_gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    readiness: str = "BLOCKED"  # READY|READY_WITH_WARNINGS|BLOCKED
    gate_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finding_blocking(f: Any) -> bool:
    if isinstance(f, dict):
        return bool(f.get("blocking"))
    return bool(getattr(f, "blocking", False))


def _finding_severity(f: Any) -> str:
    if isinstance(f, dict):
        return str(f.get("severity") or "").upper()
    return str(getattr(f, "severity", "") or "").upper()


def _finding_message(f: Any) -> str:
    if isinstance(f, dict):
        return str(f.get("message") or f.get("code") or "")
    return str(getattr(f, "message", None) or getattr(f, "code", "") or "")


def assess_document_completeness(
    assembled: dict,
    qa_findings: list | None = None,
) -> DocumentCompletenessResult:
    """Count resolution states and derive informational readiness."""
    sections = list(assembled.get("sections") or [])
    qa_findings = list(qa_findings or [])
    result = DocumentCompletenessResult(total_sections=len(sections))

    for s in sections:
        for b in s.get("content_blocks") or []:
            status = str(b.get("resolution_status") or "").upper()
            ctype = str(b.get("content_type") or "").upper()
            origin = str(b.get("origin") or "").upper()

            if status == "RESOLVED":
                result.resolved_blocks += 1
            elif status == "PROPOSED":
                result.proposed_blocks += 1
            elif status == "BLOCKED":
                result.blocked_blocks += 1
            elif status == "UNRESOLVED" or b.get("unresolved"):
                result.unresolved_blocks += 1
            elif status:
                # Unknown status — count unresolved if markers present
                if b.get("unresolved"):
                    result.unresolved_blocks += 1

            if origin == "STATIC_VERIFIED" or ctype == "STATIC_VERIFIED":
                result.static_blocks += 1
            if ctype == "CONDITIONAL" or origin == "CONDITIONAL" or b.get("type") == "CONDITIONAL":
                result.conditional_blocks += 1

            for g in b.get("knowledge_gaps") or []:
                if isinstance(g, dict) and (
                    g.get("blocking") or str(g.get("importance") or "").upper() in {"CRITICAL", "HIGH"}
                ):
                    q = str(g.get("question") or g.get("domain") or "gap")
                    if q not in result.critical_gaps:
                        result.critical_gaps.append(q)

            for u in b.get("unresolved") or []:
                marker = str(u)
                if "SOURCE" in marker.upper() and marker not in result.missing_sources:
                    result.missing_sources.append(marker)

    draft_status = str(assembled.get("status") or "").upper()
    blocking_qa = [f for f in qa_findings if _finding_blocking(f)]
    critical_qa = [f for f in qa_findings if _finding_severity(f) == "CRITICAL"]
    warning_qa = [
        f
        for f in qa_findings
        if _finding_severity(f) == "WARNING" and not _finding_blocking(f)
    ]

    for f in warning_qa:
        msg = _finding_message(f)
        if msg and msg not in result.warnings:
            result.warnings.append(msg)

    has_critical_unresolved = result.unresolved_blocks > 0 and (
        result.critical_gaps or draft_status == "BLOCKED" or result.blocked_blocks > 0
    )

    if blocking_qa or critical_qa or draft_status == "BLOCKED" or result.blocked_blocks > 0:
        result.readiness = "BLOCKED"
        if draft_status == "BLOCKED":
            result.gate_hints.append("Draft status is BLOCKED")
        if blocking_qa or critical_qa:
            result.gate_hints.append("Blocking or critical QA findings present")
        if result.blocked_blocks:
            result.gate_hints.append(f"{result.blocked_blocks} blocked content block(s)")
        if result.critical_gaps:
            result.gate_hints.append("Critical knowledge gaps remain")
    elif has_critical_unresolved and result.critical_gaps:
        result.readiness = "BLOCKED"
        result.gate_hints.append("Critical unresolved required content")
    elif warning_qa or result.unresolved_blocks or result.proposed_blocks or result.warnings:
        result.readiness = "READY_WITH_WARNINGS"
        if result.unresolved_blocks:
            result.gate_hints.append(f"{result.unresolved_blocks} unresolved block(s)")
        if result.proposed_blocks:
            result.gate_hints.append(f"{result.proposed_blocks} proposed block(s)")
        if warning_qa:
            result.gate_hints.append("Non-blocking QA warnings present")
    else:
        result.readiness = "READY"
        result.gate_hints.append("No blocking gaps detected (informational; FINAL gate separate)")

    return result
