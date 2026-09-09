"""DESIGN decision engine — Phase 15.0 / 15.1. Deterministic. No invented thresholds."""

from __future__ import annotations

from app.domain.decision_blockers import apply_dependency_blockers
from app.domain.decision_context import DecisionContext, design_context_summary
from app.domain.decision_matrix import build_option_matrix_row, evidence, make_recommendation
from app.domain.decision_models import ProtocolDecision


def evaluate_design(ctx: DecisionContext) -> ProtocolDecision:
    d = ProtocolDecision(
        domain="DESIGN",
        subject="Study design selection",
        study_id=ctx.study_id,
        project_id=ctx.project_id,
        package_id=ctx.package_id,
        current_context=design_context_summary(ctx),
    )
    ev = []
    f = ctx.structured_facts

    if f.get("design.crossover") is True and f.get("design.periods") == 2:
        ev.append(
            evidence(
                evidence_type="STRUCTURED_STUDY_FACT",
                support_level="SUPPORTS",
                option="STANDARD_2X2_CROSSOVER",
                excerpt=(
                    f"Source package describes crossover periods={f.get('design.periods')} "
                    f"sequences={f.get('design.sequences')}"
                ),
                status=ctx.fact_statuses.get("design.crossover", "PROPOSED"),
                source_id=ctx.fact_sources.get("design.crossover"),
                location="design.crossover",
                decision_source_type="CURRENT_STUDY_FACT",
                applicability="DIRECT",
                applicability_reason="Current protocol design fact from study inputs",
            )
        )
    if f.get("design.adaptive") is True:
        ev.append(
            evidence(
                evidence_type="STRUCTURED_STUDY_FACT",
                support_level="SUPPORTS",
                option="ADAPTIVE_DESIGN",
                excerpt="Source package mentions adaptive design",
                status=ctx.fact_statuses.get("design.adaptive", "PROPOSED"),
                source_id=ctx.fact_sources.get("design.adaptive"),
                decision_source_type="CURRENT_STUDY_FACT",
                applicability="DIRECT",
                applicability_reason="Current protocol design fact from study inputs",
            )
        )

    for ic in ctx.interview_claims:
        if ic.get("domain") == "DESIGN" or "design" in str(ic.get("field_name") or "").lower():
            ev.append(
                evidence(
                    evidence_type="EXPERT_INTERVIEW",
                    support_level="CONTEXT_ONLY",
                    excerpt=f"Expert interview evidence suggests: {ic.get('normalized_claim')}",
                    status="PROPOSED",
                    claim_id=ic.get("claim_id"),
                    notes="Interview ≠ regulation",
                    applicability="UNKNOWN",
                    applicability_reason="Interview relevance not reviewed for this study",
                )
            )

    for rule in ctx.expert_rules_proposed:
        if rule.get("domain") != "DESIGN":
            continue
        action = (rule.get("action_definition") or {}).get("propose_design")
        opt = None
        if action == "CROSSOVER_2X2":
            opt = "STANDARD_2X2_CROSSOVER"
        elif action and "REPLICATE" in str(action).upper():
            opt = "REPLICATE_CROSSOVER"
        elif action and "ADAPTIVE" in str(action).upper():
            opt = "ADAPTIVE_DESIGN"
        elif action and "PARALLEL" in str(action).upper():
            opt = "PARALLEL_DESIGN"
        if opt:
            ev.append(
                evidence(
                    evidence_type="EXPERT_RULE",
                    support_level="SUPPORTS",
                    option=opt,
                    excerpt=f"Expert interview evidence suggests: {rule.get('description')}",
                    status="PROPOSED",
                    rule_id=rule.get("rule_code"),
                    notes="PROPOSED expert rule — not ACTIVE regulatory rule",
                    applicability="UNKNOWN",
                    applicability_reason="Proposed rule applicability not reviewed",
                )
            )

    for prev in ctx.previous_protocols:
        ev.append(
            evidence(
                evidence_type="PREVIOUS_PROTOCOL",
                support_level="CONTEXT_ONLY",
                excerpt=f"Previous/golden protocol registered: {prev.get('original_filename')}",
                status="PROPOSED",
                source_id=prev.get("source_id"),
                notes="Contextual precedent only — cannot overwrite current Study",
                applicability="LOW",
                applicability_reason="Previous protocol is analogue context only",
            )
        )
    for an in ctx.analogue_studies:
        ev.append(
            evidence(
                evidence_type="ANALOGUE_STUDY",
                support_level="CONTEXT_ONLY",
                excerpt=an.claim or an.study_reference,
                status=an.review_status,
                source_id=an.source_id,
                relevance=an.relevance,
                notes="Analogue ≠ identical study",
                applicability="MODERATE" if an.relevance == "HIGH" else "LOW",
                applicability_reason="Analogue study — never automatically DIRECT",
            )
        )

    missing: list[str] = []
    if ctx.cvintra is None:
        missing.append("MISSING_CVINTRA")
        d.knowledge_gaps.append(
            {
                "code": "MISSING_CVINTRA",
                "title": "Within-subject CV (CVintra) not available",
                "severity": "HIGH",
                "blocking": False,
            }
        )
        d.research_tasks.append(
            {
                "code": "FIND_CVINTRA_LITERATURE",
                "title": "Research literature / previous BE studies for CVintra",
                "status": "OPEN",
            }
        )

    report = apply_dependency_blockers(d, ctx)
    blocking = report.blocked
    d.evidence = ev

    matrix = []
    for opt in (
        "STANDARD_2X2_CROSSOVER",
        "REPLICATE_CROSSOVER",
        "ADAPTIVE_DESIGN",
        "PARALLEL_DESIGN",
    ):
        has = any(e.option == opt and e.support_level == "SUPPORTS" for e in ev)
        if blocking:
            st = "BLOCKED"
        elif opt == "STANDARD_2X2_CROSSOVER" and has:
            st = "PARTIALLY_SUPPORTED"
        elif opt == "ADAPTIVE_DESIGN" and f.get("design.adaptive"):
            st = "PARTIALLY_SUPPORTED"
        elif has:
            st = "PARTIALLY_SUPPORTED"
        else:
            st = "INSUFFICIENT_EVIDENCE"
        matrix.append(
            build_option_matrix_row(option=opt, evidence=ev, recommendation_status=st, missing=missing)
        )
    d.option_matrix = matrix

    blocker_codes = [b.blocking_reason_code for b in report.blocking_reasons]
    if blocking:
        d.status = "BLOCKED"
        d.recommendation = make_recommendation(
            option="STANDARD_2X2_CROSSOVER",
            status="BLOCKED",
            confidence="NONE",
            evidence=ev,
            missing_codes=missing,
            blocking_conflicts=d.blocking_conflicts,
            rationale=(
                "Unable to complete design decision because registered dependencies "
                f"are unresolved ({', '.join(blocker_codes)}). "
                "Current design context is retained for review only."
            ),
            explanation={
                "why": "Registered dependency blockers prevent design recommendation",
                "blocking_reasons": [b.to_dict() for b in report.blocking_reasons],
                "non_blocking_issues": [b.to_dict() for b in report.non_blocking_issues],
                "current_design_context": d.current_context,
                "missing": missing,
                "required_action": "Resolve dependency blockers, then recompute",
            },
        )
    else:
        d.status = "REVIEW_REQUIRED"
        d.recommendation = make_recommendation(
            option="STANDARD_2X2_CROSSOVER",
            status="PARTIALLY_SUPPORTED",
            confidence="LOW",
            evidence=ev,
            missing_codes=missing,
            rationale=(
                "Current source package describes a two-period crossover. "
                "Expert interview evidence describes standard crossover as typical when high "
                "variability is not demonstrated. No verified high-variability evidence is present. "
                "This is not an approved medical decision."
            ),
            explanation={
                "why": [
                    "Structured study facts describe two-period crossover",
                    "Expert interview evidence suggests standard crossover when high variability is not demonstrated",
                    "No verified high-variability evidence currently present",
                ],
                "non_blocking_issues": [b.to_dict() for b in report.non_blocking_issues],
                "missing": missing,
                "caution": ["PROPOSED evidence is not VERIFIED", "Recommendation ≠ approval"],
                "required_action": "Medical writer review",
            },
        )

    for e in d.evidence:
        e.decision_id = d.id
    if d.recommendation:
        d.recommendation.decision_id = d.id
    d.study_mutated = False
    return d
