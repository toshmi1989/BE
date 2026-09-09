"""Missing-input detection + input coverage — Phase 14."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from app.domain.study_input_classes import COVERAGE_DOMAINS, COVERAGE_STATES
from app.domain.study_input_package import CandidateStudyValue, StudyInputDocument, StudyInputPackage


# Requirement profiles for a normal BE writer package
REQUIRED_DOCUMENT_TYPES: dict[str, str] = {
    "DESIGN_OR_SYNOPSIS": "REQUIRED",  # at least one
    "SMPC": "REQUIRED",  # for product-specific medical/safety
    "CHECKLIST": "RECOMMENDED",
    "PREVIOUS_PROTOCOL": "OPTIONAL",
}

# Domain field profiles: critical subset must be present for COMPLETE
DOMAIN_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "ADMINISTRATIVE": ("study.protocol_number", "sponsor.name"),
    "TEST_PRODUCT": ("test_product.dose",),
    "REFERENCE_PRODUCT": ("reference_product.name", "reference_product.dose"),
    "DESIGN": ("design.randomized", "design.crossover", "design.periods"),
    "SUBJECTS": ("subjects.sex", "subjects.age_min", "subjects.randomized_n"),
    "TREATMENT": ("treatment.fasting",),
    "SAMPLING": ("sampling.times",),
    "WASHOUT": ("washout.duration",),
    "FOOD": ("food.condition",),
    "PK": ("pk.parameters",),
    "BIOANALYSIS": ("bioanalysis.analyte",),
    "SAFETY": ("safety.adverse_events",),
    "STATISTICS": ("statistics.method",),
}


@dataclass
class KnowledgeGap:
    code: str
    title: str
    severity: str = "HIGH"
    required_data: list[str] = field(default_factory=list)
    blocking: bool = True
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchTaskDraft:
    code: str
    title: str
    description: str
    priority: str = "HIGH"
    status: str = "OPEN"
    linked_gap_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def document_types_present(docs: list[StudyInputDocument]) -> set[str]:
    return {d.document_type for d in docs if d.role == "INPUT"}


def detect_missing_inputs(package: StudyInputPackage) -> tuple[list[KnowledgeGap], list[ResearchTaskDraft]]:
    types = document_types_present(package.documents)
    gaps: list[KnowledgeGap] = []
    tasks: list[ResearchTaskDraft] = []

    has_design_or_synopsis = bool(types & {"DESIGN", "SYNOPSIS"})
    if not has_design_or_synopsis:
        gaps.append(
            KnowledgeGap(
                code="MISSING_DESIGN_OR_SYNOPSIS",
                title="Design or Synopsis required for protocol assembly",
                severity="CRITICAL",
                required_data=["design basics", "subjects", "treatment/conditions"],
                blocking=True,
            )
        )

    if "SMPC" not in types:
        gaps.append(
            KnowledgeGap(
                code="MISSING_SMPC_REFERENCE_PRODUCT",
                title="Need current official product information for reference product",
                severity="HIGH",
                required_data=[
                    "product identity",
                    "dosage/form",
                    "contraindications",
                    "warnings",
                    "interactions",
                    "relevant PK",
                    "safety",
                ],
                blocking=True,
                notes="Do not fabricate medical information",
            )
        )
        tasks.append(
            ResearchTaskDraft(
                code="FIND_SMPC_REFERENCE_PRODUCT",
                title="Find current official SmPC / registered product information for reference product",
                description=(
                    "Locate current official SmPC or registered product information. "
                    "External results remain assistive until SOURCE→CLAIM→REVIEW→VERIFIED."
                ),
                priority="HIGH",
                linked_gap_code="MISSING_SMPC_REFERENCE_PRODUCT",
            )
        )

    # Design-only is OK without Synopsis
    if "SYNOPSIS" not in types and "DESIGN" in types:
        # recommended gap only — not blocking extraction
        gaps.append(
            KnowledgeGap(
                code="MISSING_SYNOPSIS_OPTIONAL",
                title="Synopsis not provided; Design-only input present",
                severity="LOW",
                required_data=[],
                blocking=False,
                notes="Extraction proceeds from DESIGN",
            )
        )

    return gaps, tasks


def build_input_coverage(
    package: StudyInputPackage,
    *,
    conflicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    conflicts = conflicts if conflicts is not None else package.conflicts
    conflict_fields = {
        str(c.get("field_path"))
        for c in conflicts
        if str(c.get("status") or "OPEN") in {"OPEN", "UNDER_REVIEW"}
    }
    by_path: dict[str, list[CandidateStudyValue]] = {}
    for c in package.candidates:
        if c.status == "REJECTED":
            continue
        by_path.setdefault(c.field_path, []).append(c)

    domains: dict[str, Any] = {}
    for domain, paths in COVERAGE_DOMAINS.items():
        required = DOMAIN_REQUIRED_FIELDS.get(domain, paths[:1])
        present_req = [p for p in required if p in by_path]
        present_all = [p for p in paths if p in by_path]
        domain_conflict = any(p in conflict_fields for p in paths)
        statuses = {c.status for p in present_all for c in by_path.get(p, [])}

        if domain_conflict:
            state = "CONFLICT"
        elif not present_req:
            state = "MISSING"
        elif len(present_req) < len(required) or len(present_all) < max(1, len(paths) // 2):
            state = "PARTIAL"
        elif "REVIEW_REQUIRED" in statuses and "VERIFIED" not in statuses:
            state = "REVIEW_REQUIRED"
        elif statuses and statuses <= {"VERIFIED"}:
            state = "VERIFIED"
        else:
            state = "PRESENT"

        assert state in COVERAGE_STATES
        domains[domain] = {
            "state": state,
            "required_present": present_req,
            "required_missing": [p for p in required if p not in by_path],
            "fields_present": present_all,
        }

    open_conflicts = [c for c in conflicts if str(c.get("status") or "OPEN") == "OPEN"]
    blocking = list(package.blocking_issues)
    for g in package.knowledge_gaps:
        if g.get("blocking"):
            blocking.append(str(g.get("code")))
    if open_conflicts:
        blocking.append("OPEN_CONFLICTS")

    ready = not any(
        d["state"] in {"MISSING", "CONFLICT"} for d in domains.values() if d["state"] != "NOT_APPLICABLE"
    ) and not open_conflicts and not any(g.get("blocking") for g in package.knowledge_gaps)

    return {
        "domains": domains,
        "ready_for_assembly": ready,
        "blocking_issues": sorted(set(blocking)),
        "open_conflict_count": len(open_conflicts),
    }
