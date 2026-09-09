"""Expert interview claims vs regulatory documents — Phase 13.1.

Interview = practice evidence. Not proof of regulatory requirement.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.domain.knowledge_seed import KNOWLEDGE_RULE_SEEDS
from app.domain.regulatory_claims import EvidenceProvenance, RegulatoryEvidenceClaim, build_claim
from app.domain.regulatory_evidence_manifest import DEFAULT_REGULATORY_ROOT


@dataclass(frozen=True)
class InterviewClaimSeed:
    claim_id: str
    domain: str
    field_name: str
    exact_text: str
    normalized_claim: str
    related_rule_codes: tuple[str, ...] = ()
    interview_section: str | None = None


# Derived from existing PROPOSED rule regulatory_hints / interview practice — NOT regulatory verification
INTERVIEW_CLAIM_SEEDS: tuple[InterviewClaimSeed, ...] = (
    InterviewClaimSeed(
        "INT-REF-01",
        "REFERENCE",
        "reference_selection",
        "Reference product selection should be justified per Decision 85 p.18 (writer interview).",
        "Interview practice: justify reference product using Decision 85 p.18",
        ("REF-01",),
        "reference_product",
    ),
    InterviewClaimSeed(
        "INT-FOOD-01",
        "FOOD",
        "food_condition",
        "Food determination referenced to Decision 85 p.44 (writer interview).",
        "Interview practice: food condition per Decision 85 p.44",
        ("FOOD-01",),
        "food",
    ),
    InterviewClaimSeed(
        "INT-FOOD-02",
        "FOOD",
        "fed_meal",
        "Fed meal concept referenced to Decision 85 p.46 (writer interview).",
        "Interview practice: fed meal per Decision 85 p.46",
        ("FOOD-02",),
        "food",
    ),
    InterviewClaimSeed(
        "INT-ENDOG-01",
        "DESIGN",
        "endogenous",
        "Endogenous compounds discussed with Decision 85 pp.41,56 (writer interview).",
        "Interview practice: endogenous compounds Decision 85 pp.41,56",
        (),
        "design",
    ),
    InterviewClaimSeed(
        "INT-ANALYTE-01",
        "ANALYTE",
        "analyte_selection",
        "Analyte selection referenced to Decision 85 p.50 subsection 6 section III of Rules (writer interview).",
        "Interview practice: analyte selection Decision 85 p.50 §6 III",
        ("ANALYTE-01",),
        "analyte",
    ),
    InterviewClaimSeed(
        "INT-SAFETY-01",
        "SAFETY",
        "be_safety",
        "Practical BE safety reference: protocols after June 2026 (writer interview). Not a verified regulatory checklist.",
        "Interview practice: post-June-2026 protocols as practical safety reference",
        (),
        "safety",
    ),
)


def interview_claims_as_evidence() -> list[RegulatoryEvidenceClaim]:
    out: list[RegulatoryEvidenceClaim] = []
    for seed in INTERVIEW_CLAIM_SEEDS:
        out.append(
            build_claim(
                claim_id=seed.claim_id,
                claim_kind="EXPERT_INTERVIEW_CLAIM",
                domain=seed.domain,
                field_name=seed.field_name,
                raw_extract=seed.exact_text,
                normalized_claim=seed.normalized_claim,
                confidence="MEDIUM",
                verification_status="UNVERIFIED",
                source_class="EXPERT_INTERVIEW",
                related_rule_codes=list(seed.related_rule_codes),
                provenance=EvidenceProvenance(
                    source_id="SRC-INTERVIEW-MW",
                    document_id="expert_interview",
                    source_version="1",
                    section=seed.interview_section,
                    quoted_text=seed.exact_text,
                    extraction_method="INTERVIEW_IMPORT",
                ),
            )
        )
    return out


def assert_interview_not_regulatory(claim: RegulatoryEvidenceClaim) -> bool:
    return claim.is_interview_claim() and not (
        claim.claim_kind == "REGULATORY_CLAIM" and claim.source_class != "EXPERT_INTERVIEW"
    )


def load_or_export_interview_json(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or (DEFAULT_REGULATORY_ROOT / "interview" / "interview_claims.json")
    if target.is_file():
        return list(json.loads(target.read_text(encoding="utf-8")))
    data = [asdict(s) for s in INTERVIEW_CLAIM_SEEDS]
    for d in data:
        d["source_type"] = "EXPERT_INTERVIEW"
        d["is_regulatory_document"] = False
    return data


def proposed_rules_remain_proposed(rules: list[dict[str, Any]] | None = None) -> bool:
    """Invariant: seed catalog rules stay PROPOSED unless explicitly verified elsewhere."""
    if rules is None:
        return all(s.status == "PROPOSED" for s in KNOWLEDGE_RULE_SEEDS)
    return all(str(r.get("status") or "PROPOSED").upper() == "PROPOSED" for r in rules)
