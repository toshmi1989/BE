"""Content validation CONTENT.* codes — Phase 12A.2."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.content_resolver import ResolvedContent, filter_decision_for_render


@dataclass
class ContentValidationFinding:
    code: str
    section: str | None
    severity: str
    blocking: bool
    message: str
    canonical_field: str | None = None
    source: str | None = None
    expected: str | None = None
    actual: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_resolved_contents(
    resolved: list[ResolvedContent],
    *,
    expert_decisions: list[dict] | None = None,
    legacy_template_values: dict[str, Any] | None = None,
    mark_proposed_as_final: bool = False,
) -> list[ContentValidationFinding]:
    findings: list[ContentValidationFinding] = []
    for r in resolved:
        for issue in r.validation_issues:
            findings.append(
                ContentValidationFinding(
                    code=str(issue.get("code") or "CONTENT.MISSING_SOURCE"),
                    section=r.section_code,
                    severity=str(issue.get("severity") or "WARNING"),
                    blocking=bool(issue.get("blocking")),
                    message=str(issue.get("message") or ""),
                    canonical_field=r.canonical_source,
                    source=r.source_type,
                )
            )
        if r.source_type == "MISSING" and r.content is None:
            # ensure missing source finding exists
            if not any(f.code == "CONTENT.MISSING_SOURCE" and f.section == r.section_code for f in findings):
                findings.append(
                    ContentValidationFinding(
                        code="CONTENT.MISSING_SOURCE",
                        section=r.section_code,
                        severity="WARNING",
                        blocking=False,
                        message=f"No resolved content for {r.section_code}",
                        source=r.source_type,
                    )
                )
        if mark_proposed_as_final and r.source_type.startswith("PROPOSED") and r.display_as_final:
            findings.append(
                ContentValidationFinding(
                    code="CONTENT.PROPOSED_AS_FINAL",
                    section=r.section_code,
                    severity="ERROR",
                    blocking=True,
                    message="PROPOSED content marked as final",
                    source=r.source_type,
                )
            )
        if r.knowledge_gaps:
            open_gaps = [g for g in r.knowledge_gaps if str(g.get("status") or "OPEN").upper() == "OPEN"]
            for g in open_gaps:
                findings.append(
                    ContentValidationFinding(
                        code="CONTENT.KNOWLEDGE_GAP_OPEN",
                        section=r.section_code,
                        severity="WARNING" if not g.get("blocking") else "ERROR",
                        blocking=bool(g.get("blocking")),
                        message=str(g.get("question") or "Open knowledge gap"),
                    )
                )

    for d in expert_decisions or []:
        st = str(d.get("status") or "").upper()
        if st in {"REJECTED", "SUPERSEDED"} and filter_decision_for_render(d) is None:
            if d.get("forced_render"):
                findings.append(
                    ContentValidationFinding(
                        code="CONTENT.STALE_DECISION",
                        section=None,
                        severity="ERROR",
                        blocking=True,
                        message=f"Stale/invalid decision {d.get('id')} status={st}",
                        source=st,
                    )
                )
        if st == "PROPOSED" and d.get("forced_render"):
            findings.append(
                ContentValidationFinding(
                    code="CONTENT.EXPERT_DECISION_INVALID",
                    section=None,
                    severity="ERROR",
                    blocking=True,
                    message="PROPOSED decision cannot be rendered as final",
                )
            )

    legacy_template_values = legacy_template_values or {}
    for field, legacy_val in legacy_template_values.items():
        canon = None
        # caller may pass pairs via special key
        if isinstance(legacy_val, dict) and "canonical" in legacy_val:
            canon = legacy_val.get("canonical")
            legacy_val = legacy_val.get("template")
        if canon is not None and str(canon) != str(legacy_val):
            findings.append(
                ContentValidationFinding(
                    code="CONTENT.LEGACY_TEMPLATE_VALUE",
                    section=None,
                    severity="WARNING",
                    blocking=False,
                    message=f"Legacy template value differs from canonical for {field}",
                    canonical_field=field,
                    expected=str(canon),
                    actual=str(legacy_val),
                )
            )
            findings.append(
                ContentValidationFinding(
                    code="CONTENT.CANONICAL_MISMATCH",
                    section=None,
                    severity="ERROR",
                    blocking=True,
                    message=f"Canonical mismatch for {field}",
                    canonical_field=field,
                    expected=str(canon),
                    actual=str(legacy_val),
                )
            )

    return findings
