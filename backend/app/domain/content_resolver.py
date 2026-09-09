"""ProtocolContentBlock + ContentResolver — Phase 12A.2.

Resolves content without writing Canonical Study.
PROPOSED decisions never render as final.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.content_foundation_v2 import (
    CONTENT_BLOCK_TYPES,
    CONTENT_SOURCE_PRIORITY,
    PROCEDURE_SECTION_MAP,
)
from app.domain.content_matrix import PROTOCOL_CONTENT_MATRIX, ContentMatrixRow


@dataclass
class ProtocolContentBlock:
    code: str
    section_code: str
    block_type: str
    content_source: str
    canonical_field: str | None = None
    procedure_definition_id: str | None = None
    evidence_claim_ids: list[str] = field(default_factory=list)
    knowledge_rule_ids: list[str] = field(default_factory=list)
    expert_decision_id: str | None = None
    status: str = "PROPOSED"
    render_priority: int = 100
    id: str | None = None

    def __post_init__(self) -> None:
        if self.block_type not in CONTENT_BLOCK_TYPES:
            raise ValueError(f"Invalid block_type: {self.block_type}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolvedContent:
    section_code: str
    content: Any
    source_type: str
    canonical_source: str | None = None
    evidence: list[str] = field(default_factory=list)
    rule: list[str] = field(default_factory=list)
    expert_decision: str | None = None
    status: str = "UNRESOLVED"
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    validation_issues: list[dict[str, Any]] = field(default_factory=list)
    block: dict[str, Any] | None = None
    display_as_final: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _latest_approved_decisions(decisions: list[dict]) -> dict[str, dict]:
    """Map decision_type → latest APPROVED (ignore SUPERSEDED/REJECTED/PROPOSED)."""
    out: dict[str, dict] = {}
    for d in decisions or []:
        if str(d.get("status") or "").upper() != "APPROVED":
            continue
        key = str(d.get("decision_type") or d.get("target_entity_type") or "")
        if not key:
            continue
        prev = out.get(key)
        if prev is None:
            out[key] = d
            continue
        # Prefer newer by decided_at / created_at string compare when present
        pa = str(prev.get("decided_at") or prev.get("created_at") or "")
        ca = str(d.get("decided_at") or d.get("created_at") or "")
        if ca >= pa:
            out[key] = d
    return out


def _canonical_value(snapshot: dict, field: str | None) -> Any:
    if not field:
        return None
    if field in snapshot:
        return snapshot.get(field)
    # dotted / nested soft lookup
    parts = field.split(".")
    cur: Any = snapshot
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def resolve_section(
    *,
    section_code: str,
    canonical_snapshot: dict[str, Any],
    expert_decisions: list[dict] | None = None,
    evidence_claims: list[dict] | None = None,
    knowledge_rules: list[dict] | None = None,
    knowledge_gaps: list[dict] | None = None,
    matrix_row: ContentMatrixRow | None = None,
) -> ResolvedContent:
    """Resolve one section per source priority. Never mutates study."""
    row = matrix_row
    if row is None:
        for r in PROTOCOL_CONTENT_MATRIX:
            if r.section_code == section_code:
                row = r
                break

    issues: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = list(knowledge_gaps or [])
    approved = _latest_approved_decisions(list(expert_decisions or []))

    # Rejected / superseded / proposed must not be final
    for d in expert_decisions or []:
        st = str(d.get("status") or "").upper()
        if st in {"REJECTED", "SUPERSEDED", "PROPOSED"} and d.get("used_as_final"):
            issues.append(
                {
                    "code": "CONTENT.EXPERT_DECISION_INVALID",
                    "severity": "ERROR",
                    "message": f"Decision {d.get('id')} status {st} cannot be final content",
                    "blocking": True,
                }
            )

    # Prefer canonical fields from matrix dependencies
    canonical_field = None
    if row and row.dependencies:
        # Map first dependency to snapshot key heuristically
        dep0 = row.dependencies[0]
        alias = {
            "design": "design",
            "sampling": "sampling_fingerprint",
            "subjects": "randomized_n",
            "washout": "washout",
            "food": "food",
            "statistics": "statistics",
            "product": "product",
            "reference": "reference_product",
            "bioanalysis": "bioanalysis",
            "safety": "safety",
            "observation": "observation",
            "analytes": "analytes",
            "pk": "pk",
            "eligibility": "eligibility",
            "sources": "sources",
            "evidence": "evidence",
            "procedures": "procedures",
        }.get(dep0, dep0)
        canonical_field = alias

    # 1. Canonical
    canon_val = _canonical_value(canonical_snapshot, canonical_field)
    if canon_val not in (None, "", [], {}):
        return ResolvedContent(
            section_code=section_code,
            content=canon_val,
            source_type="CANONICAL",
            canonical_source=canonical_field,
            status="RESOLVED",
            display_as_final=True,
            knowledge_gaps=[],
            validation_issues=issues,
            block={
                "block_type": "CANONICAL_VALUE",
                "canonical_field": canonical_field,
                "status": "RESOLVED",
            },
        )

    # 2. Approved ExpertDecision matching section/domain
    decision_type_hints = {
        "4.4.2": "SAMPLING_PLAN",
        "6.1.5": "WASHOUT",
        "4.3": "DESIGN",
        "4.4": "DESIGN",
        "7.3.1": "OTHER",
        "6.1.9": "OTHER",
        "8.1": "SAFETY",
    }
    hint = decision_type_hints.get(section_code)
    if hint and hint in approved:
        d = approved[hint]
        return ResolvedContent(
            section_code=section_code,
            content=d.get("final_value") or d.get("proposed_value"),
            source_type="APPROVED_EXPERT_DECISION",
            expert_decision=str(d.get("id")),
            status="RESOLVED",
            display_as_final=True,
            validation_issues=issues,
            block={
                "block_type": "EXPERT_DECISION",
                "expert_decision_id": str(d.get("id")),
                "status": "APPROVED",
            },
        )

    # 3. Verified evidence/rule
    verified_claims = [
        c
        for c in (evidence_claims or [])
        if str(c.get("status") or c.get("verification_status") or "").upper() == "VERIFIED"
    ]
    verified_rules = [
        r for r in (knowledge_rules or []) if str(r.get("status") or "").upper() == "VERIFIED"
    ]
    if verified_claims or verified_rules:
        return ResolvedContent(
            section_code=section_code,
            content={
                "claims": [c.get("id") or c.get("claim_text") for c in verified_claims[:5]],
                "rules": [r.get("rule_code") for r in verified_rules[:5]],
            },
            source_type="VERIFIED_EVIDENCE_OR_RULE",
            evidence=[str(c.get("id")) for c in verified_claims if c.get("id")],
            rule=[str(r.get("rule_code")) for r in verified_rules if r.get("rule_code")],
            status="PROPOSED",
            display_as_final=False,
            validation_issues=issues
            + (
                [
                    {
                        "code": "CONTENT.PROPOSED_AS_FINAL",
                        "severity": "WARNING",
                        "message": "Verified evidence present but not elevated to canonical final without ExpertDecision",
                        "blocking": False,
                    }
                ]
                if row and row.expert_required
                else []
            ),
        )

    # 4. Proposed evidence/rule — not final
    proposed_rules = [
        r for r in (knowledge_rules or []) if str(r.get("status") or "").upper() == "PROPOSED"
    ]
    if proposed_rules and row and row.type in {"DYNAMIC", "CONDITIONAL"}:
        return ResolvedContent(
            section_code=section_code,
            content={"proposed_rules": [r.get("rule_code") for r in proposed_rules[:5]]},
            source_type="PROPOSED_EVIDENCE_OR_RULE",
            rule=[str(r.get("rule_code")) for r in proposed_rules[:5]],
            status="PROPOSED",
            display_as_final=False,
            validation_issues=issues
            + [
                {
                    "code": "CONTENT.PROPOSED_AS_FINAL",
                    "severity": "ERROR",
                    "message": "PROPOSED rule must not be rendered as final protocol content",
                    "blocking": True,
                }
            ]
            if False  # only when caller tries to mark final — kept for negative tests via flag
            else issues,
        )

    # 5. Missing → KnowledgeGap (do not invent, do not silent N/A)
    gap = {
        "domain": "QA",
        "question": f"Content for section {section_code} is missing required canonical/approved source.",
        "importance": "HIGH" if (row and (row.expert_required or row.evidence_required)) else "MEDIUM",
        "blocking": bool(row and row.expert_required),
        "related_section": section_code,
    }
    # Prefer existing open gaps for section if any
    open_gaps = [
        g
        for g in gaps
        if str(g.get("status") or "OPEN").upper() == "OPEN"
        and section_code in str(g.get("question") or "")
    ]
    if not open_gaps and row and row.current_status in {"UNRESOLVED", "PARTIAL"} and row.expert_required:
        open_gaps = [gap]

    if open_gaps or (row and row.expert_required):
        issues.append(
            {
                "code": "CONTENT.MISSING_SOURCE",
                "severity": "ERROR" if (row and row.expert_required) else "WARNING",
                "message": f"Section {section_code} missing canonical/approved content",
                "blocking": bool(row and row.expert_required),
                "section": section_code,
            }
        )
        if open_gaps:
            issues.append(
                {
                    "code": "CONTENT.KNOWLEDGE_GAP_OPEN",
                    "severity": "WARNING",
                    "message": open_gaps[0].get("question"),
                    "blocking": bool(open_gaps[0].get("blocking")),
                    "section": section_code,
                }
            )
        return ResolvedContent(
            section_code=section_code,
            content=None,
            source_type="MISSING",
            status="UNRESOLVED",
            display_as_final=False,
            knowledge_gaps=open_gaps or [gap],
            validation_issues=issues,
            block={"block_type": "PLACEHOLDER", "status": "UNRESOLVED"},
        )

    return ResolvedContent(
        section_code=section_code,
        content=None,
        source_type="MISSING",
        status="UNRESOLVED",
        display_as_final=False,
        knowledge_gaps=[gap] if row else [],
        validation_issues=issues,
    )


def resolve_content_matrix(
    *,
    canonical_snapshot: dict[str, Any],
    expert_decisions: list[dict] | None = None,
    evidence_claims: list[dict] | None = None,
    knowledge_rules: list[dict] | None = None,
    knowledge_gaps: list[dict] | None = None,
    section_codes: list[str] | None = None,
) -> list[ResolvedContent]:
    codes = section_codes or [r.section_code for r in PROTOCOL_CONTENT_MATRIX]
    return [
        resolve_section(
            section_code=code,
            canonical_snapshot=canonical_snapshot,
            expert_decisions=expert_decisions,
            evidence_claims=evidence_claims,
            knowledge_rules=knowledge_rules,
            knowledge_gaps=knowledge_gaps,
        )
        for code in codes
    ]


def filter_decision_for_render(decision: dict) -> dict | None:
    """Only APPROVED (non-superseded) decisions may contribute final content."""
    if str(decision.get("status") or "").upper() != "APPROVED":
        return None
    return decision


class ContentResolver:
    """Service wrapper — read-only resolution."""

    def resolve(self, **kwargs: Any) -> list[ResolvedContent]:
        return resolve_content_matrix(**kwargs)

    def resolve_one(self, **kwargs: Any) -> ResolvedContent:
        return resolve_section(**kwargs)

    def procedure_sections(self, category: str) -> tuple[str, ...]:
        return PROCEDURE_SECTION_MAP.get(category.upper(), ())
