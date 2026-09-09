"""Phase 15.5 — Deterministic Statistics Engine (protocol method planning).

Produces STATISTICAL_METHOD_PLAN without fabricating observed GMR/CI.
Canonical ANOVA vocabulary aligns with existing stats_rules ANOVA_TOST_90CI.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.domain.exceptions import ValidationError
from app.domain.statistics_engine_classes import (
    ANOVA_2X2_MODEL_TERMS,
    DESCRIPTIVE_ONLY_DEFAULT,
    LOG_ANOVA_ELIGIBLE,
    METHODOLOGY_VERSION,
    SUPPORTED_DESIGNS_FOR_ANOVA_2X2,
    TMAX_SUMMARY_DEFAULT,
    UNSUPPORTED_DESIGN_MODELS,
)
from app.domain.statistics_explanation import build_statistics_explanation
from app.domain.statistics_models import (
    AcceptanceIntervalSpec,
    ProvenancedChoice,
    StatisticalParameterPlan,
    StatisticsPlan,
    StatisticsScenario,
)
from app.domain.statistics_normalize import (
    normalize_parameter,
    normalize_parameter_list,
    parse_acceptance_interval,
    parse_confidence_level,
)
from app.domain.statistics_store import (
    latest_plan,
    list_plans,
    mark_superseded,
    next_plan_version,
    put_plan,
)


def _fact(context: dict[str, Any] | None, path: str) -> Any:
    if not context:
        return None
    if path in context:
        return context[path]
    facts = context.get("structured_facts") or context.get("facts") or {}
    if isinstance(facts, dict) and path in facts:
        return facts[path]
    return None


def _fact_source(context: dict[str, Any] | None, path: str) -> str:
    if not context:
        return "CURRENT_STUDY_FACT"
    sources = context.get("fact_sources") or {}
    if isinstance(sources, dict) and path in sources:
        return "CURRENT_STUDY_FACT"
    return "CURRENT_STUDY_FACT"


def _fingerprint(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def resolve_design(context: dict[str, Any] | None, design: str | None) -> str | None:
    if design:
        return design
    if not context:
        return None
    if context.get("design"):
        return str(context["design"])
    if _fact(context, "design.crossover") and int(_fact(context, "design.periods") or 0) == 2:
        return "STANDARD_2X2_CROSSOVER"
    if _fact(context, "design.type"):
        return str(_fact(context, "design.type"))
    return None


def collect_pk_parameters(context: dict[str, Any] | None, explicit: list[str] | None) -> list[dict[str, str]]:
    raw: list[str] = list(explicit or [])
    if context:
        params = _fact(context, "pk.parameters")
        if isinstance(params, list):
            raw.extend(str(x) for x in params)
        for token in ("Cmax", "AUC0-72", "AUC0-inf", "Tmax", "t1/2", "kel", "AUCextr", "AUC0-t", "AUC0-x"):
            # golden fixture vocabulary recovery
            if _fact(context, f"pk.{token}") or token in str(_fact(context, "pk.parameters") or ""):
                raw.append(token)
        # also from current_study_facts style keys
        for k, v in (context.get("current_study_facts") or {}).items():
            if k.startswith("pk.") and v:
                raw.append(str(v) if not isinstance(v, bool) else k.split(".", 1)[-1])
    # Always include golden set if provided under known keys
    golden_list = context.get("pk_parameter_list") if context else None
    if isinstance(golden_list, list):
        raw.extend(str(x) for x in golden_list)
    return normalize_parameter_list(raw)


def recompute_statistics_plan(
    *,
    study_id: str,
    context: dict[str, Any] | None = None,
    design: str | None = None,
    parameters: list[str] | None = None,
    confidence_level: float | None = None,
    confidence_level_source: str | None = None,
    acceptance_interval: tuple[float, float] | None = None,
    acceptance_source: str | None = None,
    acceptance_wording: str | None = None,
    transformation: str | None = None,
    transformation_source: str | None = None,
    model: str | None = None,
    model_source: str | None = None,
    analysis_population: str | None = None,
    analysis_population_source: str | None = None,
    primary_be_parameters: list[str] | None = None,
    primary_be_source: str | None = None,
    observed_data_present: bool = False,
    observed_gmr: Any = None,
    observed_ci: Any = None,
    created_by: str | None = None,
    ai_select_method: bool = False,
    decision_id: str | None = None,
    supersede_previous: bool = True,
) -> StatisticsPlan:
    """Build STATISTICAL_METHOD_PLAN from facts + explicit inputs. Never mutates Study."""
    if ai_select_method:
        raise ValidationError("AI cannot select statistical method", field="ai")

    # Refuse fabricated post-study results
    if observed_gmr is not None or observed_ci is not None:
        raise ValidationError(
            "Observed GMR/CI must not be injected without a post-study dataset interface",
            field="observed_data",
        )

    blockers: list[str] = []
    gaps: list[dict[str, Any]] = []
    choices: list[ProvenancedChoice] = []
    current_facts: dict[str, Any] = {}

    design_r = resolve_design(context, design)
    if design_r:
        choices.append(
            ProvenancedChoice(
                name="design",
                value=design_r,
                source_role="CURRENT_STUDY_FACT" if not design else "EXPLICIT_CONFIGURATION",
            )
        )
        current_facts["design"] = design_r

    # Recover synopsis statistics facts as CURRENT_STUDY_FACT (not regulatory requirement)
    syn_method = _fact(context, "statistics.method")
    syn_transform = _fact(context, "statistics.transformation")
    syn_ci = _fact(context, "statistics.confidence_interval")
    syn_acc = _fact(context, "statistics.acceptance_interval")
    for path, val in (
        ("statistics.method", syn_method),
        ("statistics.transformation", syn_transform),
        ("statistics.confidence_interval", syn_ci),
        ("statistics.acceptance_interval", syn_acc),
    ):
        if val is not None:
            current_facts[path] = val
            choices.append(
                ProvenancedChoice(
                    name=path,
                    value=val,
                    source_role="CURRENT_STUDY_FACT",
                    original_wording=str(val),
                    notes="CURRENT_STUDY_FACT — not REGULATORY_REQUIREMENT / not APPROVED_STATISTICAL_PLAN",
                )
            )

    # Confidence level — no silent default
    ci_level = confidence_level
    ci_src = confidence_level_source
    if ci_level is None and syn_ci is not None:
        ci_level = parse_confidence_level(syn_ci)
        ci_src = "CURRENT_STUDY_FACT"
    if ci_level is None:
        blockers.append("MISSING_CONFIDENCE_LEVEL")
        gaps.append({"code": "MISSING_CONFIDENCE_LEVEL", "title": "Confidence level not specified"})
    else:
        if not ci_src:
            blockers.append("MISSING_PROVENANCE")
        else:
            choices.append(
                ProvenancedChoice(name="confidence_level", value=ci_level, source_role=ci_src)
            )

    # Acceptance interval — no silent default
    acc = acceptance_interval
    acc_src = acceptance_source
    acc_word = acceptance_wording
    if acc is None and syn_acc is not None:
        parsed = parse_acceptance_interval(str(syn_acc))
        if parsed:
            acc = parsed
            acc_src = "CURRENT_STUDY_FACT"
            acc_word = str(syn_acc)
    acc_spec = None
    if acc is None:
        blockers.append("MISSING_ACCEPTANCE_INTERVAL")
        gaps.append({"code": "MISSING_ACCEPTANCE_INTERVAL", "title": "BE acceptance interval missing"})
    else:
        if not acc_src:
            blockers.append("MISSING_PROVENANCE")
        else:
            acc_spec = AcceptanceIntervalSpec(
                lower_bound=float(acc[0]),
                upper_bound=float(acc[1]),
                source_role=acc_src,
                verification_status="UNVERIFIED"
                if acc_src == "CURRENT_STUDY_FACT"
                else "EXPLICIT",
                original_wording=acc_word,
            )
            choices.append(
                ProvenancedChoice(
                    name="acceptance_interval",
                    value={"lower": acc[0], "upper": acc[1]},
                    source_role=acc_src,
                    original_wording=acc_word,
                    verification_status=acc_spec.verification_status,
                )
            )

    # Alpha derived from confidence level when CI known (explicit deterministic rule)
    alpha = None
    alpha_derivation = None
    if ci_level is not None:
        # TOST: 100(1-2α)% CI ⇒ α = (1 − CI) / 2  (e.g. 90% CI → α=0.05)
        alpha = round((1.0 - float(ci_level)) / 2.0, 12)
        alpha_derivation = (
            "DETERMINISTIC_FROM_CONFIDENCE_LEVEL: "
            f"TOST per-side alpha = (1 - {ci_level}) / 2 = {alpha}"
        )
        choices.append(
            ProvenancedChoice(
                name="alpha",
                value=alpha,
                source_role="EXPLICIT_CONFIGURATION",
                notes=alpha_derivation,
            )
        )

    # Transformation
    transform = transformation
    transform_src = transformation_source
    if transform is None and syn_transform is not None:
        t = str(syn_transform).lower()
        transform = "LOG" if "log" in t else None
        transform_src = "CURRENT_STUDY_FACT"
    if transform is None:
        blockers.append("MISSING_TRANSFORMATION")
        gaps.append({"code": "MISSING_TRANSFORMATION", "title": "Transformation not specified for BE params"})
    elif not transform_src:
        blockers.append("MISSING_PROVENANCE")
    else:
        choices.append(
            ProvenancedChoice(name="transformation", value=transform, source_role=transform_src)
        )

    # Model selection
    selected_model = model
    model_src = model_source
    model_terms: list[str] = []
    if design_r and design_r in UNSUPPORTED_DESIGN_MODELS:
        blockers.append("METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW")
        selected_model = None
    elif design_r and design_r not in SUPPORTED_DESIGNS_FOR_ANOVA_2X2 and selected_model == "ANOVA_LOG_2X2":
        blockers.append("METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW")
        selected_model = None
    else:
        if selected_model is None:
            # Recover ANOVA mention as CURRENT_STUDY_FACT recommendation only when design supports it
            if syn_method and "ANOVA" in str(syn_method).upper():
                if design_r in SUPPORTED_DESIGNS_FOR_ANOVA_2X2 or design_r is None:
                    # If design unknown but ANOVA mentioned, still recommend with review required
                    selected_model = "ANOVA_LOG_2X2"
                    model_src = "CURRENT_STUDY_FACT"
        if selected_model == "ANOVA_LOG_2X2":
            if design_r and design_r not in SUPPORTED_DESIGNS_FOR_ANOVA_2X2:
                blockers.append("METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW")
                selected_model = None
            else:
                model_terms = list(ANOVA_2X2_MODEL_TERMS)
                if not model_src:
                    blockers.append("MISSING_PROVENANCE")
                else:
                    choices.append(
                        ProvenancedChoice(
                            name="statistical_model",
                            value=selected_model,
                            source_role=model_src,
                            notes="Reuses canonical ANOVA_TOST_90CI vocabulary; model terms not invented",
                        )
                    )
        elif selected_model is None:
            blockers.append("MISSING_STATISTICAL_MODEL")
            gaps.append({"code": "MISSING_STATISTICAL_MODEL", "title": "Statistical model not specified"})

    # Analysis population
    if analysis_population is None:
        blockers.append("MISSING_ANALYSIS_POPULATION_RULE")
        gaps.append(
            {
                "code": "MISSING_ANALYSIS_POPULATION_RULE",
                "title": "Analysis population requires expert decision",
            }
        )
        # also mark requires expert
        if "REQUIRES_EXPERT_DECISION" not in blockers:
            blockers.append("REQUIRES_EXPERT_DECISION")
    else:
        src = analysis_population_source or "EXPERT_DECISION"
        choices.append(
            ProvenancedChoice(
                name="analysis_population",
                value=analysis_population,
                source_role=src,
            )
        )

    # Parameters
    param_rows = collect_pk_parameters(context, parameters)
    # Ensure golden fixture tokens present when context includes them as facts
    for token in ("Cmax", "AUC0-72", "AUC0-inf", "Tmax", "t1/2", "kel", "AUCextr"):
        if any(r.get("canonical") == token for r in param_rows):
            current_facts[f"pk.{token}"] = token

    if not any(r.get("canonical") for r in param_rows):
        blockers.append("MISSING_PRIMARY_PK_PARAMETER")
        gaps.append({"code": "MISSING_PRIMARY_PK_PARAMETER", "title": "No PK parameters recovered"})

    # Primary BE only via expert decision or verified rule — never silent from synopsis alone
    primary_set: set[str] = set()
    if primary_be_parameters:
        if primary_be_source not in {"EXPERT_DECISION", "VERIFIED_RULE", "VERIFIED_EVIDENCE"}:
            blockers.append("MISSING_PROVENANCE")
        else:
            for p in primary_be_parameters:
                c, _ = normalize_parameter(p)
                if c:
                    primary_set.add(c)
            choices.append(
                ProvenancedChoice(
                    name="primary_be_parameters",
                    value=sorted(primary_set),
                    source_role=primary_be_source,
                )
            )
    # Synopsis primary_parameters are CURRENT_STUDY_FACT recommendations only
    syn_primary = _fact(context, "pk.primary_parameters")
    recommended_primary: list[str] = []
    if isinstance(syn_primary, list):
        for p in syn_primary:
            c, _ = normalize_parameter(str(p))
            if c:
                recommended_primary.append(c)
        current_facts["pk.primary_parameters"] = recommended_primary
        choices.append(
            ProvenancedChoice(
                name="synopsis_primary_parameters",
                value=recommended_primary,
                source_role="CURRENT_STUDY_FACT",
                notes="Not auto-promoted to PRIMARY_BE without expert/verified rule",
            )
        )

    # Conflicting AUC endpoints → scenarios
    auc_endpoints = [
        r["canonical"]
        for r in param_rows
        if r.get("canonical") in {"AUC0-72", "AUC0-inf", "AUC0-t", "AUC0-x"}
    ]
    scenarios: list[StatisticsScenario] = []
    if len(set(auc_endpoints)) > 1 and "Cmax" in {r.get("canonical") for r in param_rows}:
        for auc in sorted(set(auc_endpoints)):
            scenarios.append(
                StatisticsScenario(
                    label=f"{auc} + Cmax",
                    primary_parameters=[auc, "Cmax"],
                    status="REQUIRES_EXPERT_SELECTION",
                )
            )
        blockers.append("REQUIRES_EXPERT_SELECTION")
        blockers.append("CONFLICTING_ENDPOINT_DEFINITIONS")

    # Conflicting acceptance intervals if multiple provided
    extra_acc = context.get("acceptance_interval_candidates") if context else None
    if isinstance(extra_acc, list) and len(extra_acc) > 1:
        blockers.append("CONFLICTING_ACCEPTANCE_INTERVALS")

    param_plans: list[StatisticalParameterPlan] = []
    for row in param_rows:
        canon = row.get("canonical") or ""
        orig = row.get("original") or canon
        if not canon:
            blockers.append("UNSUPPORTED_PARAMETER")
            continue

        if canon in DESCRIPTIVE_ONLY_DEFAULT or canon == "Tmax":
            role = "DESCRIPTIVE"
            tr = "NONE"
            mdl = None
            est = "NONE"
            summary = list(TMAX_SUMMARY_DEFAULT) if canon == "Tmax" else ["N", "Mean", "SD", "Min", "Median", "Max"]
            p_blockers: list[str] = []
            # Guard: never apply LOG-ANOVA to Tmax
            if selected_model == "ANOVA_LOG_2X2" and canon == "Tmax":
                # model not applied
                pass
        elif canon in primary_set:
            role = "PRIMARY_BE"
            tr = transform or "LOG"
            if tr != "LOG" and canon in LOG_ANOVA_ELIGIBLE:
                p_blockers = ["MISSING_TRANSFORMATION"]
            else:
                p_blockers = []
            mdl = selected_model if canon in LOG_ANOVA_ELIGIBLE else None
            est = (
                "GEOMETRIC_MEAN_RATIO_TEST_REFERENCE"
                if mdl == "ANOVA_LOG_2X2"
                else "NONE"
            )
            summary = ["N", "Geometric Mean", "CV%", "Min", "Max"]
        elif canon in LOG_ANOVA_ELIGIBLE:
            # Source-derived candidate — recommendation role SECONDARY until expert promotes
            role = "SECONDARY_PK"
            tr = transform or "LOG"
            mdl = selected_model if transform == "LOG" or (transform is None and syn_transform) else selected_model
            if transform is None and syn_transform:
                tr = "LOG"
            mdl = selected_model if tr == "LOG" else None
            est = (
                "GEOMETRIC_MEAN_RATIO_TEST_REFERENCE"
                if mdl == "ANOVA_LOG_2X2"
                else "NONE"
            )
            summary = ["N", "Geometric Mean", "CV%"]
            p_blockers = []
            if role != "PRIMARY_BE" and canon in recommended_primary:
                # stays secondary/recommendation until expert
                pass
        else:
            role = "NOT_ANALYZED_FOR_BE"
            tr = "NONE"
            mdl = None
            est = "NONE"
            summary = ["N", "Mean", "SD"]
            p_blockers = []

        if observed_data_present is False:
            # method plan only
            if "NO_OBSERVED_DATA_NO_FABRICATED_GMR" not in blockers:
                # informational — not necessarily blocking plan creation
                pass

        pp = StatisticalParameterPlan(
            parameter=canon,
            role=role,
            transformation=tr if tr in {"NONE", "LOG"} else "NONE",
            model=mdl,
            estimate=est,
            confidence_interval=ci_level if mdl else None,
            acceptance_interval=acc_spec if mdl else None,
            summary_method=summary,
            status="DRAFT",
            original_wording=orig,
            model_terms=list(model_terms) if mdl else [],
            observed_data_present=False,
            blocking_reasons=p_blockers,
        )
        param_plans.append(pp)

    # Status
    uniq_blockers: list[str] = []
    seen: set[str] = set()
    for b in blockers:
        if b not in seen:
            seen.add(b)
            uniq_blockers.append(b)
    blockers = uniq_blockers

    hard = {
        "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
        "MISSING_STATISTICAL_MODEL",
        "MISSING_PRIMARY_PK_PARAMETER",
        "MISSING_PROVENANCE",
        "UNSUPPORTED_PARAMETER",
    }
    if hard.intersection(blockers) and "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW" in blockers:
        status = "BLOCKED"
    elif blockers:
        status = "REVIEW_REQUIRED"
    else:
        status = "DRAFT"

    # Versioning
    prev = latest_plan(study_id)
    version = next_plan_version(study_id)
    supersedes = None
    if supersede_previous and prev is not None:
        mark_superseded(prev.id, reason="recompute")
        supersedes = prev.id

    fp = _fingerprint(
        {
            "design": design_r,
            "parameters": [p.parameter for p in param_plans],
            "roles": {p.parameter: p.role for p in param_plans},
            "transformation": transform,
            "model": selected_model,
            "confidence_level": ci_level,
            "acceptance": acc,
            "population": analysis_population,
            "methodology_version": METHODOLOGY_VERSION,
        }
    )

    recommendation = (
        "STATISTICAL_RECOMMENDATION from current study facts / explicit inputs — "
        "not APPROVED_STATISTICAL_PLAN; not REGULATORY_REQUIREMENT"
    )

    plan = StatisticsPlan(
        study_id=study_id,
        decision_id=decision_id,
        version=version,
        status=status,
        created_by=created_by,
        design=design_r,
        model=selected_model,
        model_terms=model_terms,
        confidence_level=ci_level,
        alpha=alpha,
        alpha_derivation=alpha_derivation,
        acceptance_interval=acc_spec,
        analysis_population=analysis_population,
        parameters=param_plans,
        scenarios=scenarios,
        choices=choices,
        current_study_facts=current_facts,
        recommendation_summary=recommendation,
        blocking_reasons=blockers,
        knowledge_gaps=gaps,
        supersedes_id=supersedes,
        fingerprint=fp,
        observed_data_present=False,
        study_mutated=False,
        audit=[{"event": "CREATE", "version": version, "fingerprint": fp}],
    )
    for p in plan.parameters:
        p.plan_id = plan.id
    plan.explanation = build_statistics_explanation(plan)
    put_plan(plan)
    return plan


def invalidate_statistics_on_change(
    study_id: str,
    *,
    changed_field: str,
) -> dict[str, Any]:
    """Design / endpoint changes supersede active statistics plans."""
    stats_fields = {
        "design",
        "design.type",
        "design.periods",
        "design.sequences",
        "pk.parameters",
        "pk.primary_parameters",
        "pk.AUC_endpoint",
        "pk.Cmax",
        "statistics.method",
        "statistics.transformation",
        "statistics.confidence_interval",
        "statistics.acceptance_interval",
        "evidence_version",
    }
    # normalize
    cf = changed_field
    affected = any(
        cf == f or cf.startswith(f + ".") or f.startswith(cf)
        for f in stats_fields
    ) or cf in {"tmax", "Tmax", "Cmax", "AUC0-72", "AUC0-inf"}
    superseded: list[str] = []
    if affected:
        for p in list_plans(study_id):
            if p.status in {"DRAFT", "REVIEW_REQUIRED", "APPROVED"}:
                mark_superseded(p.id, reason=f"upstream_change:{changed_field}")
                superseded.append(p.id)
    return {
        "study_id": study_id,
        "changed_field": changed_field,
        "affected": affected,
        "superseded_plan_ids": superseded,
        "study_mutated": False,
    }


def apply_expert_modifications(
    old: StatisticsPlan,
    modifications: dict[str, Any],
    *,
    reviewer: str,
) -> StatisticsPlan:
    """Create a new plan version from expert modifications."""
    ctx = {
        "structured_facts": dict(old.current_study_facts),
        "pk_parameter_list": [p.parameter for p in old.parameters],
    }
    # merge modifications
    params = modifications.get("parameters") or [p.parameter for p in old.parameters]
    primary = modifications.get("primary_be_parameters")
    primary_src = "EXPERT_DECISION" if primary is not None else None
    if primary is None:
        primary = [p.parameter for p in old.parameters if p.role == "PRIMARY_BE"]
        primary_src = "EXPERT_DECISION" if primary else None

    acc = modifications.get("acceptance_interval")
    if acc is None and old.acceptance_interval:
        acc = (old.acceptance_interval.lower_bound, old.acceptance_interval.upper_bound)

    return recompute_statistics_plan(
        study_id=old.study_id,
        context=ctx,
        design=modifications.get("design", old.design),
        parameters=params,
        confidence_level=modifications.get("confidence_level", old.confidence_level),
        confidence_level_source="EXPERT_DECISION",
        acceptance_interval=tuple(acc) if acc else None,
        acceptance_source="EXPERT_DECISION" if acc else None,
        transformation=modifications.get("transformation")
        or next((c.value for c in old.choices if c.name == "transformation"), None),
        transformation_source="EXPERT_DECISION",
        model=modifications.get("model", old.model),
        model_source="EXPERT_DECISION",
        analysis_population=modifications.get(
            "analysis_population", old.analysis_population or "PK_ANALYSIS_SET"
        ),
        analysis_population_source="EXPERT_DECISION",
        primary_be_parameters=primary,
        primary_be_source=primary_src,
        created_by=reviewer,
        supersede_previous=False,  # already marked by modify_plan
    )


def ui_statistics_panel(study_id: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    plan = latest_plan(study_id)
    return {
        "section": "STATISTICS",
        "title": "Статистический план",
        "study_id": study_id,
        "plan_id": plan.id if plan else None,
        "status": plan.status if plan else "NO_PLAN",
        "parameters": [p.display_dict() for p in (plan.parameters if plan else [])],
        "scenarios": [s.to_dict() for s in (plan.scenarios if plan else [])],
        "current_study_facts": plan.current_study_facts if plan else (context or {}),
        "recommendation_summary": plan.recommendation_summary if plan else None,
        "blocking_reasons": plan.blocking_reasons if plan else [],
        "knowledge_gaps": plan.knowledge_gaps if plan else [],
        "is_approved": bool(plan and plan.status == "APPROVED"),
        "recommendation_shown_as_approved": False,
        "exposes_internal_enums": False,
        "study_mutated": False,
        "actions": ["Открыть evidence", "Изменить", "На проверку"],
        "warning": "Требуется проверка методологии" if plan and plan.status != "APPROVED" else None,
    }


def golden_updcb_context() -> dict[str, Any]:
    """Source-derived facts for UPDCB-02-BE-2026-REAL-01 (not universal defaults)."""
    return {
        "fixture_id": "UPDCB-02-BE-2026-REAL-01",
        "design": "STANDARD_2X2_CROSSOVER",
        "design.crossover": True,
        "design.periods": 2,
        "design.sequences": 2,
        "structured_facts": {
            "design.crossover": True,
            "design.periods": 2,
            "design.sequences": 2,
            "pk.parameters": ["Cmax", "AUC0-72", "AUC0-inf", "Tmax", "t1/2", "kel", "AUCextr"],
            "pk.primary_parameters": ["Cmax", "AUC0-72", "AUC0-inf"],
            "pk.AUC_endpoint": "AUC0-72",
            "pk.Cmax": True,
            "pk.Tmax": True,
            "pk.t_half": True,
            "statistics.method": "ANOVA",
            "statistics.transformation": "log",
            "statistics.confidence_interval": "90%",
            "statistics.acceptance_interval": "80.00-125.00%",
            "subjects.randomized_n": 56,
        },
        "fact_sources": {
            "statistics.method": "SYNOPSIS",
            "statistics.transformation": "SYNOPSIS",
            "statistics.confidence_interval": "SYNOPSIS",
            "statistics.acceptance_interval": "SYNOPSIS",
            "pk.parameters": "SYNOPSIS",
        },
        "pk_parameter_list": ["Cmax", "AUC0-72", "AUC0-inf", "Tmax", "t1/2", "kel", "AUCextr"],
    }
