"""Project-level Validation Engine — graph-aware, no LLM, no frontend logic."""

from __future__ import annotations

from typing import Any

from app.domain.constants import (
    CROSSOVER_2X2_REQUIRED_PERIODS,
    CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT,
    PARALLEL_REQUIRED_PERIODS,
)
from app.domain.design_validation import validate_design_payload
from app.domain.exceptions import ValidationError
from app.domain.food_validation import validate_food_payload
from app.domain.sampling import AnalyteTmaxWindow, validate_sampling_plan
from app.domain.subject_plan import SubjectPlanValues, validate_subject_plan
from app.domain.validation_types import IssueDraft


def _issue(**kwargs: Any) -> IssueDraft:
    return IssueDraft(**kwargs)


def validate_study(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    study = ctx.get("study")
    if not study:
        issues.append(
            _issue(
                category="study",
                severity="ERROR",
                rule_id="VAL.STUDY.MISSING.v1",
                message="Study entity missing",
                entity_type="Study",
            )
        )
        return issues
    if not study.get("protocol_number"):
        issues.append(
            _issue(
                category="study",
                severity="WARNING",
                rule_id="VAL.STUDY.PROTOCOL_NUMBER.v1",
                message="protocol_number not set",
                entity_type="Study",
                entity_id=str(study.get("id")) if study.get("id") else None,
                field="protocol_number",
            )
        )
    return issues


def validate_design(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    design = ctx.get("design")
    if not design:
        issues.append(
            _issue(
                category="design",
                severity="ERROR",
                rule_id="VAL.DESIGN.MISSING.v1",
                message="Design not configured",
                entity_type="Design",
            )
        )
        return issues
    dtype = design.get("type")
    periods = design.get("periods")
    sequences = design.get("sequences") or []
    if periods is None:
        issues.append(
            _issue(
                category="design",
                severity="ERROR",
                rule_id="VAL.DESIGN.PERIODS_MISSING.v1",
                message="Design periods missing",
                entity_type="Design",
                entity_id=str(design.get("id")) if design.get("id") else None,
                field="periods",
            )
        )
    try:
        validate_design_payload(
            design_type=str(dtype),
            periods=periods,
            sequences=sequences,
            treatments=design.get("treatments"),
            stage_configuration=design.get("stage_configuration"),
        )
    except ValidationError as exc:
        issues.append(
            _issue(
                category="design",
                severity="ERROR",
                rule_id="VAL.DESIGN.STRUCTURE.v1",
                message=exc.message,
                entity_type="Design",
                entity_id=str(design.get("id")) if design.get("id") else None,
                field=exc.field,
                details=exc.details,
            )
        )
    # Explicit DESIGN ↔ PERIODS / SEQUENCES rules (also covered above)
    if dtype == "CROSSOVER_2X2" and periods is not None and periods != CROSSOVER_2X2_REQUIRED_PERIODS:
        issues.append(
            _issue(
                category="design",
                severity="ERROR",
                rule_id="VAL.DESIGN.2X2_PERIODS.v1",
                message=f"CROSSOVER_2X2 requires periods={CROSSOVER_2X2_REQUIRED_PERIODS}",
                entity_type="Design",
                field="periods",
            )
        )
    if dtype == "PARALLEL" and periods is not None and periods != PARALLEL_REQUIRED_PERIODS:
        issues.append(
            _issue(
                category="design",
                severity="ERROR",
                rule_id="VAL.DESIGN.PARALLEL_PERIODS.v1",
                message=f"PARALLEL requires periods={PARALLEL_REQUIRED_PERIODS}",
                entity_type="Design",
                field="periods",
            )
        )
    if dtype == "CROSSOVER_2X2" and len(sequences) != CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT:
        issues.append(
            _issue(
                category="design",
                severity="ERROR",
                rule_id="VAL.DESIGN.2X2_SEQUENCES.v1",
                message="CROSSOVER_2X2 requires two sequences",
                entity_type="Design",
                field="sequences",
            )
        )
    return issues


def validate_food(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    design = ctx.get("design") or {}
    food = ctx.get("food")
    food_condition = (food or {}).get("condition") or design.get("food_condition")
    if food_condition == "FED":
        if not food:
            issues.append(
                _issue(
                    category="food",
                    severity="ERROR",
                    rule_id="VAL.FOOD.FED_MISSING.v1",
                    message="FED design requires food configuration",
                    entity_type="FoodCondition",
                    field="condition",
                )
            )
        else:
            try:
                validate_food_payload(
                    condition=food.get("condition"),
                    meal_type=food.get("meal_type"),
                    calories=food.get("calories"),
                    fat_percent=food.get("fat_percent"),
                )
            except ValidationError as exc:
                issues.append(
                    _issue(
                        category="food",
                        severity="ERROR",
                        rule_id="VAL.FOOD.STRUCTURE.v1",
                        message=exc.message,
                        entity_type="FoodCondition",
                        entity_id=str(food.get("id")) if food.get("id") else None,
                        field=exc.field,
                        details=exc.details,
                    )
                )
            if not food.get("meal_type"):
                issues.append(
                    _issue(
                        category="food",
                        severity="ERROR",
                        rule_id="VAL.FOOD.FED_MEAL.v1",
                        message="FED requires meal_type configuration",
                        entity_type="FoodCondition",
                        field="meal_type",
                    )
                )
    elif food_condition == "FASTING":
        # meal configuration not required
        if food and food.get("meal_type") and food.get("meal_type") not in {None, "CUSTOM"}:
            issues.append(
                _issue(
                    category="food",
                    severity="INFO",
                    rule_id="VAL.FOOD.FASTING_MEAL_NOTE.v1",
                    message="FASTING typically does not require meal configuration",
                    entity_type="FoodCondition",
                    field="meal_type",
                    blocking=False,
                )
            )
    elif not food and not food_condition:
        issues.append(
            _issue(
                category="food",
                severity="WARNING",
                rule_id="VAL.FOOD.MISSING.v1",
                message="Food condition not configured",
                entity_type="FoodCondition",
            )
        )
    return issues


def validate_subjects(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    subjects = ctx.get("subjects")
    if not subjects:
        issues.append(
            _issue(
                category="subjects",
                severity="WARNING",
                rule_id="VAL.SUBJECTS.MISSING.v1",
                message="Subject plan not configured",
                entity_type="SubjectPlan",
            )
        )
        return issues
    try:
        validate_subject_plan(
            SubjectPlanValues(
                target_evaluable_n=subjects.get("target_evaluable_n"),
                planned_randomized_n=subjects.get("planned_randomized_n"),
                reserve_n=subjects.get("reserve_n"),
                planned_screened_n=subjects.get("planned_screened_n"),
            )
        )
    except ValidationError as exc:
        issues.append(
            _issue(
                category="subjects",
                severity="ERROR",
                rule_id="VAL.SUBJECTS.STRUCTURE.v1",
                message=exc.message,
                entity_type="SubjectPlan",
                field=exc.field,
                details=exc.details,
            )
        )
    return issues


def validate_eligibility(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    eligibility = ctx.get("eligibility") or {}
    inclusion = eligibility.get("inclusion") or []
    if not inclusion:
        issues.append(
            _issue(
                category="eligibility",
                severity="WARNING",
                rule_id="VAL.ELIG.INCLUSION.v1",
                message="No inclusion criteria defined",
                entity_type="Eligibility",
            )
        )
    return issues


def validate_analytes(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    analytes = ctx.get("analytes") or []
    if not analytes:
        issues.append(
            _issue(
                category="analytes",
                severity="ERROR",
                rule_id="VAL.ANALYTE.MISSING.v1",
                message="No analytes configured",
                entity_type="Analyte",
            )
        )
        return issues
    for a in analytes:
        if a.get("active") is False:
            continue
        if a.get("tmax_min") is None or a.get("tmax_max") is None:
            issues.append(
                _issue(
                    category="analytes",
                    severity="ERROR",
                    rule_id="VAL.ANALYTE.TMAX.v1",
                    message=f"Analyte {a.get('name')} missing Tmax range",
                    entity_type="Analyte",
                    entity_id=str(a.get("id")) if a.get("id") else None,
                    field="tmax",
                )
            )
    return issues


def validate_pk(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    analytes = [a for a in (ctx.get("analytes") or []) if a.get("active") is not False]
    pk_params = ctx.get("pk_parameters") or []
    by_analyte: dict[str, set[str]] = {}
    for p in pk_params:
        aid = str(p.get("analyte_id"))
        by_analyte.setdefault(aid, set()).add(str(p.get("parameter_code")))
    for a in analytes:
        aid = str(a.get("id"))
        codes = by_analyte.get(aid, set())
        if "Tmax" not in codes and (a.get("tmax_min") is None):
            status = a.get("status")
            if status == "NEEDS_REVIEW":
                issues.append(
                    _issue(
                        category="pk",
                        severity="WARNING",
                        rule_id="VAL.PK.TMAX_NEEDS_REVIEW.v1",
                        message=f"Analyte {a.get('name')} PK/Tmax marked NEEDS_REVIEW",
                        entity_type="Analyte",
                        entity_id=aid,
                        field="Tmax",
                    )
                )
            else:
                issues.append(
                    _issue(
                        category="pk",
                        severity="ERROR",
                        rule_id="VAL.PK.TMAX_MISSING.v1",
                        message=f"Analyte {a.get('name')} lacks Tmax PK parameter or range",
                        entity_type="Analyte",
                        entity_id=aid,
                        field="Tmax",
                    )
                )
    return issues


def validate_washout(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    design = ctx.get("design") or {}
    dtype = design.get("type")
    washout = ctx.get("washout")
    if dtype == "PARALLEL":
        if washout and washout.get("requires_washout"):
            issues.append(
                _issue(
                    category="washout",
                    severity="WARNING",
                    rule_id="VAL.WASHOUT.PARALLEL.v1",
                    message="Parallel design should not require washout",
                    entity_type="WashoutPlan",
                )
            )
        return issues
    if dtype in {"CROSSOVER_2X2", "REPLICATE_2X2X4"}:
        if not washout:
            issues.append(
                _issue(
                    category="washout",
                    severity="ERROR",
                    rule_id="VAL.WASHOUT.MISSING.v1",
                    message="Crossover/replicate design requires washout plan",
                    entity_type="WashoutPlan",
                )
            )
        elif washout.get("issues"):
            critical = [
                i
                for i in (washout.get("issues") or [])
                if isinstance(i, dict) and i.get("severity") == "CRITICAL"
            ]
            if critical:
                issues.append(
                    _issue(
                        category="washout",
                        severity="CRITICAL",
                        rule_id="VAL.WASHOUT.CRITICAL.v1",
                        message="Washout plan has critical issues",
                        entity_type="WashoutPlan",
                        entity_id=str(washout.get("id")) if washout.get("id") else None,
                        details={"critical_issues": critical},
                    )
                )
        if washout and washout.get("manual_override"):
            issues.append(
                _issue(
                    category="washout",
                    severity="INFO",
                    rule_id="VAL.WASHOUT.MANUAL.v1",
                    message="Washout uses manual override — verify before generation",
                    entity_type="WashoutPlan",
                    blocking=False,
                )
            )
    return issues


def validate_observation(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    observation = ctx.get("observation")
    if not observation:
        issues.append(
            _issue(
                category="observation",
                severity="ERROR",
                rule_id="VAL.OBS.MISSING.v1",
                message="Observation plan missing",
                entity_type="ObservationPlan",
            )
        )
    return issues


def validate_sampling(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    sampling = ctx.get("sampling")
    if not sampling:
        issues.append(
            _issue(
                category="sampling",
                severity="ERROR",
                rule_id="VAL.SAMP.MISSING.v1",
                message="Sampling plan missing",
                entity_type="SamplingPlan",
            )
        )
        return issues
    points = sampling.get("points") or []
    observation = ctx.get("observation") or {}
    obs_h = observation.get("selected_duration") or observation.get("final_sampling_time")
    windows: list[AnalyteTmaxWindow] = []
    for a in ctx.get("analytes") or []:
        if a.get("active") is False:
            continue
        if a.get("tmax_min") is None or a.get("tmax_max") is None:
            continue
        windows.append(
            AnalyteTmaxWindow(
                analyte_id=str(a.get("id") or a.get("name")),
                name=str(a.get("name")),
                tmax_min=float(a["tmax_min"]),
                tmax_max=float(a["tmax_max"]),
                tmax_unit=str(a.get("tmax_unit") or "h"),
            )
        )
    design = ctx.get("design") or {}
    point_dicts = [
        {"time_h": p.get("time_h"), "reason": p.get("reason")} for p in points
    ]
    for si in validate_sampling_plan(
        point_dicts,
        observation_duration_h=float(obs_h) if obs_h is not None else None,
        analyte_windows=windows or None,
        design_type=design.get("type"),
        manual_override=bool(sampling.get("manual_override")),
    ):
        issues.append(
            _issue(
                category="sampling",
                severity=si.severity,
                rule_id=f"VAL.SAMP.{si.code}.v1",
                message=si.message,
                entity_type="SamplingPlan",
                entity_id=str(sampling.get("id")) if sampling.get("id") else None,
                field=si.field,
            )
        )
    if sampling.get("manual_override"):
        issues.append(
            _issue(
                category="sampling",
                severity="INFO",
                rule_id="VAL.SAMP.MANUAL.v1",
                message="Sampling uses manual override",
                entity_type="SamplingPlan",
                blocking=False,
            )
        )
    return issues


def validate_blood_volume(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    sampling = ctx.get("sampling")
    blood = ctx.get("blood_volume")
    if not sampling:
        return issues
    if not blood:
        issues.append(
            _issue(
                category="blood_volume",
                severity="ERROR",
                rule_id="VAL.BLOOD.MISSING.v1",
                message="Blood volume not calculated after sampling plan",
                entity_type="BloodVolumeCalculation",
            )
        )
        return issues
    expected_points = sampling.get("total_points_per_period")
    if expected_points is None:
        expected_points = len(sampling.get("points") or [])
    stored = blood.get("sampling_points_per_period")
    if stored is not None and expected_points is not None and int(stored) != int(expected_points):
        issues.append(
            _issue(
                category="blood_volume",
                severity="ERROR",
                rule_id="VAL.BLOOD.STALE.v1",
                message="Blood volume sampling_points_per_period inconsistent with sampling plan",
                entity_type="BloodVolumeCalculation",
                field="sampling_points_per_period",
                details={"stored": stored, "expected": expected_points},
            )
        )
    return issues


def validate_statistics(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    selection = ctx.get("cv_selection")
    sample_size = ctx.get("sample_size")
    if sample_size and selection is None:
        issues.append(
            _issue(
                category="statistics",
                severity="ERROR",
                rule_id="VAL.STAT.NO_CV.v1",
                message="Sample size present but selected CV missing",
                entity_type="CVSelection",
            )
        )
    if selection is None or selection.get("selected_cv") is None:
        issues.append(
            _issue(
                category="statistics",
                severity="ERROR",
                rule_id="VAL.STAT.CV_MISSING.v1",
                message="Selected CV required for sample-size dependent planning",
                entity_type="CVSelection",
            )
        )
    else:
        status = selection.get("status") or (selection.get("provenance") or {}).get("status")
        if status in {"REJECTED", "MISSING"}:
            issues.append(
                _issue(
                    category="statistics",
                    severity="ERROR",
                    rule_id="VAL.STAT.CV_STATUS.v1",
                    message=f"Selected CV status={status} is not usable",
                    entity_type="CVSelection",
                    field="status",
                )
            )
        elif status == "NEEDS_REVIEW":
            issues.append(
                _issue(
                    category="statistics",
                    severity="WARNING",
                    rule_id="VAL.STAT.CV_REVIEW.v1",
                    message="Selected CV needs review",
                    entity_type="CVSelection",
                    field="status",
                )
            )
        if status == "VERIFIED":
            evidence_ok = False
            for cv in ctx.get("cv_studies") or []:
                if cv.get("evidence"):
                    evidence_ok = True
                    break
            if not evidence_ok and not (selection.get("source_study_ids") or []):
                issues.append(
                    _issue(
                        category="statistics",
                        severity="ERROR",
                        rule_id="VAL.STAT.CV_EVIDENCE.v1",
                        message="VERIFIED CV must have source evidence",
                        entity_type="CVSelection",
                    )
                )
    if not sample_size:
        issues.append(
            _issue(
                category="statistics",
                severity="WARNING",
                rule_id="VAL.STAT.SAMPLE_SIZE_MISSING.v1",
                message="No sample size calculation stored",
                entity_type="SampleSizeCalculation",
            )
        )
    return issues


def validate_cross_dependencies(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []

    # REFERENCE ↔ SOURCE
    reference = ctx.get("reference_product")
    if not reference:
        issues.append(
            _issue(
                category="reference",
                severity="CRITICAL",
                rule_id="VAL.REF.MISSING.v1",
                message="Reference product missing",
                entity_type="ReferenceProduct",
            )
        )
    else:
        ref_status = reference.get("status") or (reference.get("provenance") or {}).get("status")
        if ref_status == "VERIFIED":
            source_ids = reference.get("source_ids") or (reference.get("provenance") or {}).get(
                "source_ids"
            ) or []
            if not source_ids:
                issues.append(
                    _issue(
                        category="reference",
                        severity="CRITICAL",
                        rule_id="VAL.REF.VERIFIED_NO_SOURCE.v1",
                        message="VERIFIED reference must have source evidence",
                        entity_type="ReferenceProduct",
                        entity_id=str(reference.get("id")) if reference.get("id") else None,
                        field="source_ids",
                    )
                )

    # SUBJECTS ↔ STATISTICS N ordering + canonical divergence
    from app.domain.canonical_subjects import get_canonical_subject_counts

    subjects_c = get_canonical_subject_counts(ctx)
    if subjects_c.diverges_from_sample_size:
        issues.append(
            _issue(
                category="subjects",
                severity="ERROR",
                rule_id="VAL.N.SUBJECTPLAN_SAMPLESIZE_DIVERGENCE.v1",
                message=(
                    "SubjectPlan N diverges from SampleSizeCalculation — "
                    "SubjectPlan is canonical; accept/sync calculation or update SubjectPlan"
                ),
                entity_type="SubjectPlan",
                field="N",
                details=subjects_c.to_dict(),
            )
        )

    evaluable = subjects_c.evaluable_n
    randomized = subjects_c.randomized_n
    screened = subjects_c.screened_n

    vals = [evaluable, randomized, screened]
    if all(v is not None for v in vals):
        if not (evaluable <= randomized <= screened):
            issues.append(
                _issue(
                    category="subjects",
                    severity="ERROR",
                    rule_id="VAL.N.ORDER.v1",
                    message="Require evaluable_n <= randomized_n <= screened_n",
                    entity_type="SubjectPlan",
                    field="N",
                    details={
                        "evaluable_n": evaluable,
                        "randomized_n": randomized,
                        "screened_n": screened,
                    },
                )
            )

    # DESIGN ↔ FOOD already in validate_food; DESIGN ↔ WASHOUT in validate_washout
    return issues


def validate_administration(ctx: dict) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    sponsor = ctx.get("sponsor") or {}
    has_sponsor = bool(sponsor.get("name") or sponsor.get("legal_name"))
    if not has_sponsor:
        orgs = ctx.get("organizations") or []
        has_sponsor = any(str(o.get("role") or "").upper() == "SPONSOR" and o.get("name") for o in orgs)
    if not has_sponsor:
        issues.append(
            _issue(
                category="administration",
                severity="ERROR",
                rule_id="VAL.ADMIN.SPONSOR_MISSING.v1",
                message="Sponsor not configured",
                entity_type="Sponsor",
                field="name",
                blocking=True,
            )
        )

    inv_people = ctx.get("persons") or []
    has_investigator = any(
        str(p.get("role") or "").upper() in {"INVESTIGATOR", "PRINCIPAL_INVESTIGATOR"} for p in inv_people
    )
    if not has_investigator:
        orgs = ctx.get("organizations") or []
        has_investigator = any(
            str(o.get("role") or "").upper() in {"INVESTIGATOR", "PRINCIPAL_INVESTIGATOR", "CLINICAL_SITE"}
            and o.get("name")
            for o in orgs
        )
    if not has_investigator:
        issues.append(
            _issue(
                category="administration",
                severity="WARNING",
                rule_id="VAL.ADMIN.INVESTIGATOR_MISSING.v1",
                message="Principal investigator / site not configured",
                entity_type="Person",
                field="role",
            )
        )

    labs = [
        o
        for o in (ctx.get("organizations") or [])
        if str(o.get("role") or "").upper() in {"BIOANALYTICAL_LAB", "ANALYTICAL_LAB", "LABORATORY"}
    ]
    if not labs:
        issues.append(
            _issue(
                category="administration",
                severity="WARNING",
                rule_id="VAL.ADMIN.LAB_MISSING.v1",
                message="Bioanalytical laboratory not configured",
                entity_type="Organization",
                field="role",
            )
        )

    admin = ctx.get("study_administration") or {}
    has_insurance = bool(admin.get("insurance_provider") or admin.get("insurance_details")) or any(
        str(o.get("role") or "").upper() == "INSURANCE" for o in (ctx.get("organizations") or [])
    )
    if not has_insurance:
        issues.append(
            _issue(
                category="administration",
                severity="WARNING",
                rule_id="VAL.ADMIN.INSURANCE_MISSING.v1",
                message="Insurance details not configured",
                entity_type="StudyAdministration",
                field="insurance_provider",
            )
        )
    return issues


def validate_knowledge_gaps(ctx: dict) -> list[IssueDraft]:
    """Open CRITICAL / blocking KnowledgeGaps block REVIEW/FINAL readiness.

    LOW/MEDIUM open gaps are not auto-blocking (accepted limitation — no INFO spam).
    """
    issues: list[IssueDraft] = []
    for g in ctx.get("knowledge_gaps") or []:
        if str(g.get("status") or "OPEN").upper() != "OPEN":
            continue
        importance = str(g.get("importance") or "").upper()
        blocking = bool(g.get("blocking")) or importance == "CRITICAL"
        if not blocking and importance != "CRITICAL":
            continue
        issues.append(
            _issue(
                category="knowledge",
                severity="CRITICAL" if importance == "CRITICAL" else "ERROR",
                rule_id="VAL.KNOWLEDGE.GAP_OPEN.v1",
                message=str(g.get("question") or "Open knowledge gap"),
                entity_type="KnowledgeGap",
                entity_id=str(g.get("id")) if g.get("id") else None,
                field="status",
                blocking=True,
                details={"domain": g.get("domain"), "importance": importance},
            )
        )
    return issues


def validate_knowledge_rules(ctx: dict) -> list[IssueDraft]:
    """VERIFIED rules without provenance are ERROR (not auto-fixed)."""
    from app.domain.knowledge_transitions import has_verified_provenance

    issues: list[IssueDraft] = []
    for r in ctx.get("knowledge_rules") or []:
        if str(r.get("status") or "").upper() != "VERIFIED":
            continue
        if has_verified_provenance(
            regulatory_basis_id=r.get("regulatory_basis_id"),
            evidence_claim_ids=list(r.get("evidence_claim_ids") or []),
            source_ids=list(r.get("source_ids") or []),
        ):
            continue
        issues.append(
            _issue(
                category="knowledge",
                severity="ERROR",
                rule_id="VAL.KNOWLEDGE.VERIFIED_WITHOUT_PROVENANCE.v1",
                message=f"VERIFIED rule {r.get('rule_code')} lacks regulatory basis / evidence / sources",
                entity_type="KnowledgeRule",
                entity_id=str(r.get("id")) if r.get("id") else None,
                field="status",
                blocking=True,
                details={"rule_code": r.get("rule_code")},
            )
        )
    return issues


def validate_project(ctx: dict) -> list[IssueDraft]:
    """Full project validation in graph-stable category order."""
    collectors = [
        validate_study,
        validate_cross_dependencies,
        validate_design,
        validate_food,
        validate_eligibility,
        validate_analytes,
        validate_pk,
        validate_washout,
        validate_observation,
        validate_sampling,
        validate_blood_volume,
        validate_statistics,
        validate_subjects,
        validate_administration,
        validate_knowledge_gaps,
        validate_knowledge_rules,
    ]
    all_issues: list[IssueDraft] = []
    for fn in collectors:
        all_issues.extend(fn(ctx))
    # Deduplicate by rule_id+entity+field+message
    seen: set[tuple] = set()
    unique: list[IssueDraft] = []
    for issue in all_issues:
        key = (issue.rule_id, issue.entity_type, issue.entity_id, issue.field, issue.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return unique
