"""Deterministic Protocol Assembly Engine — no DOCX rendering."""

from __future__ import annotations

import re
from typing import Any, Callable

from app.domain.protocol_conditions import build_variable_map, conditions_pass
from app.domain.protocol_consistency import (
    find_unresolved_markers,
    scan_forbidden_placeholders,
    validate_protocol_consistency,
)
from app.domain.canonical_consistency import validate_canonical_consistency
from app.domain.display_value_registry import resolve_display
from app.domain.protocol_constants import (
    FORBIDDEN_PLACEHOLDER_TOKENS,
    PROTOCOL_GENERATOR_VERSION,
    PROTOCOL_SCHEMA_VERSION,
    PROTOCOL_TEMPLATE_VERSION,
)
from app.domain.protocol_generators_p0 import P0_GENERATORS
from app.domain.protocol_generators_p1 import P1_GENERATORS
from app.domain.protocol_generators_12b1 import CORE_12B1_GENERATORS
from app.domain.protocol_generators_12b2 import CORE_12B2_GENERATORS
from app.domain.protocol_generators_12b3 import CORE_12B3_GENERATORS
from app.domain.protocol_generators_12b4 import CORE_12B4_GENERATORS
from app.domain.protocol_sections import SECTION_TREE, SectionDef
from app.domain.protocol_tables import build_tables
from app.domain.protocol_text_blocks import TEXT_BLOCKS, TextBlockDef
from app.domain.reference_registry import build_reference_registry
from app.domain.study_snapshot import build_canonical_snapshot, build_consistency_snapshot
from app.domain.table_registry import apply_table_numbers_to_tables, build_table_registry
from app.domain.validation_types import IssueDraft


def _fmt(template: str, variables: dict[str, Any]) -> str:
    class _Safe(dict):
        def __missing__(self, key: str) -> str:
            return "{{" + key.upper().replace(" ", "_") + "}}"

    try:
        return template.format_map(_Safe(**{k: variables.get(k, f"{{{{{k.upper()}}}}}") for k in re.findall(r"\{(\w+)\}", template)} | variables))
    except Exception:
        return template


def _block(
    *,
    type_: str,
    block_code: str | None = None,
    text: str | None = None,
    items: list | None = None,
    table_key: str | None = None,
    origin: str | None = None,
    rule_id: str | None = None,
    source_ids: list | None = None,
    unresolved: list | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    display_text: str | None = None,
) -> dict:
    unresolved = unresolved or (find_unresolved_markers(text) if text else [])
    return {
        "type": type_,
        "block_code": block_code,
        "text": text,
        "items": items or [],
        "table_key": table_key,
        "origin": origin,
        "rule_id": rule_id,
        "source_ids": source_ids or [],
        "unresolved": unresolved,
        "target_type": target_type,
        "target_id": target_id,
        "display_text": display_text,
    }


def _render_text_block(block: TextBlockDef, variables: dict[str, Any], ctx: dict) -> dict | None:
    if not conditions_pass(block.conditions, ctx):
        return None
    text = _fmt(block.text_template, variables)
    forbad = scan_forbidden_placeholders(text)
    if forbad:
        text = re.sub(
            r"(?i)\b(хх|xxx|примерно|tbd)\b",
            "{{UNRESOLVED}}",
            text,
        )
    return _block(
        type_="TEXT",
        block_code=block.block_code,
        text=text,
        origin="RULE_DERIVED",
        rule_id=f"TEXTBLOCK.{block.block_code}.{block.version}",
        source_ids=list(block.source_ids),
        unresolved=find_unresolved_markers(text),
    )


def _missing_required(section: SectionDef, ctx: dict) -> list[str]:
    missing: list[str] = []
    for key in section.required_data:
        val = ctx.get(key)
        if val is None:
            missing.append(key)
        elif isinstance(val, (list, dict)) and not val:
            # empty eligibility categories handled per-generator
            if key in {"eligibility"}:
                continue
            if key in {"analytes", "pk_parameters", "sampling", "sources"} and not val:
                missing.append(key)
        elif key == "sampling" and isinstance(val, dict) and not (val.get("points") or []):
            missing.append("sampling.points")
        elif key == "sample_size" and not val:
            missing.append(key)
    return missing


GeneratorFn = Callable[[SectionDef, dict, dict, dict], tuple[list[dict], list[str], list[str]]]


def _gen_heading(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return [_block(type_="TEXT", text=section.title, origin="TEMPLATE")], [], []


def _gen_synopsis(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks: list[dict] = []
    tb = TEXT_BLOCKS["SYNOPSIS_CORE"]
    rendered = _render_text_block(tb, variables, ctx)
    if rendered:
        blocks.append(rendered)
    blocks.append(_block(type_="TABLE", table_key="STUDY_METADATA"))
    blocks.append(_block(type_="TABLE", table_key="SYNOPSIS_N"))
    blocks.append(
        _block(
            type_="REFERENCE",
            target_type="section",
            target_id="4.2",
            display_text="см. раздел 4.2",
        )
    )
    sources = []
    for entity in (ctx.get("product"), ctx.get("reference_product"), ctx.get("design")):
        if isinstance(entity, dict):
            sources.extend(str(x) for x in (entity.get("source_ids") or []))
    return blocks, sources, find_unresolved_markers(blocks)


def _gen_protocol_metadata(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    study = ctx.get("study") or {}
    items = [
        f"Protocol number: {study.get('protocol_number') or '{{STUDY.PROTOCOL_NUMBER}}'}",
        f"Version: {study.get('version') or '{{STUDY.VERSION}}'}",
        f"Title: {study.get('title') or study.get('short_title') or '{{STUDY.TITLE}}'}",
        f"Country: {study.get('country') or '{{STUDY.COUNTRY}}'}",
    ]
    return [
        _block(type_="NUMBERED_LIST", items=items, origin="SOURCE_DERIVED", source_ids=list(study.get("source_ids") or []) if isinstance(study.get("source_ids"), list) else [])
    ], list(study.get("source_ids") or []) if isinstance(study.get("source_ids"), list) else [], find_unresolved_markers(items)


def _gen_sponsor(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return P0_GENERATORS["sponsor"](section, ctx, variables, consistency)


def _gen_unresolved_org(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    # Fallback for financing etc.
    marker = f"{{{{{section.template_key}.DETAILS}}}}"
    blocks = [
        _block(type_="TEXT", text=marker, unresolved=[marker], origin="TEMPLATE"),
    ]
    return blocks, [], [marker]


def _gen_signatures(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return P0_GENERATORS["signatures"](section, ctx, variables, consistency)


def _gen_test_product(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    p = ctx.get("product") or {}
    if not p:
        return [
            _block(type_="TEXT", text="{{TEST_PRODUCT.MISSING}}", unresolved=["{{TEST_PRODUCT.MISSING}}"])
        ], [], ["{{TEST_PRODUCT.MISSING}}"]
    text = (
        f"Тестовый препарат: {p.get('trade_name') or p.get('inn') or '{{TEST_PRODUCT.NAME}}'}, "
        f"доза {p.get('dosage') or '{{TEST_PRODUCT.DOSAGE}}'}, "
        f"форма {p.get('dosage_form') or '{{TEST_PRODUCT.DOSAGE_FORM}}'}."
    )
    src = list(p.get("source_ids") or []) if isinstance(p.get("source_ids"), list) else []
    return [
        _block(type_="TEXT", text=text, origin="SOURCE_DERIVED", source_ids=src),
        _block(type_="TABLE", table_key="TEST_PRODUCT"),
    ], src, find_unresolved_markers(text)


def _gen_reference_product(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    r = ctx.get("reference_product") or {}
    if not r:
        return [
            _block(
                type_="TEXT",
                text="{{REFERENCE_PRODUCT.MISSING}}",
                unresolved=["{{REFERENCE_PRODUCT.MISSING}}"],
            )
        ], [], ["{{REFERENCE_PRODUCT.MISSING}}"]
    blocks = []
    text = (
        f"Референтный препарат: {r.get('trade_name') or r.get('inn') or '{{REFERENCE_PRODUCT.NAME}}'}, "
        f"доза {r.get('dosage') or '{{REFERENCE_PRODUCT.DOSAGE}}'}."
    )
    src = list(r.get("source_ids") or []) if isinstance(r.get("source_ids"), list) else []
    blocks.append(_block(type_="TEXT", text=text, origin="SOURCE_DERIVED", source_ids=src))
    tb = TEXT_BLOCKS.get("REFERENCE_NOT_PURCHASED")
    if tb:
        rendered = _render_text_block(tb, variables, ctx)
        if rendered:
            blocks.append(rendered)
    blocks.append(_block(type_="TABLE", table_key="REFERENCE_PRODUCT"))
    return blocks, src, find_unresolved_markers(blocks)


def _gen_study_conditions(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    design = variables.get("design_type") or "{{DESIGN.TYPE}}"
    food = variables.get("food_condition") or "{{FOOD.CONDITION}}"
    text = f"Условия исследования: дизайн {design}, пища {food}."
    return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED")], [], find_unresolved_markers(text)


def _gen_subjects_rationale(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    eval_n = variables.get("evaluable_n")
    rand_n = variables.get("randomized_n")
    eval_s = eval_n if eval_n is not None else "{{SUBJECTS.EVALUABLE_N}}"
    rand_s = rand_n if rand_n is not None else "{{SUBJECTS.RANDOMIZED_N}}"
    text = (
        f"Планируемое число оцениваемых субъектов: {eval_s}; "
        f"рандомизированных субъектов: {rand_s}."
    )
    return [_block(type_="TEXT", text=text, origin="CALCULATED", rule_id="SUBJECTS.N")], [], find_unresolved_markers(text)


def _gen_reference_justification(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    r = ctx.get("reference_product") or {}
    if not r:
        return [_block(type_="TEXT", text="{{REFERENCE_PRODUCT.JUSTIFICATION}}", unresolved=["{{REFERENCE_PRODUCT.JUSTIFICATION}}"])], [], ["{{REFERENCE_PRODUCT.JUSTIFICATION}}"]
    text = f"Обоснование выбора референта {r.get('trade_name') or r.get('inn')} на основании доступных источников."
    src = list(r.get("source_ids") or []) if isinstance(r.get("source_ids"), list) else []
    return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED", source_ids=src)], src, []


def _gen_observation_rationale(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    o = ctx.get("observation") or {}
    dur = o.get("selected_duration") or o.get("final_sampling_time")
    unit = o.get("selected_unit") or o.get("unit") or "h"
    text = f"Длительность наблюдения: {dur if dur is not None else '{{OBSERVATION.DURATION}}'} {unit}."
    return [
        _block(type_="TEXT", text=text, origin="CALCULATED", rule_id="PK.OBSERVATION")
    ], [], find_unresolved_markers(text)


def _gen_washout_rationale(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks = []
    tb = TEXT_BLOCKS.get("WASHOUT_DESCRIPTION")
    if tb:
        rendered = _render_text_block(tb, variables, ctx)
        if rendered:
            blocks.append(rendered)
    if not blocks:
        blocks.append(
            _block(type_="TEXT", text="{{WASHOUT.VALUE}}", unresolved=["{{WASHOUT.VALUE}}"])
        )
    return blocks, [], find_unresolved_markers(blocks)


def _gen_objectives(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    study = ctx.get("study") or {}
    primary = study.get("primary_objective") or study.get("objective")
    design = variables.get("design_type_full") or variables.get("design_type") or "{{DESIGN.TYPE}}"
    if primary:
        text = str(primary)
        extras = []
        for key in ("secondary_objectives", "objectives"):
            val = study.get(key)
            if isinstance(val, list) and val:
                extras.extend(str(x) for x in val)
            elif isinstance(val, str) and val and val != primary:
                extras.append(val)
        blocks = [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED", rule_id="OBJECTIVES.STUDY")]
        if extras:
            blocks.append(_block(type_="NUMBERED_LIST", items=extras, origin="SOURCE_DERIVED"))
        return blocks, [], find_unresolved_markers(blocks)
    text = (
        f"Цель: оценить биоэквивалентность тестового и референтного препаратов "
        f"в дизайне {design}."
    )
    return [_block(type_="TEXT", text=text, origin="RULE_DERIVED", rule_id="OBJECTIVES.BE")], [], find_unresolved_markers(text)


def _gen_pk_parameters(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return [
        _block(type_="TABLE", table_key="PK_PARAMETERS", origin="SOURCE_DERIVED"),
        _block(type_="REFERENCE", target_type="table", target_id="PK_PARAMETERS", display_text="таблица PK_PARAMETERS"),
    ], [], []


def _gen_design(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks: list[dict] = []
    for code in (
        "CROSSOVER_DESCRIPTION",
        "REPLICATE_DESCRIPTION",
        "PARALLEL_DESCRIPTION",
        "ADAPTIVE_DESCRIPTION",
    ):
        tb = TEXT_BLOCKS.get(code)
        if not tb:
            continue
        rendered = _render_text_block(tb, variables, ctx)
        if rendered:
            blocks.append(rendered)
    if not blocks:
        blocks.append(
            _block(type_="TEXT", text="{{DESIGN.TYPE}}", unresolved=["{{DESIGN.TYPE}}"])
        )
    return blocks, [], find_unresolved_markers(blocks)


def _gen_randomization(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    text = "Рандомизация субъектов в последовательности лечения выполняется до приёма первой дозы."
    return [_block(type_="TEXT", text=text, origin="RULE_DERIVED", rule_id="DESIGN.RANDOMIZATION")], [], []


def _gen_treatment(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    food = variables.get("food_condition") or "{{FOOD.CONDITION}}"
    text = f"Лечение включает введение T и R. Условие пищи: {food}."
    return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED")], [], find_unresolved_markers(text)


def _gen_stages(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    design = ctx.get("design") or {}
    periods = design.get("periods")
    items = [f"Period {i}" for i in range(1, int(periods or 0) + 1)] or ["{{DESIGN.PERIODS}}"]
    return [_block(type_="NUMBERED_LIST", items=items, origin="SOURCE_DERIVED")], [], find_unresolved_markers(items)


def _gen_sampling_plan(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks: list[dict] = []
    tb = TEXT_BLOCKS.get("SAMPLING_RATIONALE")
    if tb:
        rendered = _render_text_block(tb, variables, ctx)
        if rendered:
            blocks.append(rendered)
    blocks.append(_block(type_="TABLE", table_key="BLOOD_SAMPLING", origin="CALCULATED", rule_id="PK.SAMPLING"))
    blocks.append(
        _block(
            type_="REFERENCE",
            target_type="table",
            target_id="BLOOD_SAMPLING",
            display_text="таблица BLOOD_SAMPLING",
        )
    )
    sampling = ctx.get("sampling") or {}
    src: list[str] = []
    if isinstance(sampling.get("source_ids"), list):
        src = list(sampling["source_ids"])
    return blocks, src, find_unresolved_markers(blocks)


def _gen_participation_duration(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    text = (
        f"Длительность участия определяется периодами лечения, washout "
        f"{variables.get('washout_value')} {variables.get('washout_unit')} "
        f"и наблюдением {variables.get('observation_duration')} {variables.get('observation_unit')}."
    )
    return [_block(type_="TEXT", text=text, origin="CALCULATED", rule_id="PK.DURATION")], [], find_unresolved_markers(text)


def _gen_eligibility(category: str):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        from app.domain.eligibility_render import render_eligibility_list

        elig = ctx.get("eligibility") or {}
        rows = elig.get(category) or []
        marker = f"{{{{ELIGIBILITY.{category.upper()}}}}}"
        if not rows:
            return [
                _block(type_="TEXT", text=marker, unresolved=[marker], origin="TEMPLATE")
            ], [], [marker]
        items = render_eligibility_list(rows, numbered=True)
        return [_block(type_="NUMBERED_LIST", items=items, origin="SOURCE_DERIVED")], [], []

    return _inner


def _gen_treatment_detail(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return _gen_treatment(section, ctx, variables, consistency)


def _gen_washout_procedure(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return _gen_washout_rationale(section, ctx, variables, consistency)


def _gen_food_restrictions(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks: list[dict] = []
    for code in ("FED_MEAL_DESCRIPTION", "FASTING_DESCRIPTION", "FASTING_AND_FED_DESCRIPTION"):
        tb = TEXT_BLOCKS.get(code)
        if not tb:
            continue
        rendered = _render_text_block(tb, variables, ctx)
        if rendered:
            blocks.append(rendered)
    if not blocks:
        blocks.append(
            _block(type_="TEXT", text="{{FOOD.CONDITION}}", unresolved=["{{FOOD.CONDITION}}"])
        )
    return blocks, [], find_unresolved_markers(blocks)


def _gen_eval_parameters(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks = [_block(type_="TABLE", table_key="PK_PARAMETERS")]
    analytes = ctx.get("analytes") or []
    if len(analytes) > 1:
        names = ", ".join(a.get("name") or "{{ANALYTE.NAME}}" for a in analytes)
        blocks.append(
            _block(
                type_="TEXT",
                block_code="MULTI_ANALYTE_NOTE",
                text=f"В исследовании оценивается более одного аналита ({len(analytes)}): {names}.",
                origin="SOURCE_DERIVED",
            )
        )
    return blocks, [], find_unresolved_markers(blocks)


def _gen_bioanalysis(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    analytes = ctx.get("analytes") or []
    names = ", ".join(a.get("name") or "{{ANALYTE.NAME}}" for a in analytes) or "{{ANALYTES.NAMES}}"
    text = f"Биоаналитическое определение: {names}. Метод: {{BIOANALYSIS.METHOD}}."
    return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED")], [], find_unresolved_markers(text)


def _gen_safety_standard(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    tb = TEXT_BLOCKS["SAFETY_STANDARD_TEXT"]
    rendered = _render_text_block(tb, variables, ctx)
    return ([rendered] if rendered else []), [], []


def _gen_statistical_method(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    tb = TEXT_BLOCKS["STATISTICAL_METHOD"]
    rendered = _render_text_block(tb, variables, ctx)
    return ([rendered] if rendered else []), [], find_unresolved_markers(rendered or {})


def _gen_sample_size(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks: list[dict] = []
    tb = TEXT_BLOCKS["SAMPLE_SIZE_RATIONALE"]
    rendered = _render_text_block(tb, variables, ctx)
    if rendered:
        rendered["origin"] = "CALCULATED"
        rendered["rule_id"] = "STATISTICS.SAMPLE_SIZE"
        blocks.append(rendered)
    if any(t.get("table_key") == "CV_EVIDENCE" for t in build_tables(ctx, consistency)):
        # table presence checked later; reference by key
        blocks.append(_block(type_="TABLE", table_key="CV_EVIDENCE", origin="SOURCE_DERIVED"))
    blocks.append(
        _block(
            type_="REFERENCE",
            target_type="section",
            target_id="SYNOPSIS",
            display_text="см. Synopsis (N)",
        )
    )
    return blocks, [], find_unresolved_markers(blocks)


def _gen_alpha(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return P0_GENERATORS["alpha"](section, ctx, variables, consistency)


def _gen_be_criteria(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return P0_GENERATORS["be_criteria"](section, ctx, variables, consistency)


def _gen_standard_text(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return [
        _block(
            type_="TEXT",
            text=f"{section.title}: стандартный раздел шаблона (без study-specific данных).",
            origin="TEMPLATE",
        )
    ], [], []


def _gen_appendices(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return [
        _block(type_="PAGE_BREAK"),
        _block(type_="TEXT", text="Приложения", origin="TEMPLATE"),
        _block(
            type_="REFERENCE",
            target_type="appendix",
            target_id="A",
            display_text="Приложение A",
        ),
    ], [], []


def _gen_literature(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    sources = ctx.get("sources") or []
    if not sources:
        return [
            _block(type_="TEXT", text="{{SOURCES.LIST}}", unresolved=["{{SOURCES.LIST}}"])
        ], [], ["{{SOURCES.LIST}}"]
    items = []
    for s in sources:
        parts = []
        stype = s.get("type")
        if stype:
            parts.append(resolve_display(stype, context="source_type", fallback=str(stype)))
        authors = s.get("authors") or []
        if isinstance(authors, list) and authors:
            parts.append(", ".join(str(a) for a in authors))
        elif authors:
            parts.append(str(authors))
        title = s.get("title") or ""
        if title:
            parts.append(title)
        if s.get("year"):
            parts.append(str(s["year"]))
        if s.get("url"):
            parts.append(str(s["url"]))
        if s.get("access_date"):
            parts.append(f"accessed {s['access_date']}")
        items.append(" — ".join(parts) if parts else str(s.get("id")))
    src_ids = [str(s.get("id")) for s in sources if s.get("id")]
    return [
        _block(type_="LIST", items=items, origin="SOURCE_DERIVED", source_ids=src_ids),
        _block(type_="TABLE", table_key="SOURCES"),
    ], src_ids, []


GENERATORS: dict[str, GeneratorFn] = {
    "heading": _gen_heading,
    "synopsis": _gen_synopsis,
    "protocol_metadata": _gen_protocol_metadata,
    "sponsor": _gen_sponsor,
    "unresolved_org": _gen_unresolved_org,
    "signatures": _gen_signatures,
    "test_product": _gen_test_product,
    "reference_product": _gen_reference_product,
    "study_conditions": _gen_study_conditions,
    "subjects_rationale": _gen_subjects_rationale,
    "reference_justification": _gen_reference_justification,
    "observation_rationale": _gen_observation_rationale,
    "washout_rationale": _gen_washout_rationale,
    "objectives": _gen_objectives,
    "pk_parameters": _gen_pk_parameters,
    "design": _gen_design,
    "randomization": _gen_randomization,
    "treatment": _gen_treatment,
    "stages": _gen_stages,
    "sampling_plan": _gen_sampling_plan,
    "participation_duration": _gen_participation_duration,
    "inclusion": _gen_eligibility("inclusion"),
    "non_inclusion": _gen_eligibility("non_inclusion"),
    "exclusion": _gen_eligibility("exclusion"),
    "treatment_detail": _gen_treatment_detail,
    "washout_procedure": _gen_washout_procedure,
    "food_restrictions": _gen_food_restrictions,
    "eval_parameters": _gen_eval_parameters,
    "bioanalysis": _gen_bioanalysis,
    "safety_standard": _gen_safety_standard,
    "statistical_method": _gen_statistical_method,
    "sample_size": _gen_sample_size,
    "alpha": _gen_alpha,
    "be_criteria": _gen_be_criteria,
    "standard_text": _gen_standard_text,
    "appendices": _gen_appendices,
    "literature": _gen_literature,
}
GENERATORS.update(P0_GENERATORS)
GENERATORS.update(P1_GENERATORS)
GENERATORS.update(CORE_12B1_GENERATORS)  # Phase 12B.1 core overlays (last wins)
GENERATORS.update(CORE_12B2_GENERATORS)  # Phase 12B.2 sections 5–8 overlays
GENERATORS.update(CORE_12B3_GENERATORS)  # Phase 12B.3 sections 9–15 overlays
GENERATORS.update(CORE_12B4_GENERATORS)  # Phase 12B.4 sections 16–18 overlays


def assemble_protocol(
    ctx: dict,
    *,
    blocking_validation: bool,
    validation_issues: list[dict] | None = None,
    rules_version: str = "1",
    protocol_version: str = "1",
    only_section: str | None = None,
    only_sections: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """
    Build structured ProtocolDraft payload (deterministic).
    Does not write DOCX.
    only_section / only_sections: optional filters for targeted rebuilds.
    """
    consistency = build_consistency_snapshot(ctx)
    canonical = build_canonical_snapshot(ctx)
    variables = build_variable_map(ctx, consistency)
    tables = build_tables(ctx, consistency)
    table_registry = build_table_registry(tables)
    tables = apply_table_numbers_to_tables(tables, table_registry)
    table_by_key = {t["table_key"]: t for t in tables}

    sections_out: list[dict] = []
    all_unresolved: list[str] = []
    warnings: list[str] = []
    calculated_values: list[dict] = []
    expert_verified_values: list[dict] = []
    source_ids_all: set[str] = set()
    blocking_issues: list[dict] = []

    if blocking_validation:
        for issue in validation_issues or []:
            if issue.get("blocking"):
                blocking_issues.append(
                    {
                        "code": "VALIDATION_BLOCKING",
                        "rule_id": issue.get("rule_id"),
                        "message": issue.get("message"),
                        "field": issue.get("field"),
                    }
                )

    for section in SECTION_TREE:
        if only_section and section.section_code != only_section:
            continue
        if only_sections is not None and section.section_code not in only_sections:
            continue
        if not conditions_pass(section.conditions, ctx):
            sections_out.append(
                {
                    "section_code": section.section_code,
                    "title": section.title,
                    "order": section.order,
                    "parent_section": section.parent_section,
                    "status": "SKIPPED",
                    "generation_status": "SKIPPED",
                    "content_blocks": [],
                    "source_ids": [],
                    "warnings": [f"Condition not met: {section.conditions}"],
                    "template_key": section.template_key,
                }
            )
            continue

        missing = _missing_required(section, ctx)
        gen = GENERATORS.get(section.generator, _gen_heading)

        # Soft-missing for optional empty lists on headings
        hard_missing = [
            m
            for m in missing
            if section.generator
            not in {
                "heading",
                "standard_text",
                "unresolved_org",
                "sponsor",
                "sponsor_persons",
                "medical_expert",
                "investigators",
                "analytical_lab",
                "key_orgs",
                "signatures",
                "investigator_agreement",
                "safety_standard",
                "alpha",
                "be_criteria",
                "appendices",
                "objectives",
                "randomization",
                "preclinical_clinical_summary",
                "risk_benefit",
                "dose_rationale",
                "rationale_literature",
                "pharmacology",
                "stop_rules",
                "ae_framework",
                "ae_followup",
                "pregnancy",
                "physical_exam",
                "vital_signs",
                "safety_labs",
                "safety_methods",
                "financing_insurance",
                "publications",
                "data_access",
                "standard_text",
                "conclusion",
            }
        ]

        content_blocks, src_ids, unresolved = gen(section, ctx, variables, consistency)
        content_blocks = [b for b in content_blocks if b is not None]

        # Attach table display numbers into TABLE blocks via TableRegistry
        for b in content_blocks:
            if b.get("type") == "TABLE" and b.get("table_key") in table_by_key:
                t = table_by_key[b["table_key"]]
                display = table_registry.display_text(b["table_key"]) or f"Таблица {t['display_number']}"
                b["display_text"] = display
                b["table_number"] = t["display_number"]

            if b.get("origin") == "CALCULATED":
                calculated_values.append(
                    {
                        "section_code": section.section_code,
                        "block_code": b.get("block_code"),
                        "rule_id": b.get("rule_id"),
                        "text": b.get("text"),
                    }
                )
            if (ctx.get("analytes") or []) and any(
                (a.get("status") == "VERIFIED") for a in (ctx.get("analytes") or [])
            ):
                if b.get("origin") == "SOURCE_DERIVED":
                    expert_verified_values.append(
                        {
                            "section_code": section.section_code,
                            "origin": "EXPERT_VERIFIED",
                        }
                    )

            forbad = scan_forbidden_placeholders(str(b.get("text") or ""))
            if forbad:
                warnings.append(
                    f"{section.section_code}: forbidden placeholder tokens {forbad}"
                )
                b["text"] = "{{UNRESOLVED}}"
                b["unresolved"] = list(set((b.get("unresolved") or []) + ["{{UNRESOLVED}}"]))

        source_ids_all.update(str(x) for x in src_ids)
        all_unresolved.extend(unresolved)
        all_unresolved.extend(find_unresolved_markers(content_blocks))

        status = "GENERATED"
        gen_status = "OK"
        sec_warnings = list(hard_missing and [f"MISSING_REQUIRED_DATA:{','.join(hard_missing)}"] or [])
        if hard_missing and section.generator in {
            "sampling_plan",
            "sample_size",
            "pk_parameters",
            "reference_product",
            "test_product",
            "design",
        }:
            status = "UNRESOLVED"
            gen_status = "UNRESOLVED"
            blocking_issues.append(
                {
                    "code": "MISSING_REQUIRED_DATA",
                    "section_code": section.section_code,
                    "fields": hard_missing,
                    "message": f"Missing required data for {section.section_code}",
                }
            )
        if find_unresolved_markers(content_blocks):
            if status != "UNRESOLVED":
                status = "UNRESOLVED"
                gen_status = "UNRESOLVED"

        if blocking_validation:
            status = "BLOCKED"
            if gen_status not in {"SKIPPED", "UNRESOLVED"}:
                gen_status = "FAILED"

        sections_out.append(
            {
                "section_code": section.section_code,
                "title": section.title,
                "order": section.order,
                "parent_section": section.parent_section,
                "status": status,
                "generation_status": gen_status,
                "content_blocks": content_blocks,
                "source_ids": list(src_ids),
                "warnings": sec_warnings,
                "template_key": section.template_key,
            }
        )

    # Consistency (legacy protocol checks + Phase 11A canonical)
    consistency_issues = validate_protocol_consistency(
        consistency=consistency, sections=sections_out, tables=tables
    )
    for issue in consistency_issues:
        blocking_issues.append(
            {
                "code": "PROTOCOL_CONSISTENCY",
                "rule_id": issue.rule_id,
                "message": issue.message,
                "field": issue.field,
            }
        )

    canon_report = validate_canonical_consistency(
        ctx,
        consistency=consistency,
        sections=sections_out,
        tables=tables,
    )
    for issue in canon_report.issues:
        if issue.blocking:
            blocking_issues.append(
                {
                    "code": "CANONICAL_CONSISTENCY",
                    "rule_id": issue.rule_id,
                    "message": issue.message,
                    "field": issue.field,
                    "details": issue.details,
                }
            )

    unresolved_unique = sorted(set(all_unresolved))
    if unresolved_unique:
        for u in unresolved_unique:
            if u not in {i.get("message") for i in blocking_issues}:
                pass  # listed in report

    # Draft status
    has_missing_critical = any(i.get("code") == "MISSING_REQUIRED_DATA" for i in blocking_issues)
    has_consistency = any(
        i.get("code") in {"PROTOCOL_CONSISTENCY", "CANONICAL_CONSISTENCY"} for i in blocking_issues
    )
    if blocking_validation or has_missing_critical or has_consistency:
        draft_status = "BLOCKED"
    elif unresolved_unique:
        draft_status = "DRAFT"  # unresolved template placeholders → not ready
    else:
        draft_status = "READY_FOR_REVIEW"

    # Cross-references collected
    references: list[dict] = []
    for s in sections_out:
        for b in s.get("content_blocks") or []:
            if b.get("type") == "REFERENCE":
                references.append(
                    {
                        "source_section": s["section_code"],
                        "target_type": b.get("target_type"),
                        "target_id": b.get("target_id"),
                        "display_text": b.get("display_text"),
                    }
                )

    section_codes = {s["section_code"] for s in sections_out}
    ref_registry = build_reference_registry(
        references, table_registry=table_registry, section_codes=section_codes
    )
    for broken in ref_registry.unresolved():
        blocking_issues.append(
            {
                "code": "BROKEN_REFERENCE",
                "rule_id": "CANON.REF.BROKEN.v1",
                "message": broken.error or "Broken reference",
                "field": broken.target_id,
            }
        )
        draft_status = "BLOCKED"

    # Resolve reference display texts from registry
    for ref, entry in zip(references, ref_registry.entries):
        ref["display_text"] = entry.display_text
        ref["resolved"] = entry.resolved

    report = {
        "generated_sections": [s["section_code"] for s in sections_out if s["generation_status"] in {"OK", "UNRESOLVED"}],
        "unresolved_fields": unresolved_unique,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "source_count": len(source_ids_all),
        "calculated_values": calculated_values,
        "expert_verified_values": expert_verified_values,
        "table_count": len(tables),
        "reference_count": len(references),
        "snapshot_fingerprint": canonical.fingerprint(),
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "table_registry": table_registry.to_dict(),
        "reference_registry": ref_registry.to_dict(),
        "document_consistency": canon_report.to_dict(),
    }

    return {
        "status": draft_status,
        "protocol_version": protocol_version,
        "template_version": PROTOCOL_TEMPLATE_VERSION,
        "rules_version": rules_version,
        "generator_version": PROTOCOL_GENERATOR_VERSION,
        "sections": sections_out,
        "tables": tables,
        "references": references,
        "build_report": report,
        "consistency_snapshot": consistency,
        "canonical_fingerprint": canonical.fingerprint(),
        "document_consistency": canon_report.to_dict(),
    }
