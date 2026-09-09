"""PK semantic model + analyte / standard PK profile — Phase 12A.1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.knowledge_constants import AUC_METRIC_TYPES, PK_PROFILE_KINDS


# Compatibility aliases: legacy string codes → semantic type
AUC_COMPAT_ALIASES: dict[str, str] = {
    "AUC0-t": "AUC_0_LAST",
    "AUC0_t": "AUC_0_LAST",
    "AUC0-last": "AUC_0_LAST",
    "AUC0_last": "AUC_0_LAST",
    "AUC0-x": "AUC_0_LAST",
    "AUC0_x": "AUC_0_LAST",
    "AUC0-72": "AUC_0_72H",
    "AUC0_72": "AUC_0_72H",
    "AUC0-72h": "AUC_0_72H",
    "AUC0-inf": "AUC_0_INF",
    "AUC0_inf": "AUC_0_INF",
    "AUCinf": "AUC_0_INF",
    "AUC0-t/AUC0-inf": "AUC_0_LAST_OVER_INF",
    "AUC0-72/AUC0-inf": "AUC_0_72H_OVER_INF",
}


@dataclass(frozen=True)
class PKParameterDefinition:
    code: str
    display_name: str
    type: str  # PRIMARY | SECONDARY | OTHER
    start_time: str | None = None
    end_time_rule: str | None = None
    analyte_scope: str = "PARENT"
    primary_or_secondary: str = "SECONDARY"
    source: str = "STANDARD_PROPOSED"
    status: str = "PROPOSED"
    auc_metric_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


STANDARD_PK_PARAMETERS: tuple[PKParameterDefinition, ...] = (
    PKParameterDefinition("Cmax", "Cmax", "PRIMARY", primary_or_secondary="PRIMARY"),
    PKParameterDefinition(
        "AUC_0_LAST",
        "AUC0-x",
        "PRIMARY",
        end_time_rule="LAST_MEASURABLE",
        primary_or_secondary="PRIMARY",
        auc_metric_type="AUC_0_LAST",
    ),
    PKParameterDefinition(
        "AUC_0_72H",
        "AUC0-72",
        "SECONDARY",
        end_time_rule="FIXED_72H",
        auc_metric_type="AUC_0_72H",
    ),
    PKParameterDefinition(
        "AUC_0_INF",
        "AUC0-inf",
        "SECONDARY",
        end_time_rule="INFINITY",
        auc_metric_type="AUC_0_INF",
    ),
    PKParameterDefinition(
        "AUC_0_LAST_OVER_INF",
        "AUC0-x/AUC0-inf",
        "SECONDARY",
        auc_metric_type="AUC_0_LAST_OVER_INF",
    ),
    PKParameterDefinition("Kel", "Kel", "SECONDARY"),
    PKParameterDefinition("T1_2", "t½", "SECONDARY"),
    PKParameterDefinition("Tmax", "Tmax", "SECONDARY"),
)


@dataclass
class PKParameterProfile:
    kind: str = "STANDARD_PROPOSED"
    parameters: list[PKParameterDefinition] = field(default_factory=list)
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "parameters": [p.to_dict() for p in self.parameters],
            "status": self.status,
            "requires_expert_confirmation": self.requires_expert_confirmation,
            "knowledge_gaps": self.knowledge_gaps,
        }


def resolve_auc_metric_type(raw: str | None) -> str | None:
    if not raw:
        return None
    if raw in AUC_METRIC_TYPES:
        return raw
    return AUC_COMPAT_ALIASES.get(raw) or AUC_COMPAT_ALIASES.get(raw.replace(" ", ""))


def display_auc_metric(metric_type: str | None, *, approved_label: str | None = None) -> str:
    if approved_label:
        return approved_label
    from app.domain.display_value_registry import resolve_display

    if not metric_type:
        return "{{PK.AUC_METRIC}}"
    return resolve_display(metric_type, context="auc", fallback=metric_type)


def standard_pk_profile() -> PKParameterProfile:
    return PKParameterProfile(
        kind="STANDARD_PROPOSED",
        parameters=list(STANDARD_PK_PARAMETERS),
        knowledge_gaps=[
            {
                "domain": "PK",
                "question": "Specific PK exceptions are not yet fully specified by expert.",
                "importance": "MEDIUM",
                "blocking": False,
                "related_decision_type": "PK_PARAMETER_SET",
            }
        ],
    )


@dataclass
class AnalyteSelectionProposal:
    proposed_scope: str | None  # PARENT | METABOLITE | BOTH | None
    reasons: list[str] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)
    evidence_claim_ids: list[str] = field(default_factory=list)
    regulatory_basis: list[str] = field(default_factory=list)
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def propose_analyte_selection(
    *,
    parent_present: bool = True,
    metabolites: list[str] | None = None,
    pharmacological_relevance: str | None = None,
    evidence_claim_ids: list[str] | None = None,
    regulatory_basis_ids: list[str] | None = None,
) -> AnalyteSelectionProposal:
    metabolites = metabolites or []
    gaps = []
    scope = None
    reasons = ["ANALYTE-01: parent/metabolite/both per Rules §III.6 p.50 — PROPOSED."]
    if parent_present and not metabolites:
        scope = "PARENT"
        reasons.append("Only parent indicated in inputs — tentative PARENT scope.")
    elif parent_present and metabolites:
        scope = None
        reasons.append("Metabolites listed — selection requires expert decision (no auto BOTH/METABOLITE).")
        gaps.append(
            {
                "domain": "ANALYTE",
                "question": "Parent vs metabolite vs both not decided for listed metabolites.",
                "importance": "HIGH",
                "blocking": True,
                "related_rule_id": "ANALYTE-01",
            }
        )
    else:
        gaps.append(
            {
                "domain": "ANALYTE",
                "question": "Analyte selection inputs incomplete.",
                "importance": "HIGH",
                "blocking": True,
            }
        )
    return AnalyteSelectionProposal(
        proposed_scope=scope,
        reasons=reasons,
        triggered_rules=["ANALYTE-01"],
        evidence_claim_ids=list(evidence_claim_ids or []),
        regulatory_basis=list(regulatory_basis_ids or []),
        knowledge_gaps=gaps,
    )


# silence unused import warning for kinds constant used by docs/tests
_ = PK_PROFILE_KINDS
