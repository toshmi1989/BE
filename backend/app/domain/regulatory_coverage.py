"""RegulatoryCoverageReport — Phase 13.1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.regulatory_evidence_tasks import REGULATORY_EVIDENCE_TASKS, gap_for_missing_task_source
from app.domain.regulatory_source_classes import EVIDENCE_DOMAINS


COVERAGE_DOMAINS: tuple[str, ...] = (
    "DESIGN",
    "FOOD",
    "SAMPLING",
    "WASHOUT",
    "ANALYTE",
    "PK",
    "STATISTICS",
    "ELIGIBILITY",
    "SAFETY",
    "REFERENCE",
)


@dataclass
class DomainCoverage:
    domain: str
    required_tasks: list[str] = field(default_factory=list)
    available_source_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    verified_count: int = 0
    proposed_count: int = 0
    gaps: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RegulatoryCoverageReport:
    report_id: str
    package_status: str
    domains: list[DomainCoverage] = field(default_factory=list)
    total_sources: int = 0
    sources_present: int = 0
    sources_missing: int = 0
    verified_claims: int = 0
    proposed_claims: int = 0
    open_conflicts: int = 0
    open_review_items: int = 0
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    knowledge_rules_verified: int = 0
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_regulatory_coverage_report(
    *,
    report_id: str,
    package_status: str,
    sources: list[dict[str, Any]] | None = None,
    claims: list[dict[str, Any]] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    review_items: list[dict[str, Any]] | None = None,
    knowledge_gaps: list[dict[str, Any]] | None = None,
    knowledge_rules: list[dict[str, Any]] | None = None,
) -> RegulatoryCoverageReport:
    sources = list(sources or [])
    claims = list(claims or [])
    conflicts = list(conflicts or [])
    review_items = list(review_items or [])
    knowledge_gaps = list(knowledge_gaps or [])
    knowledge_rules = list(knowledge_rules or [])

    present = [s for s in sources if str(s.get("ingestion_status")) == "OK"]
    missing = [s for s in sources if str(s.get("ingestion_status")) == "MISSING"]

    verified_claims = [c for c in claims if str(c.get("verification_status")).upper() == "VERIFIED"]
    proposed_claims = [
        c
        for c in claims
        if str(c.get("verification_status")).upper() in {"UNVERIFIED", "EXTRACTED", "REVIEW_REQUIRED", "PROPOSED"}
    ]

    domains_out: list[DomainCoverage] = []
    for domain in COVERAGE_DOMAINS:
        tasks = [t for t in REGULATORY_EVIDENCE_TASKS if t.domain == domain]
        domain_claims = [c for c in claims if str(c.get("domain")).upper() == domain]
        domain_sources = [
            str(s.get("source_id"))
            for s in present
            if domain.lower() in str(s.get("title") or "").lower()
            or domain in str(s.get("notes") or "")
            or str(s.get("source_class")) in {"EEC_REGULATORY", "FDA_GUIDANCE", "EMA_GUIDANCE", "SMPC_OHLP"}
        ]
        # Prefer explicit domain tags on sources
        tagged = [str(s.get("source_id")) for s in present if domain in (s.get("domains") or [])]
        avail = sorted(set(tagged or domain_sources))
        gaps = []
        for t in tasks:
            # Gap if no claim for task and no official source present for package
            has_claim = any(
                t.task_code in (c.get("related_tasks") or []) or t.task_code in str(c.get("field_name") or "")
                for c in domain_claims
            )
            if not has_claim and not avail:
                gaps.append(gap_for_missing_task_source(t))
        domains_out.append(
            DomainCoverage(
                domain=domain,
                required_tasks=[t.task_code for t in tasks],
                available_source_ids=avail,
                claim_ids=[str(c.get("claim_id") or c.get("id") or "") for c in domain_claims],
                verified_count=sum(1 for c in domain_claims if str(c.get("verification_status")).upper() == "VERIFIED"),
                proposed_count=sum(
                    1
                    for c in domain_claims
                    if str(c.get("verification_status")).upper() != "VERIFIED"
                ),
                gaps=gaps,
                conflicts=[
                    str(cf.get("conflict_id") or cf.get("id") or "")
                    for cf in conflicts
                    if str(cf.get("resolution_status") or "OPEN") == "OPEN"
                    and (
                        domain.lower() in str(cf.get("affected_field") or "").lower()
                        or domain.lower() in str(cf.get("study_field") or "").lower()
                    )
                ],
            )
        )

    verified_rules = [
        r
        for r in knowledge_rules
        if str(r.get("status") or r.get("verification_status") or "").upper() == "VERIFIED"
    ]

    return RegulatoryCoverageReport(
        report_id=report_id,
        package_status=package_status,
        domains=domains_out,
        total_sources=len(sources),
        sources_present=len(present),
        sources_missing=len(missing),
        verified_claims=len(verified_claims),
        proposed_claims=len(proposed_claims),
        open_conflicts=sum(1 for c in conflicts if str(c.get("resolution_status") or "OPEN") == "OPEN"),
        open_review_items=sum(1 for i in review_items if str(i.get("status")) == "PENDING"),
        knowledge_gaps=list(knowledge_gaps),
        knowledge_rules_verified=len(verified_rules),
        notes="Coverage is evidence discovery status — not medical verification",
    )
