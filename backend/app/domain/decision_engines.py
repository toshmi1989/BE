"""FOOD / WASHOUT / SAMPLING / ANALYTE_PK decision engines — Phase 15.0 / 15.1."""

from __future__ import annotations

from app.domain.decision_blockers import apply_dependency_blockers
from app.domain.decision_context import DecisionContext
from app.domain.decision_matrix import build_option_matrix_row, evidence, make_recommendation
from app.domain.decision_models import ProtocolDecision


def _attach(d: ProtocolDecision) -> ProtocolDecision:
    for e in d.evidence:
        e.decision_id = d.id
    if d.recommendation:
        d.recommendation.decision_id = d.id
    d.study_mutated = False
    return d


def evaluate_food(ctx: DecisionContext) -> ProtocolDecision:
    d = ProtocolDecision(
        domain="FOOD",
        subject="Food condition selection",
        study_id=ctx.study_id,
        project_id=ctx.project_id,
        package_id=ctx.package_id,
    )
    f = ctx.structured_facts
    ev = []
    cond = f.get("design.conditions") or f.get("food.condition")
    fasting = f.get("treatment.fasting") is True or (isinstance(cond, list) and "fasting" in cond) or (
        isinstance(cond, str) and "fasting" in cond
    )
    fed = f.get("treatment.fed") is True or (isinstance(cond, list) and "fed" in cond) or (
        isinstance(cond, str) and "fed" in cond
    )

    if fasting or fed:
        opt = "FASTING_AND_FED" if fasting and fed else ("FASTING" if fasting else "FED")
        ev.append(
            evidence(
                evidence_type="STRUCTURED_STUDY_FACT",
                support_level="SUPPORTS",
                option=opt,
                excerpt=f"Study inputs describe conditions={cond}",
                status=ctx.fact_statuses.get("design.conditions")
                or ctx.fact_statuses.get("treatment.fasting")
                or "PROPOSED",
                source_id=ctx.fact_sources.get("design.conditions")
                or ctx.fact_sources.get("treatment.fasting"),
                decision_source_type="CURRENT_STUDY_FACT",
                applicability="DIRECT",
                applicability_reason="Current protocol food-condition fact from study inputs",
            )
        )
    else:
        opt = "FOOD_CONDITION_REQUIRES_EXPERT_DECISION"

    for ic in ctx.interview_claims:
        if ic.get("domain") == "FOOD":
            ev.append(
                evidence(
                    evidence_type="EXPERT_INTERVIEW",
                    support_level="CONTEXT_ONLY",
                    excerpt=f"Expert interview evidence suggests: {ic.get('normalized_claim')}",
                    status="PROPOSED",
                    claim_id=ic.get("claim_id"),
                    notes="Interview ≠ regulation",
                    applicability="UNKNOWN",
                    applicability_reason="Interview applicability not reviewed",
                )
            )
    for rule in ctx.expert_rules_proposed:
        if rule.get("domain") == "FOOD":
            ev.append(
                evidence(
                    evidence_type="EXPERT_RULE",
                    support_level="CONTEXT_ONLY",
                    excerpt=rule.get("description") or rule.get("rule_code"),
                    status="PROPOSED",
                    rule_id=rule.get("rule_code"),
                    applicability="UNKNOWN",
                    applicability_reason="Proposed rule applicability not reviewed",
                )
            )

    if not (f.get("food.calorie_target") or f.get("food.fat_target")):
        d.knowledge_gaps.append(
            {
                "code": "MISSING_MEAL_COMPOSITION",
                "title": "Calorie/fat meal targets not verified",
                "severity": "MEDIUM",
                "blocking": False,
                "notes": "Do not invent calorie/fat targets",
            }
        )

    report = apply_dependency_blockers(d, ctx)
    blocking = report.blocked
    d.evidence = ev
    d.current_context = {"conditions": cond, "fasting": fasting, "fed": fed}

    primary = (
        "FASTING_AND_FED"
        if fasting and fed
        else ("FASTING" if fasting else ("FED" if fed else "FOOD_CONDITION_REQUIRES_EXPERT_DECISION"))
    )
    matrix = []
    for o in ("FASTING", "FED", "FASTING_AND_FED", "FOOD_CONDITION_REQUIRES_EXPERT_DECISION"):
        if blocking:
            st = "BLOCKED"
        elif o == primary and (fasting or fed):
            st = "PARTIALLY_SUPPORTED"
        else:
            st = "INSUFFICIENT_EVIDENCE"
        matrix.append(build_option_matrix_row(option=o, evidence=ev, recommendation_status=st, missing=[]))
    d.option_matrix = matrix

    if blocking:
        d.status = "BLOCKED"
        d.recommendation = make_recommendation(
            option=primary,
            status="BLOCKED",
            confidence="NONE",
            evidence=ev,
            blocking_conflicts=d.blocking_conflicts,
            rationale="Food decision blocked by registered dependency blockers.",
            explanation={
                "blocking_reasons": [b.to_dict() for b in report.blocking_reasons],
                "non_blocking_issues": [b.to_dict() for b in report.non_blocking_issues],
            },
        )
    elif fasting or fed:
        d.status = "REVIEW_REQUIRED"
        d.recommendation = make_recommendation(
            option=primary,
            status="PARTIALLY_SUPPORTED",
            confidence="LOW",
            evidence=ev,
            missing_codes=["MISSING_MEAL_COMPOSITION"]
            if any(g.get("code") == "MISSING_MEAL_COMPOSITION" for g in d.knowledge_gaps)
            else [],
            rationale=(
                f"Structured study facts support food condition '{primary}'. "
                "Expert interview evidence is contextual only. No verified meal composition targets. "
                "Recommendation is not an approved decision. "
                "Reference-product dose conflict does not block FOOD (not a registered dependency)."
            ),
            explanation={
                "non_blocking_issues": [b.to_dict() for b in report.non_blocking_issues],
                "required_action": "Medical writer review",
            },
        )
    else:
        d.status = "REVIEW_REQUIRED"
        d.recommendation = make_recommendation(
            option="FOOD_CONDITION_REQUIRES_EXPERT_DECISION",
            status="INSUFFICIENT_EVIDENCE",
            confidence="NONE",
            evidence=ev,
            missing_codes=["MISSING_FOOD_CONDITION"],
            rationale="No structured food condition found in verified/proposed inputs.",
            explanation={"non_blocking_issues": [b.to_dict() for b in report.non_blocking_issues]},
        )
    return _attach(d)


def evaluate_washout(ctx: DecisionContext) -> ProtocolDecision:
    d = ProtocolDecision(
        domain="WASHOUT",
        subject="Washout duration",
        study_id=ctx.study_id,
        project_id=ctx.project_id,
        package_id=ctx.package_id,
    )
    ev = []
    f = ctx.structured_facts
    duration = f.get("washout.duration")
    unit = f.get("washout.unit")
    half_life_numeric = ctx.half_life

    if half_life_numeric is None:
        d.knowledge_gaps.append(
            {
                "code": "MISSING_HALF_LIFE_FOR_WASHOUT",
                "title": "Half-life (t½) unavailable for washout calculation",
                "severity": "HIGH",
                "blocking": True,
            }
        )
        d.research_tasks.append(
            {
                "code": "FIND_HALF_LIFE_PK",
                "title": "Research official PK / SmPC for half-life",
                "status": "OPEN",
            }
        )

    if duration is not None:
        ev.append(
            evidence(
                evidence_type="STRUCTURED_STUDY_FACT",
                support_level="SUPPORTS",
                option="FIXED_DURATION",
                excerpt=f"Source package states washout duration={duration} {unit or ''}".strip(),
                status=ctx.fact_statuses.get("washout.duration", "PROPOSED"),
                source_id=ctx.fact_sources.get("washout.duration"),
                notes="CURRENT_STUDY_FACT — not a SYSTEM_RECOMMENDATION or calculated value",
                decision_source_type="CURRENT_STUDY_FACT",
                applicability="DIRECT",
                applicability_reason="Current protocol washout value from study inputs (e.g. Synopsis)",
            )
        )

    for rule in ctx.expert_rules_proposed:
        if rule.get("domain") == "WASHOUT":
            ev.append(
                evidence(
                    evidence_type="EXPERT_RULE",
                    support_level="CONTEXT_ONLY",
                    option="EXPERT_DEFINED",
                    excerpt=f"Expert evidence (not verified active rule): {rule.get('description')}",
                    status="PROPOSED",
                    rule_id=rule.get("rule_code"),
                    notes="Do not treat as active regulatory washout calculation",
                    applicability="UNKNOWN",
                    applicability_reason="Proposed rule applicability not reviewed",
                )
            )

    report = apply_dependency_blockers(d, ctx)
    blocking = report.blocked
    d.evidence = ev
    d.current_context = {
        "washout_duration": duration,
        "washout_unit": unit,
        "half_life_numeric": half_life_numeric,
        "calculated": False,
        "current_fact_vs_recommendation": "CURRENT_STUDY_FACT preserved separately from SYSTEM_RECOMMENDATION",
    }

    missing = ["MISSING_HALF_LIFE_FOR_WASHOUT"] if half_life_numeric is None else []

    if half_life_numeric is None:
        # Dependency graph blocks HALF_LIFE_DERIVED; current fact may still be shown
        primary = "FIXED_DURATION" if duration is not None else "INSUFFICIENT_EVIDENCE"
        if blocking:
            d.status = "BLOCKED"
            rec_status = "BLOCKED"
            conf = "NONE"
        else:
            d.status = "REVIEW_REQUIRED"
            rec_status = "PARTIALLY_SUPPORTED" if duration is not None else "INSUFFICIENT_EVIDENCE"
            conf = "LOW" if duration is not None else "NONE"

        d.option_matrix = [
            build_option_matrix_row(
                option="FIXED_DURATION",
                evidence=ev,
                recommendation_status="BLOCKED"
                if blocking
                else ("PARTIALLY_SUPPORTED" if duration is not None else "INSUFFICIENT_EVIDENCE"),
                missing=missing,
            ),
            build_option_matrix_row(
                option="HALF_LIFE_DERIVED",
                evidence=ev,
                recommendation_status="BLOCKED" if blocking else "INSUFFICIENT_EVIDENCE",
                missing=missing,
            ),
            build_option_matrix_row(
                option="EXPERT_DEFINED",
                evidence=ev,
                recommendation_status="BLOCKED" if blocking else "INSUFFICIENT_EVIDENCE",
                missing=missing,
            ),
            build_option_matrix_row(
                option="INSUFFICIENT_EVIDENCE",
                evidence=ev,
                recommendation_status="INSUFFICIENT_EVIDENCE",
                missing=missing,
            ),
        ]
        d.recommendation = make_recommendation(
            option=primary,
            status=rec_status,
            confidence=conf,
            evidence=ev,
            missing_codes=missing,
            blocking_conflicts=d.blocking_conflicts,
            rationale=(
                "Half-life unavailable — washout was NOT calculated. "
                + (
                    f"A fixed duration of {duration} {unit or 'day(s)'} appears in study inputs as "
                    "CURRENT_STUDY_FACT only (not a SYSTEM_RECOMMENDATION). "
                    if duration is not None
                    else "No washout duration available. "
                )
                + "Reference-product dose conflict does not block WASHOUT (not a registered dependency)."
            ),
            explanation={
                "why": "Missing t½ blocks HALF_LIFE_DERIVED calculation",
                "blocking_reasons": [b.to_dict() for b in report.blocking_reasons],
                "non_blocking_issues": [b.to_dict() for b in report.non_blocking_issues],
                "missing": missing,
                "required_action": "Obtain verified half-life or expert KEEP_CURRENT_VALUE / EXPERT_DEFINED",
            },
        )
        return _attach(d)

    verified_wash = [r for r in ctx.verified_rules if r.get("domain") == "WASHOUT"]
    if not verified_wash:
        d.status = "REVIEW_REQUIRED" if not blocking else "BLOCKED"
        d.option_matrix = [
            build_option_matrix_row(
                option=o,
                evidence=ev,
                recommendation_status="BLOCKED" if blocking else "INSUFFICIENT_EVIDENCE",
                missing=["MISSING_ACTIVE_WASHOUT_RULE"],
            )
            for o in ("FIXED_DURATION", "HALF_LIFE_DERIVED", "EXPERT_DEFINED", "INSUFFICIENT_EVIDENCE")
        ]
        d.recommendation = make_recommendation(
            option="EXPERT_DEFINED",
            status="BLOCKED" if blocking else "INSUFFICIENT_EVIDENCE",
            confidence="LOW",
            evidence=ev,
            missing_codes=["MISSING_ACTIVE_WASHOUT_RULE"],
            blocking_conflicts=d.blocking_conflicts,
            rationale="Numeric half-life present but no ACTIVE verified washout rule — do not invent multiplier.",
            explanation={
                "blocking_reasons": [b.to_dict() for b in report.blocking_reasons],
                "non_blocking_issues": [b.to_dict() for b in report.non_blocking_issues],
            },
        )
    return _attach(d)


def evaluate_sampling(ctx: DecisionContext) -> ProtocolDecision:
    d = ProtocolDecision(
        domain="SAMPLING",
        subject="Sampling schedule",
        study_id=ctx.study_id,
        project_id=ctx.project_id,
        package_id=ctx.package_id,
    )
    ev = []
    f = ctx.structured_facts
    times = f.get("sampling.times")
    n_points = f.get("sampling.total_points")

    if times:
        ev.append(
            evidence(
                evidence_type="STRUCTURED_STUDY_FACT",
                support_level="SUPPORTS",
                option="STANDARD_PROFILE",
                excerpt=f"Source package lists sampling times (n={n_points or len(times)})",
                status=ctx.fact_statuses.get("sampling.times", "PROPOSED"),
                source_id=ctx.fact_sources.get("sampling.times"),
                notes="Existing plan from inputs — not newly invented timepoints",
                decision_source_type="CURRENT_STUDY_FACT",
                applicability="DIRECT",
                applicability_reason="Current protocol sampling plan from study inputs",
            )
        )

    if ctx.tmax is None:
        d.knowledge_gaps.append(
            {
                "code": "MISSING_TMAX_FOR_SAMPLING",
                "title": "Tmax unavailable for sampling derivation",
                "severity": "HIGH",
                "blocking": True,
            }
        )
        d.research_tasks.append(
            {
                "code": "FIND_TMAX_PK",
                "title": "Research Tmax from official PK / literature",
                "status": "OPEN",
            }
        )
    if ctx.half_life is None:
        d.knowledge_gaps.append(
            {
                "code": "MISSING_HALF_LIFE_FOR_WASHOUT",
                "title": "Half-life unavailable for sampling terminal-phase assessment",
                "severity": "HIGH",
                "blocking": True,
            }
        )

    report = apply_dependency_blockers(d, ctx)
    blocking = report.blocked
    d.evidence = ev
    d.current_context = {
        "sampling_times": times,
        "total_points": n_points,
        "tmax": ctx.tmax,
        "half_life": ctx.half_life,
        "invented_timepoints": False,
    }

    missing = []
    if ctx.tmax is None:
        missing.append("MISSING_TMAX_FOR_SAMPLING")
    if ctx.half_life is None:
        missing.append("MISSING_HALF_LIFE_FOR_WASHOUT")

    if blocking:
        d.status = "BLOCKED"
        primary = "STANDARD_PROFILE" if times else "EXPERT_DEFINED"
        rec_status = "BLOCKED"
        conf = "NONE"
        rationale = (
            "Sampling blocked by registered dependencies: "
            + ", ".join(b.blocking_reason_code for b in report.blocking_reasons)
            + ". Reference-product dose conflict does not block SAMPLING."
        )
    elif times and ctx.tmax is None:
        d.status = "REVIEW_REQUIRED"
        primary = "STANDARD_PROFILE"
        rec_status = "PARTIALLY_SUPPORTED"
        conf = "LOW"
        rationale = (
            "Existing sampling profile present in study inputs. "
            "Tmax unavailable — system did NOT invent or replace timepoints."
        )
    elif not times:
        d.status = "REVIEW_REQUIRED"
        primary = "EXPERT_DEFINED"
        rec_status = "INSUFFICIENT_EVIDENCE"
        conf = "NONE"
        rationale = "Insufficient evidence to derive a scientifically defensible sampling schedule. No timepoints invented."
    else:
        d.status = "REVIEW_REQUIRED"
        primary = "STANDARD_PROFILE"
        rec_status = "PARTIALLY_SUPPORTED"
        conf = "MEDIUM"
        rationale = "Sampling profile present with supporting structured facts."

    d.option_matrix = [
        build_option_matrix_row(
            option=o,
            evidence=ev,
            recommendation_status=rec_status if o == primary else ("BLOCKED" if blocking else "INSUFFICIENT_EVIDENCE"),
            missing=missing,
        )
        for o in ("STANDARD_PROFILE", "EXTENDED_TERMINAL_PHASE", "ADAPTIVE_SAMPLING", "EXPERT_DEFINED")
    ]
    d.recommendation = make_recommendation(
        option=primary,
        status=rec_status,
        confidence=conf,
        evidence=ev,
        missing_codes=missing,
        blocking_conflicts=d.blocking_conflicts,
        rationale=rationale,
        explanation={
            "proposed_sampling_profile": times,
            "blocking_reasons": [b.to_dict() for b in report.blocking_reasons],
            "non_blocking_issues": [b.to_dict() for b in report.non_blocking_issues],
            "terminal_phase_assessment": "NOT_ASSESSED" if ctx.tmax is None else "REVIEW",
            "tmax_coverage_assessment": "NOT_ASSESSED" if ctx.tmax is None else "REVIEW",
            "invented_timepoints": False,
            "required_action": "Medical writer review",
        },
    )
    return _attach(d)


def evaluate_analyte_pk(ctx: DecisionContext) -> ProtocolDecision:
    d = ProtocolDecision(
        domain="ANALYTE_PK",
        subject="Analyte / PK selection",
        study_id=ctx.study_id,
        project_id=ctx.project_id,
        package_id=ctx.package_id,
    )
    ev = []
    f = ctx.structured_facts
    analyte = f.get("bioanalysis.analyte") or f.get("test_product.active_substance")

    if analyte:
        ev.append(
            evidence(
                evidence_type="STRUCTURED_STUDY_FACT",
                support_level="SUPPORTS",
                option="PARENT_DRUG",
                excerpt=f"Source package identifies analyte/active substance: {analyte}",
                status=ctx.fact_statuses.get("bioanalysis.analyte")
                or ctx.fact_statuses.get("test_product.active_substance")
                or "PROPOSED",
                source_id=ctx.fact_sources.get("bioanalysis.analyte")
                or ctx.fact_sources.get("test_product.active_substance"),
                decision_source_type="CURRENT_STUDY_FACT",
                applicability="DIRECT",
                applicability_reason="Current protocol analyte identity from study inputs",
            )
        )
    else:
        d.knowledge_gaps.append(
            {
                "code": "MISSING_ANALYTE",
                "title": "Analyte identity unavailable",
                "severity": "HIGH",
                "blocking": True,
            }
        )

    for ic in ctx.interview_claims:
        if ic.get("domain") == "ANALYTE":
            ev.append(
                evidence(
                    evidence_type="EXPERT_INTERVIEW",
                    support_level="CONTEXT_ONLY",
                    option="PARENT_DRUG",
                    excerpt=f"Expert interview evidence suggests: {ic.get('normalized_claim')}",
                    status="PROPOSED",
                    claim_id=ic.get("claim_id"),
                    notes="Parent analyte typical per interview — not independently verified rule",
                    applicability="UNKNOWN",
                    applicability_reason="Interview applicability not reviewed",
                )
            )

    report = apply_dependency_blockers(d, ctx)
    blocking = report.blocked
    d.evidence = ev
    d.current_context = {"analyte": analyte, "metabolite_auto_added": False}

    primary = "PARENT_DRUG" if analyte else "EXPERT_DEFINED"
    if blocking:
        d.status = "BLOCKED"
        rec_status = "BLOCKED"
        conf = "NONE"
    elif analyte:
        d.status = "REVIEW_REQUIRED"
        rec_status = "PARTIALLY_SUPPORTED"
        conf = "LOW"
    else:
        d.status = "REVIEW_REQUIRED"
        rec_status = "INSUFFICIENT_EVIDENCE"
        conf = "NONE"

    d.option_matrix = [
        build_option_matrix_row(
            option=o,
            evidence=ev,
            recommendation_status=rec_status if o == primary else ("BLOCKED" if blocking else "INSUFFICIENT_EVIDENCE"),
            missing=[] if analyte else ["MISSING_ANALYTE"],
        )
        for o in (
            "PARENT_DRUG",
            "PARENT_AND_METABOLITE",
            "ACTIVE_METABOLITE",
            "ENDOGENOUS_ANALYTE",
            "EXPERT_DEFINED",
        )
    ]
    d.recommendation = make_recommendation(
        option=primary,
        status=rec_status,
        confidence=conf,
        evidence=ev,
        blocking_conflicts=d.blocking_conflicts,
        missing_codes=[] if analyte else ["MISSING_ANALYTE"],
        rationale=(
            f"Structured facts identify analyte '{analyte}'. "
            "Expert interview suggests parent analyte is typical. "
            "Metabolite measurement was NOT automatically added. "
            "Reference-product dose conflict is non-blocking for ANALYTE_PK when identity is known. "
            "Recommendation ≠ approval."
            if analyte
            else "Insufficient analyte evidence."
        ),
        explanation={
            "blocking_reasons": [b.to_dict() for b in report.blocking_reasons],
            "non_blocking_issues": [b.to_dict() for b in report.non_blocking_issues],
        },
    )
    return _attach(d)
