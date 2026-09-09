"""Decision dependency registry & blocker evaluation — Phase 15.1.

Extends existing validation_graph concepts. Single source of decision↔field deps.
No global blocking. Graph is the source of truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.decision_context import DecisionContext
from app.domain.validation_graph import change_impact as validation_change_impact


# Field / gap codes that may block a decision when OPEN / MISSING
DECISION_DEPENDENCY_REGISTRY: dict[str, dict[str, Any]] = {
    "DESIGN": {
        "blocking_conflict_fields": (
            "reference_product.dose",
            "reference_product.name",
        ),
        "blocking_gap_codes": (),  # CVintra missing → non-blocking issue
        "non_blocking_gap_codes": ("MISSING_CVINTRA",),
        "context_fields": (
            "design.periods",
            "design.sequences",
            "design.groups",
            "design.crossover",
            "subjects.randomized_n",
        ),
        "related_nodes": ("design", "reference_product"),
    },
    "FOOD": {
        "blocking_conflict_fields": (),  # reference dose does NOT block FOOD
        "blocking_gap_codes": (),
        "non_blocking_gap_codes": ("MISSING_MEAL_COMPOSITION",),
        "context_fields": (
            "design.conditions",
            "food.condition",
            "treatment.fasting",
            "treatment.fed",
        ),
        "related_nodes": ("food",),
    },
    "WASHOUT": {
        "blocking_conflict_fields": (),  # reference dose does NOT block WASHOUT
        "blocking_gap_codes": ("MISSING_HALF_LIFE_FOR_WASHOUT",),
        "non_blocking_gap_codes": (),
        "context_fields": ("washout.duration", "washout.unit", "pk.t_half"),
        "related_nodes": ("washout", "pk"),
    },
    "SAMPLING": {
        "blocking_conflict_fields": (),  # reference dose does NOT block SAMPLING
        # Expected (planning) Tmax / t½ — soft local engine gates, not whole-protocol freeze
        "blocking_gap_codes": (
            "MISSING_TMAX_FOR_SAMPLING",  # = missing verified expected Tmax
            "MISSING_HALF_LIFE_FOR_WASHOUT",  # expected t½ also used for terminal phase
        ),
        "non_blocking_gap_codes": (),
        "context_fields": (
            "sampling.times",
            "sampling.total_points",
            "pk.expected_tmax",
            "pk.Tmax",
            "pk.expected_t_half",
            "pk.t_half",
        ),
        "related_nodes": ("sampling", "pk"),
    },
    "ANALYTE_PK": {
        # Dose conflict alone does not block if analyte identity is resolvable;
        # name conflict does (identity ambiguity).
        "blocking_conflict_fields": ("reference_product.name",),
        "blocking_gap_codes": ("MISSING_ANALYTE",),
        "non_blocking_gap_codes": (),
        "non_blocking_conflict_fields": ("reference_product.dose",),
        "context_fields": (
            "bioanalysis.analyte",
            "test_product.active_substance",
            "reference_product.active_substance",
        ),
        "related_nodes": ("analytes", "pk", "reference_product"),
    },
    "STATISTICS": {
        "blocking_conflict_fields": (),
        "blocking_gap_codes": (
            "MISSING_PRIMARY_PK_PARAMETER",
            "MISSING_ACCEPTANCE_INTERVAL",
            "MISSING_CONFIDENCE_LEVEL",
            "MISSING_STATISTICAL_MODEL",
            "MISSING_ANALYSIS_POPULATION_RULE",
        ),
        "non_blocking_gap_codes": (),
        "context_fields": (
            "design.type",
            "design.periods",
            "design.sequences",
            "pk.parameters",
            "pk.primary_parameters",
            "pk.AUC_endpoint",
            "statistics.method",
            "statistics.transformation",
            "statistics.confidence_interval",
            "statistics.acceptance_interval",
        ),
        "related_nodes": ("statistics", "design", "pk"),
    },
}

# Field path → domains that must recompute when field changes
FIELD_TO_DECISION_DOMAINS: dict[str, tuple[str, ...]] = {
    "reference_product.dose": ("DESIGN",),
    "reference_product.name": ("DESIGN", "ANALYTE_PK"),
    "reference_product": ("DESIGN", "ANALYTE_PK"),
    "t_half": ("WASHOUT", "SAMPLING"),
    "pk.t_half": ("WASHOUT", "SAMPLING"),
    "half_life": ("WASHOUT", "SAMPLING"),
    "tmax": ("SAMPLING",),
    "pk.Tmax": ("SAMPLING",),
    "pk.expected_tmax": ("SAMPLING",),
    "Tmax": ("SAMPLING",),
    "pk.expected_t_half": ("WASHOUT", "SAMPLING"),
    "cv_intra": ("DESIGN",),
    "CVintra": ("DESIGN",),
    "food_condition": ("FOOD",),
    "food.condition": ("FOOD",),
    "design.conditions": ("FOOD", "DESIGN"),
    "analyte": ("ANALYTE_PK",),
    "bioanalysis.analyte": ("ANALYTE_PK",),
    "sampling.times": ("SAMPLING",),
    "washout.duration": ("WASHOUT",),
    "design.type": ("DESIGN", "STATISTICS"),
    "design": ("DESIGN", "FOOD", "STATISTICS"),
    "design.periods": ("DESIGN", "STATISTICS"),
    "design.sequences": ("DESIGN", "STATISTICS"),
    "pk.parameters": ("STATISTICS",),
    "pk.primary_parameters": ("STATISTICS",),
    "pk.AUC_endpoint": ("STATISTICS",),
    "pk.Cmax": ("STATISTICS",),
    "Cmax": ("STATISTICS",),
    "AUC0-72": ("STATISTICS",),
    "AUC0-inf": ("STATISTICS",),
    "statistics.method": ("STATISTICS",),
    "statistics.transformation": ("STATISTICS",),
    "statistics.confidence_interval": ("STATISTICS",),
    "statistics.acceptance_interval": ("STATISTICS",),
    "evidence_version": ("STATISTICS",),
}


APPLICABILITY_VALUES = ("DIRECT", "HIGH", "MODERATE", "LOW", "UNKNOWN", "NOT_APPLICABLE")
DECISION_INPUT_SOURCE_TYPES = (
    "CURRENT_STUDY_FACT",
    "EVIDENCE",
    "RULE",
    "EXPERT_DECISION",
    "SYSTEM_RECOMMENDATION",
)
BLOCKER_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


@dataclass
class BlockingReason:
    blocking_reason_code: str
    field_path: str | None = None
    severity: str = "HIGH"
    kind: str = "CONFLICT"  # CONFLICT|GAP|MISSING_FIELD|EVIDENCE|KNOWLEDGE_GAP
    reference_id: str | None = None  # conflict_id / gap code / evidence id
    message: str = ""
    # Soft gate: blocks this engine only — does not mean the whole protocol is frozen
    soft_gate: bool = False
    scope: str = "ENGINE"  # ENGINE | PROTOCOL
    next_action: str | None = None  # e.g. FIND_EXPECTED_TMAX

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionBlockerReport:
    domain: str
    blocked: bool
    blocking_reasons: list[BlockingReason] = field(default_factory=list)
    non_blocking_issues: list[BlockingReason] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "blocked": self.blocked,
            "blocking_reasons": [b.to_dict() for b in self.blocking_reasons],
            "non_blocking_issues": [b.to_dict() for b in self.non_blocking_issues],
        }


def registry_for(domain: str) -> dict[str, Any]:
    if domain not in DECISION_DEPENDENCY_REGISTRY:
        raise KeyError(f"Unknown decision domain: {domain}")
    return DECISION_DEPENDENCY_REGISTRY[domain]


def dependencies_for_domain(domain: str) -> dict[str, Any]:
    reg = registry_for(domain)
    return {
        "domain": domain,
        "blocking_conflict_fields": list(reg.get("blocking_conflict_fields") or ()),
        "blocking_gap_codes": list(reg.get("blocking_gap_codes") or ()),
        "non_blocking_gap_codes": list(reg.get("non_blocking_gap_codes") or ()),
        "non_blocking_conflict_fields": list(reg.get("non_blocking_conflict_fields") or ()),
        "context_fields": list(reg.get("context_fields") or ()),
        "related_nodes": list(reg.get("related_nodes") or ()),
    }


def domains_affected_by_field(field_path: str) -> list[str]:
    """Return decision domains that must recompute when field_path changes."""
    affected: set[str] = set()
    if field_path in FIELD_TO_DECISION_DOMAINS:
        affected.update(FIELD_TO_DECISION_DOMAINS[field_path])
    # prefix / family
    for key, domains in FIELD_TO_DECISION_DOMAINS.items():
        if field_path.startswith(key) or key.startswith(field_path.split(".")[0]):
            if field_path.split(".")[0] == key.split(".")[0] or field_path == key:
                affected.update(domains)
    # Also consult validation graph node aliases for related domains
    node = field_path.split(".")[0]
    impact = validation_change_impact(node)
    node_map = {
        "design": "DESIGN",
        "food": "FOOD",
        "washout": "WASHOUT",
        "sampling": "SAMPLING",
        "pk": None,  # pk alone is ambiguous — use FIELD_TO_DECISION_DOMAINS
        "analytes": "ANALYTE_PK",
        "reference_product": None,
    }
    for n in [impact.get("normalized_node"), *(impact.get("revalidate") or [])]:
        mapped = node_map.get(str(n))
        if mapped:
            affected.add(mapped)
    # Explicit: reference_product.dose only DESIGN (not all domains)
    if field_path == "reference_product.dose":
        return ["DESIGN"]
    if field_path in {"t_half", "pk.t_half", "pk.expected_t_half", "half_life"}:
        return ["WASHOUT", "SAMPLING"]
    if field_path in {"tmax", "pk.Tmax", "pk.expected_tmax", "Tmax"}:
        return ["SAMPLING"]
    return sorted(affected) if affected else sorted(
        FIELD_TO_DECISION_DOMAINS.get(field_path, ())
    )


def is_decision_blocked(domain: str, ctx: DecisionContext) -> DecisionBlockerReport:
    """Inspect only registered dependencies of this decision domain."""
    reg = registry_for(domain)
    blocking: list[BlockingReason] = []
    non_blocking: list[BlockingReason] = []

    open_conflicts = [
        c for c in ctx.open_conflicts if str(c.get("status") or "OPEN") == "OPEN"
    ]
    open_by_field = {str(c.get("field_path")): c for c in open_conflicts}

    for fp in reg.get("blocking_conflict_fields") or ():
        if fp in open_by_field:
            c = open_by_field[fp]
            blocking.append(
                BlockingReason(
                    blocking_reason_code=f"CONFLICT_{fp.replace('.', '_').upper()}",
                    field_path=fp,
                    severity="CRITICAL",
                    kind="CONFLICT",
                    reference_id=str(c.get("conflict_id") or fp),
                    message=f"Open conflict on {fp}",
                )
            )

    for fp in reg.get("non_blocking_conflict_fields") or ():
        if fp in open_by_field and fp not in (reg.get("blocking_conflict_fields") or ()):
            c = open_by_field[fp]
            non_blocking.append(
                BlockingReason(
                    blocking_reason_code=f"UNRELATED_CONFLICT_{fp.replace('.', '_').upper()}",
                    field_path=fp,
                    severity="MEDIUM",
                    kind="CONFLICT",
                    reference_id=str(c.get("conflict_id") or fp),
                    message=f"Open conflict on {fp} is unrelated to this decision",
                )
            )

    # Also surface open critical conflicts that are NOT in this domain's deps as non-blocking
    for fp, c in open_by_field.items():
        in_blocking = fp in (reg.get("blocking_conflict_fields") or ())
        in_non = fp in (reg.get("non_blocking_conflict_fields") or ())
        if not in_blocking and not in_non:
            # Unrelated to this decision
            non_blocking.append(
                BlockingReason(
                    blocking_reason_code=f"UNRELATED_CONFLICT_{fp.replace('.', '_').upper()}",
                    field_path=fp,
                    severity="LOW",
                    kind="CONFLICT",
                    reference_id=str(c.get("conflict_id") or fp),
                    message=f"Unrelated open conflict on {fp}",
                )
            )

    gap_codes_present = {str(g.get("code")) for g in ctx.knowledge_gaps}
    # Domain-specific gaps also come from engines; allow caller to pass via ctx
    for code in reg.get("blocking_gap_codes") or ():
        # Evaluate presence: either in ctx.knowledge_gaps OR computable missing state
        present = code in gap_codes_present or _gap_condition(domain, code, ctx)
        if present:
            soft = code in {
                "MISSING_TMAX_FOR_SAMPLING",
                "MISSING_HALF_LIFE_FOR_WASHOUT",
            }
            msg = {
                "MISSING_TMAX_FOR_SAMPLING": (
                    "Sampling design requires verified expected (planning) Tmax from SmPC/literature — "
                    "not an observed post-study Tmax. Other protocol steps may continue."
                ),
                "MISSING_HALF_LIFE_FOR_WASHOUT": (
                    "Washout/sampling terminal phase requires verified expected t½. "
                    "Other protocol steps may continue."
                ),
            }.get(code, f"Missing required input: {code}")
            next_action = {
                "MISSING_TMAX_FOR_SAMPLING": "FIND_EXPECTED_TMAX",
                "MISSING_HALF_LIFE_FOR_WASHOUT": "FIND_EXPECTED_HALF_LIFE",
            }.get(code)
            blocking.append(
                BlockingReason(
                    blocking_reason_code=code,
                    field_path=_gap_field(code),
                    severity="HIGH",
                    kind="KNOWLEDGE_GAP",
                    reference_id=code,
                    message=msg,
                    soft_gate=soft,
                    scope="ENGINE" if soft else "PROTOCOL",
                    next_action=next_action,
                )
            )

    for code in reg.get("non_blocking_gap_codes") or ():
        present = code in gap_codes_present or _gap_condition(domain, code, ctx)
        if present and code not in {b.blocking_reason_code for b in blocking}:
            non_blocking.append(
                BlockingReason(
                    blocking_reason_code=code,
                    field_path=_gap_field(code),
                    severity="MEDIUM",
                    kind="GAP",
                    reference_id=code,
                    message=f"Non-blocking gap: {code}",
                )
            )

    return DecisionBlockerReport(
        domain=domain,
        blocked=bool(blocking),
        blocking_reasons=blocking,
        non_blocking_issues=non_blocking,
    )


def _gap_field(code: str) -> str | None:
    return {
        "MISSING_HALF_LIFE_FOR_WASHOUT": "pk.expected_t_half",
        "MISSING_TMAX_FOR_SAMPLING": "pk.expected_tmax",
        "MISSING_CVINTRA": "cv_intra",
        "MISSING_MEAL_COMPOSITION": "food.calorie_target",
        "MISSING_ANALYTE": "bioanalysis.analyte",
    }.get(code)


def _gap_condition(domain: str, code: str, ctx: DecisionContext) -> bool:
    from app.domain.expected_pk import (
        resolve_verified_expected_half_life,
        resolve_verified_expected_tmax,
    )

    if code == "MISSING_HALF_LIFE_FOR_WASHOUT":
        if ctx.half_life is not None:
            return False
        return (
            resolve_verified_expected_half_life(ctx.structured_facts, ctx.fact_statuses) is None
        )
    if code == "MISSING_TMAX_FOR_SAMPLING":
        if ctx.tmax is not None:
            return False
        return resolve_verified_expected_tmax(ctx.structured_facts, ctx.fact_statuses) is None
    if code == "MISSING_CVINTRA":
        return ctx.cvintra is None
    if code == "MISSING_MEAL_COMPOSITION":
        f = ctx.structured_facts
        return not (f.get("food.calorie_target") or f.get("food.fat_target"))
    if code == "MISSING_ANALYTE":
        f = ctx.structured_facts
        return not (f.get("bioanalysis.analyte") or f.get("test_product.active_substance"))
    return False
