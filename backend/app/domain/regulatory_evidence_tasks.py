"""Regulatory evidence tasks by domain — Phase 13.1.

Evidence discovery only. No numeric thresholds. No medical decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RegulatoryEvidenceTask:
    task_code: str
    domain: str
    title: str
    interview_hint: str | None = None
    related_rule_codes: tuple[str, ...] = ()
    status: str = "OPEN"  # OPEN | EVIDENCE_FOUND | GAP
    requires_official_source: bool = True


REGULATORY_EVIDENCE_TASKS: tuple[RegulatoryEvidenceTask, ...] = (
    # Design
    RegulatoryEvidenceTask("DESIGN_STANDARD_2X2", "DESIGN", "Evidence for standard 2×2 crossover", related_rule_codes=("DESIGN-01",)),
    RegulatoryEvidenceTask("DESIGN_HIGH_VARIABILITY", "DESIGN", "Evidence for high-variability / replicate designs", related_rule_codes=("DESIGN-02", "DESIGN-03")),
    RegulatoryEvidenceTask("DESIGN_REPLICATE", "DESIGN", "Evidence for replicate design", related_rule_codes=("DESIGN-02",)),
    RegulatoryEvidenceTask("DESIGN_ADAPTIVE", "DESIGN", "Evidence for adaptive design when CV/CI missing", related_rule_codes=("DESIGN-04",)),
    RegulatoryEvidenceTask("DESIGN_LONG_HALF_LIFE", "DESIGN", "Evidence for long half-life / parallel considerations", related_rule_codes=("DESIGN-05",)),
    RegulatoryEvidenceTask("DESIGN_ENDOGENOUS", "DESIGN", "Evidence for endogenous compounds", interview_hint="Decision 85 pp.41,56", related_rule_codes=()),
    # Food
    RegulatoryEvidenceTask("FOOD_FASTING", "FOOD", "Evidence for fasting condition", related_rule_codes=("FOOD-01",)),
    RegulatoryEvidenceTask("FOOD_FED", "FOOD", "Evidence for fed condition", interview_hint="Decision 85 p.44", related_rule_codes=("FOOD-01",)),
    RegulatoryEvidenceTask("FOOD_STANDARD_MEAL", "FOOD", "Evidence for standard fed meal", interview_hint="Decision 85 p.46", related_rule_codes=("FOOD-02",)),
    RegulatoryEvidenceTask("FOOD_ALTERNATIVE", "FOOD", "Evidence for alternative meal definitions", related_rule_codes=("FOOD-02",)),
    # Sampling
    RegulatoryEvidenceTask("SAMPLING_TMAX", "SAMPLING", "Evidence for sampling around Tmax"),
    RegulatoryEvidenceTask("SAMPLING_PRE_TMAX", "SAMPLING", "Evidence for pre-Tmax points"),
    RegulatoryEvidenceTask("SAMPLING_POST_TMAX", "SAMPLING", "Evidence for post-Tmax points"),
    RegulatoryEvidenceTask("SAMPLING_TERMINAL", "SAMPLING", "Evidence for terminal phase sampling"),
    RegulatoryEvidenceTask("SAMPLING_LAST_POINT", "SAMPLING", "Evidence for last sampling point"),
    RegulatoryEvidenceTask("SAMPLING_AUC_COVERAGE", "SAMPLING", "Evidence for AUC coverage requirements"),
    RegulatoryEvidenceTask("SAMPLING_LONG_HALF_LIFE_TRUNCATION", "SAMPLING", "Evidence for long half-life truncation"),
    # Washout
    RegulatoryEvidenceTask("WASHOUT_RULE", "WASHOUT", "Evidence for washout relative to half-life", related_rule_codes=("WASH-01",)),
    # Analyte
    RegulatoryEvidenceTask(
        "ANALYTE_SELECTION",
        "ANALYTE",
        "Evidence for analyte selection",
        interview_hint="Decision 85 p.50 subsection 6 section III of Rules",
        related_rule_codes=("ANALYTE-01",),
    ),
    # PK
    RegulatoryEvidenceTask("PK_PRIMARY_PARAMETERS", "PK", "Evidence for primary PK parameters"),
    RegulatoryEvidenceTask("PK_SECONDARY_PARAMETERS", "PK", "Evidence for secondary PK parameters"),
    RegulatoryEvidenceTask("AUC_DEFINITION", "PK", "Evidence for AUC0-t / AUC0-last / AUC0-x terminology"),
    RegulatoryEvidenceTask("AUC_TRUNCATION", "PK", "Evidence for AUC0-72 truncation"),
    RegulatoryEvidenceTask("TERMINAL_PARAMETERS", "PK", "Evidence for Kel / t1/2 / AUC0-inf"),
    # Statistics
    RegulatoryEvidenceTask("CVINTRA", "STATISTICS", "Evidence for CVintra use in sample size"),
    RegulatoryEvidenceTask("90CI", "STATISTICS", "Evidence for 90% CI BE criteria"),
    RegulatoryEvidenceTask("POWER", "STATISTICS", "Evidence for power assumptions"),
    RegulatoryEvidenceTask("ALPHA", "STATISTICS", "Evidence for alpha"),
    RegulatoryEvidenceTask("EXPECTED_RATIO", "STATISTICS", "Evidence for expected T/R ratio"),
    RegulatoryEvidenceTask("DROPOUT", "STATISTICS", "Evidence for dropout / reserve handling"),
    RegulatoryEvidenceTask("ADAPTIVE", "STATISTICS", "Evidence for adaptive sample-size approaches"),
    RegulatoryEvidenceTask("POTVIN_B", "STATISTICS", "Evidence for Potvin Method B (discovery only)"),
    RegulatoryEvidenceTask("POTVIN_C", "STATISTICS", "Evidence for Potvin Method C (discovery only)"),
    # Eligibility
    RegulatoryEvidenceTask("STANDARD_INCLUSION", "ELIGIBILITY", "Evidence for standard inclusion criteria"),
    RegulatoryEvidenceTask("STANDARD_EXCLUSION", "ELIGIBILITY", "Evidence for standard exclusion criteria"),
    RegulatoryEvidenceTask("CONCOMITANT_MEDICATION", "ELIGIBILITY", "Evidence for concomitant medication restrictions"),
    RegulatoryEvidenceTask("CYP", "ELIGIBILITY", "Evidence for CYP-related restrictions"),
    RegulatoryEvidenceTask("SMOKING", "ELIGIBILITY", "Evidence for smoking restrictions"),
    RegulatoryEvidenceTask("CONTRACEPTION", "ELIGIBILITY", "Evidence for contraception requirements"),
    RegulatoryEvidenceTask("VOMITING", "ELIGIBILITY", "Evidence for vomiting handling"),
    # Safety
    RegulatoryEvidenceTask(
        "STANDARD_BE_SAFETY",
        "SAFETY",
        "Evidence for standard BE safety monitoring",
        interview_hint="Expert: protocols after June 2026 as practical reference — if absent, KnowledgeGap",
    ),
    # Reference
    RegulatoryEvidenceTask(
        "REFERENCE_SELECTION",
        "REFERENCE",
        "Evidence for reference product selection",
        interview_hint="Decision 85 p.18",
        related_rule_codes=("REF-01",),
    ),
    # Ethics / reporting
    RegulatoryEvidenceTask("ETHICS_CONDUCT", "ETHICS", "Evidence for ethics / GCP conduct requirements"),
    RegulatoryEvidenceTask("REPORTING_REFERENCES", "REPORTING", "Evidence for reporting / reference conventions"),
)


PRIORITY_RULE_WORKSPACE: tuple[str, ...] = (
    "REF-01",
    "DESIGN-01",
    "DESIGN-02",
    "DESIGN-03",
    "DESIGN-04",
    "DESIGN-05",
    "FOOD-01",
    "FOOD-02",
    "WASH-01",
    "ANALYTE-01",
)


def tasks_for_domain(domain: str) -> list[RegulatoryEvidenceTask]:
    return [t for t in REGULATORY_EVIDENCE_TASKS if t.domain == domain]


def tasks_as_dicts() -> list[dict[str, Any]]:
    return [asdict(t) for t in REGULATORY_EVIDENCE_TASKS]


def gap_for_missing_task_source(task: RegulatoryEvidenceTask) -> dict[str, Any]:
    return {
        "code": f"REG.EVIDENCE.{task.task_code}.MISSING",
        "domain": task.domain,
        "question": f"Official source not found for evidence task: {task.title}",
        "task_code": task.task_code,
        "interview_hint": task.interview_hint,
        "related_rule_codes": list(task.related_rule_codes),
        "blocking": task.requires_official_source,
        "status": "OPEN",
    }
