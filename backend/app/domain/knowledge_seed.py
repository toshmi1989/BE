"""Knowledge rule seed catalog — Phase 12A.1.

All interview-derived rules are PROPOSED with requires_expert_confirmation=True.
They evaluate / propose / gap only — never mutate Study.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class KnowledgeRuleSeed:
    rule_code: str
    name: str
    domain: str
    description: str
    condition_expression: str | None = None
    action_definition: dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    regulatory_hint: str | None = None
    notes: str = ""


KNOWLEDGE_RULE_SEEDS: tuple[KnowledgeRuleSeed, ...] = (
    KnowledgeRuleSeed(
        "INPUT-01",
        "Design is a required study input",
        "INPUT",
        "If Design is absent, the project is not ready for further medical logic.",
        action_definition={"emit": "knowledge_gap", "gap_code": "INPUT.DESIGN_MISSING"},
    ),
    KnowledgeRuleSeed(
        "REF-01",
        "Reference product selection requires Decision 85 §18 justification",
        "REFERENCE_SELECTION",
        "Reference product choice must be justified per Decision №85 p.18 and expert decision.",
        regulatory_hint="Decision 85 p.18",
        action_definition={"flow": ["candidates", "evidence", "regulatory_basis", "expert_decision"]},
    ),
    KnowledgeRuleSeed(
        "DESIGN-01",
        "Standard variability → 2×2 crossover proposal",
        "DESIGN",
        "When CVintra/90% CI exist for Cmax and AUC and variability is not indicated as high, propose CROSSOVER_2X2.",
        condition_expression="cv_and_ci_present AND NOT high_variability_indicated",
        action_definition={"propose_design": "CROSSOVER_2X2"},
    ),
    KnowledgeRuleSeed(
        "DESIGN-02",
        "High variability indicated → replicate proposal",
        "DESIGN",
        "When CVintra/90% CI exist and high intra-subject variability is indicated, propose REPLICATE_2X2X4.",
        condition_expression="cv_and_ci_present AND high_variability_indicated",
        action_definition={"propose_design": "REPLICATE_2X2X4"},
    ),
    KnowledgeRuleSeed(
        "DESIGN-03",
        "Expanded BE limits require separate expert decision",
        "DESIGN",
        "For high variability, expanded vs non-expanded BE limits must not be auto-selected.",
        action_definition={"emit": "knowledge_gap", "gap_code": "DESIGN.EXPANDED_BE_LIMITS"},
    ),
    KnowledgeRuleSeed(
        "DESIGN-04",
        "Missing CVintra/CI → adaptive proposal",
        "DESIGN",
        "When CVintra and 90% CI are absent, propose ADAPTIVE design.",
        condition_expression="NOT cv_and_ci_present",
        action_definition={"propose_design": "ADAPTIVE"},
    ),
    KnowledgeRuleSeed(
        "DESIGN-05",
        "Long half-life may suggest parallel — threshold unverified",
        "DESIGN",
        "Long half-life may support PARALLEL; numeric threshold not defined without verified source.",
        action_definition={"emit": "knowledge_gap", "gap_code": "DESIGN.LONG_HALF_LIFE_THRESHOLD"},
    ),
    KnowledgeRuleSeed(
        "DESIGN-06",
        "Final design via ExpertDecision",
        "DESIGN",
        "Final design must be fixed via ExpertDecision(APPROVED).",
        action_definition={"requires": "ExpertDecision.DESIGN"},
    ),
    KnowledgeRuleSeed(
        "FOOD-01",
        "Food determination per Decision 85 p.44",
        "FOOD",
        "Food condition determination references Decision 85 p.44.",
        regulatory_hint="Decision 85 p.44",
    ),
    KnowledgeRuleSeed(
        "FOOD-02",
        "Fed meal concept per Decision 85 p.46",
        "FOOD",
        "For Fed studies, standard high-calorie breakfast concept per Decision 85 p.46 — numeric kcal/fat/ml not auto-filled.",
        regulatory_hint="Decision 85 p.46",
        action_definition={"forbid_auto_constants": ["kcal", "fat_percent", "water_ml", "dose_after_meal_min"]},
    ),
    KnowledgeRuleSeed(
        "FOOD-03",
        "Alternative food conditions need FDA evidence + expert decision",
        "FOOD",
        "Non-standard food conditions require supporting evidence and ExpertDecision.",
    ),
    KnowledgeRuleSeed(
        "SAMPLE-01",
        "CVintra is a primary sample-size input",
        "SAMPLE_SIZE",
        "Intra-subject CV is a primary input to sample-size calculation.",
    ),
    KnowledgeRuleSeed(
        "SAMPLE-02",
        "CV from literature evidence",
        "SAMPLE_SIZE",
        "CV should be taken from literature EvidenceClaims with provenance.",
    ),
    KnowledgeRuleSeed(
        "SAMPLE-03",
        "Pooling of available CVs is a proposed workflow",
        "SAMPLE_SIZE",
        "Writer interview describes pooling multiple CV values — not auto-verified.",
    ),
    KnowledgeRuleSeed(
        "SAMPLE-04",
        "Standard 2×2 power/alpha proposed defaults",
        "SAMPLE_SIZE",
        "Proposed defaults for standard 2×2: power=80%, alpha=0.05 — pending statistical verification.",
        action_definition={"proposed_defaults": {"power": 0.8, "alpha": 0.05}},
    ),
    KnowledgeRuleSeed(
        "SAMPLE-05",
        "Adaptive may use Potvin B/C — not implemented",
        "SAMPLE_SIZE",
        "Adaptive designs may use Potvin B/C; numerical algorithms deferred until verified specification.",
        action_definition={"emit": "knowledge_gap", "gap_code": "SAMPLE.POTVIN_SPEC"},
    ),
    KnowledgeRuleSeed(
        "WASH-01",
        "Washout >= 5 × half-life (PROPOSED)",
        "WASHOUT",
        "Proposed washout minimum = 5 × half-life. Existing calculator uses same multiplier as PROPOSED DomainRule.",
        condition_expression="washout_min = half_life * 5",
        action_definition={"multiplier": 5.0, "aligns_with": "PK.WASHOUT.THALF_MULT.v1"},
    ),
    KnowledgeRuleSeed(
        "SAMPLING-01",
        "≥3 points before Tmax",
        "SAMPLING",
        "At least 3 sampling points before Tmax (PROPOSED regulatory adequacy).",
        action_definition={"kind": "adequacy", "min_before_tmax": 3},
    ),
    KnowledgeRuleSeed(
        "SAMPLING-02",
        "≥3 points after Tmax",
        "SAMPLING",
        "At least 3 sampling points after Tmax (PROPOSED).",
        action_definition={"kind": "adequacy", "min_after_tmax": 3},
    ),
    KnowledgeRuleSeed(
        "SAMPLING-03",
        "Cmax must not be the first concentration-time point",
        "SAMPLING",
        "First post-dose point should not be the only/Cmax-only first point (PROPOSED).",
        action_definition={"kind": "adequacy", "cmax_not_first": True},
    ),
    KnowledgeRuleSeed(
        "SAMPLING-04",
        "Adequate terminal-phase coverage",
        "SAMPLING",
        "Adequate terminal-phase coverage required (PROPOSED — qualitative).",
        action_definition={"kind": "adequacy", "terminal_coverage": True},
    ),
    KnowledgeRuleSeed(
        "SAMPLING-05",
        "3–4 terminal samples for elimination",
        "SAMPLING",
        "At least 3–4 terminal samples for reliable terminal elimination estimation (PROPOSED).",
        action_definition={"kind": "adequacy", "min_terminal_samples": 3},
    ),
    KnowledgeRuleSeed(
        "SAMPLING-06",
        "Last point >= 4 × half-life",
        "SAMPLING",
        "Last sampling point should be >= 4 × half-life when half-life known (PROPOSED).",
        action_definition={"kind": "adequacy", "last_ge_half_life_mult": 4.0},
    ),
    KnowledgeRuleSeed(
        "SAMPLING-07",
        "AUC0-t covers ≥80% of AUC0-inf",
        "SAMPLING",
        "AUC0-t should cover at least 80% of AUC0-inf (PROPOSED).",
        action_definition={"kind": "adequacy", "auc_coverage_min": 0.8},
    ),
    KnowledgeRuleSeed(
        "SAMPLING-08",
        "Long half-life truncation to 72h (conditional PROPOSED)",
        "SAMPLING",
        "For long half-life, truncation to 72h may apply when absorption ≤72h — requires confirmed definition of long half-life.",
        action_definition={"emit": "knowledge_gap", "gap_code": "SAMPLING.LONG_HL_72H"},
    ),
    KnowledgeRuleSeed(
        "SAMPLING-HEUR-01",
        "Tmax capture density heuristic (NOT regulatory PASS)",
        "SAMPLING",
        "Point-generation heuristic around Tmax (legacy ±25% window). HEURISTIC/PROPOSED — must not alone grant validation PASS.",
        action_definition={"kind": "heuristic", "code": "TMAX_CAPTURE_WINDOW", "aligns_with": "PK.SAMP.DENSITY.v1"},
        notes="Separated from regulatory adequacy rules.",
    ),
    KnowledgeRuleSeed(
        "ANALYTE-01",
        "Parent/metabolite selection per Rules §III.6 p.50",
        "ANALYTE",
        "Parent/metabolite/both per п.50 подраздела 6 раздела III Правил — PROPOSED pending verification.",
        regulatory_hint="Rules section III subsection 6 p.50",
    ),
    KnowledgeRuleSeed(
        "CRIT-01",
        "Most inclusion/exclusion criteria are standard",
        "ELIGIBILITY",
        "Majority of inclusion/exclusion criteria are standard templates (PROPOSED).",
    ),
    KnowledgeRuleSeed(
        "CRIT-02",
        "Concomitant meds may depend on SmPC",
        "ELIGIBILITY",
        "Concomitant medication restrictions can depend on SmPC evidence.",
    ),
    KnowledgeRuleSeed(
        "CRIT-03",
        "CYP inhibitors/inducers may create drug-specific restrictions",
        "ELIGIBILITY",
        "Do not hardcode CYP lists — require SmPC-derived evidence.",
    ),
    KnowledgeRuleSeed(
        "CRIT-04",
        "SmPC contraindications may alter criteria",
        "ELIGIBILITY",
        "Contraindications from SmPC may alter eligibility criteria.",
    ),
    KnowledgeRuleSeed(
        "CRIT-05",
        "Vomiting rule: 2 × Tmax of analyte (PROPOSED)",
        "ELIGIBILITY",
        "Proposed vomiting window = 2 × Tmax of analyte — not auto-applied as final.",
        action_definition={"expression": "vomit_window = 2 * tmax"},
    ),
    KnowledgeRuleSeed(
        "CRIT-06",
        "Smoking restrictions may depend on metabolic enzymes",
        "ELIGIBILITY",
        "Smoking restrictions can depend on metabolic enzymes — require evidence.",
    ),
    KnowledgeRuleSeed(
        "CRIT-07",
        "Contraception period from SmPC",
        "ELIGIBILITY",
        "Contraception period comes from SmPC — do not invent days.",
    ),
    KnowledgeRuleSeed(
        "SAFETY-01",
        "Standard BE safety set exists conceptually",
        "SAFETY",
        "A standard BE safety assessment set exists conceptually — checklist not formalized.",
        action_definition={"emit": "knowledge_gap", "gap_code": "SAFETY.REF_PROTOCOL_POST_2026_06"},
    ),
    KnowledgeRuleSeed(
        "SOURCE-01",
        "Source classes ordering is conceptual only",
        "SOURCE",
        "EEC / FDA / EMA / reports / articles — not a verified conflict-ranking algorithm.",
        action_definition={"emit": "knowledge_gap", "gap_code": "SOURCE.CONFLICT_RESOLUTION"},
    ),
)


FOUNDATION_KNOWLEDGE_GAPS: tuple[dict[str, Any], ...] = (
    {
        "domain": "SAMPLE_SIZE",
        "question": "Potvin B/C sample-size implementation specification not yet verified.",
        "importance": "HIGH",
        "blocking": False,
        "related_rule_id": "SAMPLE-05",
    },
    {
        "domain": "SAMPLE_SIZE",
        "question": "Final randomized N decision logic not yet specified.",
        "importance": "CRITICAL",
        "blocking": True,
        "related_decision_type": "SAMPLE_SIZE",
    },
    {
        "domain": "DESIGN",
        "question": "Verified numeric definition of long half-life for parallel design is missing.",
        "importance": "HIGH",
        "blocking": False,
        "related_rule_id": "DESIGN-05",
    },
    {
        "domain": "DESIGN",
        "question": "Expanded BE limits vs standard limits for high-variability products require expert decision.",
        "importance": "HIGH",
        "blocking": True,
        "related_rule_id": "DESIGN-03",
        "related_decision_type": "STATISTICS",
    },
    {
        "domain": "PK",
        "question": "Specific PK exceptions are not yet fully specified by expert.",
        "importance": "MEDIUM",
        "blocking": False,
        "related_decision_type": "PK_PARAMETER_SET",
    },
    {
        "domain": "SAFETY",
        "question": "Reference safety protocol after June 2026 has not yet been formalized.",
        "importance": "MEDIUM",
        "blocking": False,
        "related_rule_id": "SAFETY-01",
    },
    {
        "domain": "SOURCE",
        "question": "Formal source conflict resolution algorithm needs expert confirmation.",
        "importance": "HIGH",
        "blocking": False,
        "related_rule_id": "SOURCE-01",
    },
    {
        "domain": "SAMPLING",
        "question": "Long half-life truncation-to-72h applicability criteria not verified.",
        "importance": "MEDIUM",
        "blocking": False,
        "related_rule_id": "SAMPLING-08",
    },
    {
        "domain": "QA",
        "question": (
            "ExpertRule (Phase 12A empty catalog) vs KnowledgeRule (Phase 12A.1) coexistence "
            "needs formal deprecation plan. ExpertRule not deleted for compatibility."
        ),
        "importance": "MEDIUM",
        "blocking": False,
    },
    {
        "domain": "QA",
        "question": (
            "Explicit decision-to-canonical application boundary needs formalization "
            "before production workflow (approve ≠ apply)."
        ),
        "importance": "HIGH",
        "blocking": False,
        "related_decision_type": "OTHER",
    },
)


def list_seed_rules() -> list[dict[str, Any]]:
    return [
        {
            "rule_code": r.rule_code,
            "name": r.name,
            "domain": r.domain,
            "description": r.description,
            "condition_expression": r.condition_expression,
            "action_definition": dict(r.action_definition),
            "priority": r.priority,
            "status": r.status,
            "requires_expert_confirmation": r.requires_expert_confirmation,
            "regulatory_hint": r.regulatory_hint,
            "notes": r.notes,
        }
        for r in KNOWLEDGE_RULE_SEEDS
    ]
