"""Phase 28 — Serialize / deserialize Writer engine stores for workspace bags."""

from __future__ import annotations

from typing import Any

from app.domain.decision_context import DecisionContext
from app.domain.decision_models import (
    AnalogueStudyEvidence,
    DecisionEvidence,
    DecisionRecommendation,
    ProtocolDecision,
)
from app.domain.research_evidence_models import (
    EvidenceConflictRecord,
    RegisteredSource,
    ResearchClaim,
    ResearchQuery,
    ResearchTask,
    SourceResult,
)
from app.domain.sample_size_models import (
    ProvenancedInput,
    SampleSizeCalculationRecord,
    SampleSizeDiscrepancy,
    SampleSizeExpertReview,
    SampleSizeRecommendation,
    SampleSizeScenario,
)
from app.domain.statistics_models import (
    AcceptanceIntervalSpec,
    ProvenancedChoice,
    StatisticalParameterPlan,
    StatisticsExpertReview,
    StatisticsPlan,
    StatisticsScenario,
)


def decision_evidence_from_dict(data: dict[str, Any]) -> DecisionEvidence:
    return DecisionEvidence(**{k: v for k, v in data.items() if k in DecisionEvidence.__dataclass_fields__})


def recommendation_from_dict(data: dict[str, Any] | None) -> DecisionRecommendation | None:
    if not data:
        return None
    clean = {k: v for k, v in data.items() if k in DecisionRecommendation.__dataclass_fields__}
    clean.pop("option_label", None)
    clean.pop("status_is_not_approved", None)
    return DecisionRecommendation(**clean)


def protocol_decision_from_dict(data: dict[str, Any]) -> ProtocolDecision:
    fields = set(ProtocolDecision.__dataclass_fields__)
    kwargs = {k: v for k, v in data.items() if k in fields}
    kwargs.pop("domain_label", None)
    kwargs.pop("selected_option_label", None)
    kwargs.pop("options", None)
    kwargs.pop("display", None)
    rec = kwargs.pop("recommendation", None)
    hist = kwargs.pop("recommendation_history", []) or []
    evidence = kwargs.pop("evidence", []) or []
    kwargs["recommendation"] = recommendation_from_dict(rec)
    kwargs["recommendation_history"] = [recommendation_from_dict(h) for h in hist if h]
    kwargs["evidence"] = [decision_evidence_from_dict(e) for e in evidence if isinstance(e, dict)]
    return ProtocolDecision(**kwargs)


def analogue_from_dict(data: dict[str, Any]) -> AnalogueStudyEvidence:
    clean = {k: v for k, v in data.items() if k in AnalogueStudyEvidence.__dataclass_fields__}
    clean.pop("identical_to_current", None)
    return AnalogueStudyEvidence(**clean)


def context_from_dict(data: dict[str, Any]) -> DecisionContext:
    fields = set(DecisionContext.__dataclass_fields__)
    kwargs = {k: v for k, v in data.items() if k in fields}
    analogues = kwargs.pop("analogue_studies", []) or []
    kwargs["analogue_studies"] = [analogue_from_dict(a) for a in analogues if isinstance(a, dict)]
    return DecisionContext(**kwargs)


def sample_size_from_dict(data: dict[str, Any]) -> SampleSizeCalculationRecord:
    fields = set(SampleSizeCalculationRecord.__dataclass_fields__)
    kwargs = {k: v for k, v in data.items() if k in fields}
    kwargs.pop("is_not_approved_protocol_value", None)
    inputs = kwargs.pop("inputs", []) or []
    scenarios = kwargs.pop("scenarios", []) or []
    reviews = kwargs.pop("reviews", []) or []
    rec = kwargs.pop("recommendation", None)
    disc = kwargs.pop("discrepancy", None)
    kwargs["inputs"] = [
        ProvenancedInput(**{k: v for k, v in i.items() if k in ProvenancedInput.__dataclass_fields__})
        for i in inputs
        if isinstance(i, dict)
    ]
    kwargs["scenarios"] = [
        SampleSizeScenario(**{k: v for k, v in s.items() if k in SampleSizeScenario.__dataclass_fields__})
        for s in scenarios
        if isinstance(s, dict)
    ]
    kwargs["reviews"] = [
        SampleSizeExpertReview(
            **{k: v for k, v in r.items() if k in SampleSizeExpertReview.__dataclass_fields__}
        )
        for r in reviews
        if isinstance(r, dict)
    ]
    if rec:
        kwargs["recommendation"] = SampleSizeRecommendation(
            **{
                k: v
                for k, v in rec.items()
                if k in SampleSizeRecommendation.__dataclass_fields__
            }
        )
    if disc:
        kwargs["discrepancy"] = SampleSizeDiscrepancy(
            **{k: v for k, v in disc.items() if k in SampleSizeDiscrepancy.__dataclass_fields__}
        )
    return SampleSizeCalculationRecord(**kwargs)


def _acceptance_from_dict(data: dict[str, Any] | None) -> AcceptanceIntervalSpec | None:
    if not data:
        return None
    return AcceptanceIntervalSpec(
        **{k: v for k, v in data.items() if k in AcceptanceIntervalSpec.__dataclass_fields__}
    )


def statistics_plan_from_dict(data: dict[str, Any]) -> StatisticsPlan:
    fields = set(StatisticsPlan.__dataclass_fields__)
    kwargs = {k: v for k, v in data.items() if k in fields}
    kwargs.pop("fabricated_gmr", None)
    kwargs.pop("fabricated_ci", None)
    kwargs.pop("is_recommendation_not_approval", None)
    params = kwargs.pop("parameters", []) or []
    scenarios = kwargs.pop("scenarios", []) or []
    choices = kwargs.pop("choices", []) or []
    reviews = kwargs.pop("reviews", []) or []
    acc = kwargs.pop("acceptance_interval", None)
    rebuilt_params: list[StatisticalParameterPlan] = []
    for p in params:
        if not isinstance(p, dict):
            continue
        pf = {k: v for k, v in p.items() if k in StatisticalParameterPlan.__dataclass_fields__}
        pf.pop("fabricated_results", None)
        pai = pf.pop("acceptance_interval", None)
        pf["acceptance_interval"] = _acceptance_from_dict(pai if isinstance(pai, dict) else None)
        rebuilt_params.append(StatisticalParameterPlan(**pf))
    kwargs["parameters"] = rebuilt_params
    kwargs["scenarios"] = [
        StatisticsScenario(**{k: v for k, v in s.items() if k in StatisticsScenario.__dataclass_fields__})
        for s in scenarios
        if isinstance(s, dict)
    ]
    kwargs["choices"] = [
        ProvenancedChoice(**{k: v for k, v in c.items() if k in ProvenancedChoice.__dataclass_fields__})
        for c in choices
        if isinstance(c, dict)
    ]
    kwargs["reviews"] = [
        StatisticsExpertReview(
            **{k: v for k, v in r.items() if k in StatisticsExpertReview.__dataclass_fields__}
        )
        for r in reviews
        if isinstance(r, dict)
    ]
    kwargs["acceptance_interval"] = _acceptance_from_dict(acc if isinstance(acc, dict) else None)
    return StatisticsPlan(**kwargs)


def research_task_from_dict(data: dict[str, Any]) -> ResearchTask:
    return ResearchTask(**{k: v for k, v in data.items() if k in ResearchTask.__dataclass_fields__})


def research_query_from_dict(data: dict[str, Any]) -> ResearchQuery:
    return ResearchQuery(**{k: v for k, v in data.items() if k in ResearchQuery.__dataclass_fields__})


def source_result_from_dict(data: dict[str, Any]) -> SourceResult:
    return SourceResult(**{k: v for k, v in data.items() if k in SourceResult.__dataclass_fields__})


def research_claim_from_dict(data: dict[str, Any]) -> ResearchClaim:
    return ResearchClaim(**{k: v for k, v in data.items() if k in ResearchClaim.__dataclass_fields__})


def research_conflict_from_dict(data: dict[str, Any]) -> EvidenceConflictRecord:
    return EvidenceConflictRecord(
        **{k: v for k, v in data.items() if k in EvidenceConflictRecord.__dataclass_fields__}
    )


def registered_source_from_dict(data: dict[str, Any]) -> RegisteredSource:
    return RegisteredSource(
        **{k: v for k, v in data.items() if k in RegisteredSource.__dataclass_fields__}
    )


def collect_research_payload(study_id: str) -> dict[str, Any]:
    from app.domain.research_evidence_store import (
        list_claims,
        list_conflicts,
        list_queries,
        list_results,
        list_sources,
        list_tasks,
    )

    tasks = list_tasks(study_id)
    task_ids = {t.id for t in tasks}
    queries = [q for t in tasks for q in list_queries(t.id)]
    results = [r for t in tasks for r in list_results(t.id)]
    claims = list_claims(study_id=study_id)
    conflicts = list_conflicts(study_id=study_id)
    sources = list_sources(study_id=study_id)
    return {
        "tasks": [t.to_dict() for t in tasks],
        "queries": [q.to_dict() for q in queries],
        "results": [r.to_dict() for r in results],
        "claims": [c.to_dict() for c in claims],
        "conflicts": [c.to_dict() for c in conflicts],
        "sources": [s.to_dict() for s in sources],
        "task_ids": sorted(task_ids),
    }


def restore_research_payload(study_id: str, payload: dict[str, Any] | None) -> None:
    if not payload:
        return
    from app.domain.research_evidence_store import (
        put_claim,
        put_conflict,
        put_query,
        put_result,
        put_source,
        put_task,
    )

    for t in payload.get("tasks") or []:
        if isinstance(t, dict):
            put_task(research_task_from_dict(t))
    for q in payload.get("queries") or []:
        if isinstance(q, dict):
            put_query(research_query_from_dict(q))
    for r in payload.get("results") or []:
        if isinstance(r, dict):
            put_result(source_result_from_dict(r))
    for c in payload.get("claims") or []:
        if isinstance(c, dict):
            put_claim(research_claim_from_dict(c))
    for c in payload.get("conflicts") or []:
        if isinstance(c, dict):
            put_conflict(research_conflict_from_dict(c))
    for s in payload.get("sources") or []:
        if isinstance(s, dict):
            put_source(registered_source_from_dict(s))
