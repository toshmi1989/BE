"""Conditional evaluation for protocol sections and text blocks."""

from __future__ import annotations

from typing import Any


def _design_type(ctx: dict) -> str | None:
    d = ctx.get("design") or {}
    return d.get("type")


def _food_condition(ctx: dict) -> str | None:
    food = ctx.get("food") or {}
    design = ctx.get("design") or {}
    return food.get("condition") or design.get("food_condition")


def _ref_purchased(ctx: dict) -> str | None:
    ref = ctx.get("reference_product") or {}
    return ref.get("purchased_status")


def eval_condition(name: str, ctx: dict) -> bool:
    """Return True if condition applies to this study context."""
    if name in {"always", "*"}:
        return True
    design = _design_type(ctx)
    food = _food_condition(ctx)
    analytes = ctx.get("analytes") or []
    ref_status = _ref_purchased(ctx)

    mapping: dict[str, bool] = {
        "design_crossover_2x2": design == "CROSSOVER_2X2",
        "design == CROSSOVER_2X2": design == "CROSSOVER_2X2",
        "crossover": design in {"CROSSOVER_2X2", "REPLICATE_2X2X4"},
        "design_replicate": design == "REPLICATE_2X2X4",
        "design == REPLICATE_2X2X4": design == "REPLICATE_2X2X4",
        "design_parallel": design == "PARALLEL",
        "design == PARALLEL": design == "PARALLEL",
        "design_adaptive": design == "ADAPTIVE",
        "design == ADAPTIVE": design == "ADAPTIVE",
        "food_fed": food == "FED",
        "food == FED": food == "FED",
        "food_fasting": food == "FASTING",
        "food == FASTING": food == "FASTING",
        "food_both": food == "FASTING_AND_FED",
        "food == FASTING_AND_FED": food == "FASTING_AND_FED",
        "analyte_count_gt_1": len(analytes) > 1,
        "analyte_count > 1": len(analytes) > 1,
        "reference_not_purchased": ref_status in {"NOT_PURCHASED", "UNKNOWN", None, ""},
        "reference_purchased == false": ref_status != "PURCHASED",
        "has_ai_evidence": bool((ctx.get("evidence_summary") or {}).get("ai_proposed_count")),
    }
    if name not in mapping:
        # Unknown conditions are fail-closed (skip block)
        return False
    return mapping[name]


def conditions_pass(conditions: list[str] | tuple[str, ...], ctx: dict) -> bool:
    if not conditions:
        return True
    return all(eval_condition(c, ctx) for c in conditions)


def build_variable_map(ctx: dict, consistency: dict) -> dict[str, Any]:
    from app.domain.canonical_sampling import get_canonical_sampling_plan
    from app.domain.canonical_subjects import get_canonical_subject_counts
    from app.domain.display_value_registry import resolve_display
    from app.domain.org_render import resolve_sponsor

    design = ctx.get("design") or {}
    food = ctx.get("food") or {}
    sample_size = ctx.get("sample_size") or {}
    study = ctx.get("study") or {}
    product = ctx.get("product") or {}
    reference = ctx.get("reference_product") or {}
    washout = ctx.get("washout") or {}
    selection = ctx.get("cv_selection") or {}
    analytes = ctx.get("analytes") or []
    subjects_c = get_canonical_subject_counts(ctx)
    sampling_c = get_canonical_sampling_plan(ctx)
    sponsor = resolve_sponsor(ctx)
    sponsor_name = (
        (sponsor.get("name") or sponsor.get("legal_name"))
        if sponsor
        else None
    ) or "{{SPONSOR.NAME}}"

    sequences = design.get("sequences") or []
    seq_text = "; ".join(
        "–".join(str(x) for x in (seq if isinstance(seq, (list, tuple)) else [seq]))
        for seq in sequences
    ) or "{{DESIGN.SEQUENCES}}"

    treatments = design.get("treatments") or ["T", "R"]
    treatments_text = ", ".join(str(t) for t in treatments)

    design_code = design.get("type")
    food_code = food.get("condition") or design.get("food_condition")
    meal_code = food.get("meal_type")

    protocol_number = study.get("protocol_number") or "{{STUDY.PROTOCOL_NUMBER}}"
    test_name = product.get("trade_name") or product.get("inn") or "{{TEST_PRODUCT.NAME}}"
    ref_name = reference.get("trade_name") or reference.get("inn") or "{{REFERENCE_PRODUCT.NAME}}"

    # Prefer explicit food fields for golden FED meal description
    calories = food.get("calories")
    fat = food.get("fat_percent")
    dose_after = food.get("dose_after_meal_min")
    water = food.get("water_volume_ml")

    return {
        "protocol_number": protocol_number,
        "sponsor_name": sponsor_name,
        "design_type": resolve_display(design_code, context="design_short", fallback="{{DESIGN.TYPE}}")
        if design_code
        else "{{DESIGN.TYPE}}",
        "design_type_code": design_code or "{{DESIGN.TYPE}}",
        "design_type_full": resolve_display(design_code, context="design", fallback="{{DESIGN.TYPE}}")
        if design_code
        else "{{DESIGN.TYPE}}",
        "periods": design.get("periods") if design.get("periods") is not None else "{{DESIGN.PERIODS}}",
        "sequences_text": seq_text,
        "treatments_text": treatments_text,
        "food_condition": resolve_display(food_code, context="food", fallback="{{FOOD.CONDITION}}")
        if food_code
        else "{{FOOD.CONDITION}}",
        "food_condition_code": food_code or "{{FOOD.CONDITION}}",
        "meal_type": resolve_display(meal_code, context="meal", fallback="{{FOOD.MEAL_TYPE}}")
        if meal_code
        else "{{FOOD.MEAL_TYPE}}",
        "meal_type_code": meal_code or "{{FOOD.MEAL_TYPE}}",
        "food_calories": calories if calories is not None else "{{FOOD.CALORIES}}",
        "food_fat_percent": fat if fat is not None else "{{FOOD.FAT_PERCENT}}",
        "dose_after_meal_min": dose_after if dose_after is not None else "{{FOOD.DOSE_AFTER_MEAL_MIN}}",
        "water_volume_ml": water if water is not None else "{{FOOD.WATER_ML}}",
        "evaluable_n": subjects_c.evaluable_n
        if subjects_c.evaluable_n is not None
        else "{{SUBJECTS.EVALUABLE_N}}",
        "randomized_n": subjects_c.randomized_n
        if subjects_c.randomized_n is not None
        else "{{SUBJECTS.RANDOMIZED_N}}",
        "screened_n": subjects_c.screened_n
        if subjects_c.screened_n is not None
        else "{{SUBJECTS.SCREENED_N}}",
        "dropout_pct": sample_size.get("inputs_snapshot", {}).get("dropout_pct")
        if isinstance(sample_size.get("inputs_snapshot"), dict)
        and sample_size.get("inputs_snapshot", {}).get("dropout_pct") is not None
        else sample_size.get("dropout_pct")
        if sample_size.get("dropout_pct") is not None
        else "{{STATISTICS.DROPOUT_PCT}}",
        "cv_percent": selection.get("selected_cv")
        if selection.get("selected_cv") is not None
        else sample_size.get("selected_cv")
        if sample_size.get("selected_cv") is not None
        else sample_size.get("cv_used")
        if sample_size.get("cv_used") is not None
        else "{{STATISTICS.CV}}",
        "cv_parameter": selection.get("parameter")
        or sample_size.get("parameter")
        or "Cmax",
        "n_points": sampling_c.points_per_period
        if sampling_c.points_per_period
        else "{{SAMPLING.N_POINTS}}",
        "observation_duration": sampling_c.observation_duration
        if sampling_c.observation_duration is not None
        else "{{OBSERVATION.DURATION}}",
        "observation_unit": sampling_c.observation_unit,
        "washout_value": washout.get("selected_value")
        if washout.get("selected_value") is not None
        else "{{WASHOUT.VALUE}}",
        "washout_unit": washout.get("unit") or "day",
        "washout_minimum": washout.get("calculated_minimum")
        if washout.get("calculated_minimum") is not None
        else "{{WASHOUT.MINIMUM}}",
        "test_name": test_name,
        "ref_name": ref_name,
        "purchased_status": resolve_display(
            reference.get("purchased_status"),
            context="purchased_status",
            fallback="{{REFERENCE_PRODUCT.PURCHASED_STATUS}}",
        )
        if reference.get("purchased_status")
        else "{{REFERENCE_PRODUCT.PURCHASED_STATUS}}",
        "analyte_count": len(analytes),
        "analyte_names": ", ".join(a.get("name") or "?" for a in analytes) or "{{ANALYTES.NAMES}}",
        "consistency": consistency,
        "sample_size_evaluable_n": subjects_c.sample_size_evaluable_n,
        "sample_size_randomized_n": subjects_c.sample_size_randomized_n,
    }
