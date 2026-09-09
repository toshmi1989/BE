"""Phase 12B.1 — core section generators (canonical-first, provenance-aware).

Overlays existing GENERATORS for selected keys. No medical invention.
Does not mutate Study / Canonical.
"""

from __future__ import annotations

from typing import Any

from app.domain.canonical_sampling import get_canonical_sampling_plan
from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.content_core_templates import be_objective_template, sampling_summary_lines
from app.domain.content_resolver import filter_decision_for_render
from app.domain.display_value_registry import find_raw_enums_in_text, resolve_display
from app.domain.protocol_consistency import find_unresolved_markers
from app.domain.protocol_sections import SectionDef


def _block(**kwargs: Any) -> dict:
    """Local block builder — avoids circular import with protocol_assembly."""
    text = kwargs.get("text")
    unresolved = kwargs.get("unresolved")
    if unresolved is None:
        unresolved = find_unresolved_markers(text) if text else []
    return {
        "type": kwargs.get("type_") or kwargs.get("type") or "TEXT",
        "block_code": kwargs.get("block_code"),
        "text": text,
        "items": kwargs.get("items") or [],
        "table_key": kwargs.get("table_key"),
        "origin": kwargs.get("origin"),
        "rule_id": kwargs.get("rule_id"),
        "source_ids": kwargs.get("source_ids") or [],
        "unresolved": unresolved,
        "target_type": kwargs.get("target_type"),
        "target_id": kwargs.get("target_id"),
        "display_text": kwargs.get("display_text"),
    }


def _decisions(ctx: dict) -> list[dict]:
    return list(ctx.get("expert_decisions") or [])


def _latest_approved(ctx: dict, decision_type: str) -> dict | None:
    approved = [
        d
        for d in _decisions(ctx)
        if str(d.get("decision_type")) == decision_type
        and filter_decision_for_render(d) is not None
    ]
    if not approved:
        return None
    return max(
        approved,
        key=lambda d: str(d.get("decided_at") or d.get("created_at") or ""),
    )


def _enrich(block: dict, *, resolution_status: str, display_as_final: bool, **extra: Any) -> dict:
    block = dict(block)
    block["resolution_status"] = resolution_status
    block["display_as_final"] = display_as_final
    block["content_type"] = block.get("content_type") or (
        "CANONICAL_VALUE" if display_as_final else "PLACEHOLDER"
    )
    for k, v in extra.items():
        block[k] = v
    # Never allow raw enums in final text
    text = block.get("text")
    if text and find_raw_enums_in_text(str(text)):
        block["text"] = "{{DISPLAY.ENUM}}"
        block["unresolved"] = list(set((block.get("unresolved") or []) + ["{{DISPLAY.ENUM}}"]))
        block["resolution_status"] = "UNRESOLVED"
        block["display_as_final"] = False
    return block


def _product_name(p: dict | None) -> str | None:
    p = p or {}
    return p.get("trade_name") or p.get("inn") or None


def gen_test_product_12b1(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    p = ctx.get("product") or {}
    if not p:
        b = _block(
            type_="TEXT",
            block_code="TEST_PRODUCT.MISSING",
            text="{{TEST_PRODUCT.MISSING}}",
            unresolved=["{{TEST_PRODUCT.MISSING}}"],
            origin="PLACEHOLDER",
        )
        return [_enrich(b, resolution_status="UNRESOLVED", display_as_final=False)], [], [
            "{{TEST_PRODUCT.MISSING}}"
        ]
    # Semantic field mapping — explicit keys, not positional
    fields = [
        ("trade_name", "Торговое наименование"),
        ("inn", "МНН"),
        ("manufacturer", "Производитель"),
        ("dosage_form", "Лекарственная форма"),
        ("dosage", "Доза / дозировка"),
        ("composition", "Состав"),
        ("route", "Путь введения"),
    ]
    lines = []
    unresolved = []
    for key, label in fields:
        val = p.get(key)
        if val in (None, ""):
            marker = f"{{{{TEST_PRODUCT.{key.upper()}}}}}"
            unresolved.append(marker)
            lines.append(f"{label}: {marker}")
        else:
            display = resolve_display(str(val), context="general", fallback=str(val))
            lines.append(f"{label}: {display}")
    text = "Тестовый препарат.\n" + "\n".join(lines)
    src = list(p.get("source_ids") or []) if isinstance(p.get("source_ids"), list) else []
    blocks = [
        _enrich(
            _block(
                type_="TEXT",
                block_code="TEST_PRODUCT.SEMANTIC",
                text=text,
                origin="SOURCE_DERIVED",
                source_ids=src,
                unresolved=unresolved,
            ),
            resolution_status="RESOLVED" if not unresolved else "UNRESOLVED",
            display_as_final=not unresolved,
            canonical_source="product",
            content_type="CANONICAL_VALUE",
        ),
        _enrich(
            _block(type_="TABLE", table_key="TEST_PRODUCT", origin="SOURCE_DERIVED"),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="TABLE",
        ),
    ]
    return blocks, src, unresolved


def gen_reference_product_12b1(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    r = ctx.get("reference_product") or {}
    # Do not auto-select reference
    proposed_only = any(
        str(d.get("decision_type")) == "REFERENCE_PRODUCT"
        and str(d.get("status")).upper() == "PROPOSED"
        for d in _decisions(ctx)
    )
    approved_ref = _latest_approved(ctx, "REFERENCE_PRODUCT")
    if not r and not approved_ref:
        marker = "{{REFERENCE_PRODUCT.MISSING}}"
        finding = "REFERENCE_SELECTION_REVIEW_REQUIRED"
        b = _block(
            type_="TEXT",
            block_code=finding,
            text=f"{marker} [{finding}]",
            unresolved=[marker],
            origin="PLACEHOLDER",
        )
        return [
            _enrich(
                b,
                resolution_status="BLOCKED" if proposed_only else "UNRESOLVED",
                display_as_final=False,
                content_type="PLACEHOLDER",
                knowledge_gaps=[
                    {
                        "domain": "REFERENCE_SELECTION",
                        "question": "Reference product not approved in canonical study",
                        "importance": "HIGH",
                        "blocking": True,
                    }
                ],
            )
        ], [], [marker]
    if not r and approved_ref:
        r = (approved_ref.get("final_value") or approved_ref.get("proposed_value") or {})
    fields = [
        ("trade_name", "Торговое наименование"),
        ("inn", "МНН"),
        ("manufacturer", "Производитель / держатель РУ"),
        ("dosage_form", "Лекарственная форма"),
        ("dosage", "Доза"),
    ]
    lines = []
    unresolved = []
    for key, label in fields:
        val = r.get(key) if isinstance(r, dict) else None
        if val in (None, ""):
            marker = f"{{{{REFERENCE_PRODUCT.{key.upper()}}}}}"
            unresolved.append(marker)
            lines.append(f"{label}: {marker}")
        else:
            lines.append(f"{label}: {resolve_display(str(val), fallback=str(val))}")
    text = "Референтный препарат (канонический / утверждённый).\n" + "\n".join(lines)
    src = list(r.get("source_ids") or []) if isinstance(r, dict) and isinstance(r.get("source_ids"), list) else []
    blocks = [
        _enrich(
            _block(
                type_="TEXT",
                block_code="REFERENCE_PRODUCT.SEMANTIC",
                text=text,
                origin="SOURCE_DERIVED",
                source_ids=src,
                unresolved=unresolved,
            ),
            resolution_status="RESOLVED" if not unresolved else "UNRESOLVED",
            display_as_final=not unresolved,
            canonical_source="reference_product",
            expert_decision_id=str(approved_ref["id"]) if approved_ref and approved_ref.get("id") else None,
        ),
        _enrich(
            _block(type_="TABLE", table_key="REFERENCE_PRODUCT", origin="SOURCE_DERIVED"),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="TABLE",
        ),
    ]
    return blocks, src, unresolved


def gen_design_12b1(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    design = ctx.get("design") or {}
    dtype = design.get("type") or consistency.get("design")
    proposed = any(
        str(d.get("decision_type")) == "DESIGN" and str(d.get("status")).upper() == "PROPOSED"
        for d in _decisions(ctx)
    )
    approved = _latest_approved(ctx, "DESIGN")
    # Proposed decision alone must not become final if no canonical design
    if not dtype:
        if proposed and not approved:
            b = _block(
                type_="TEXT",
                block_code="DESIGN.PROPOSED_NOT_FINAL",
                text="{{DESIGN.TYPE}} [PROPOSED — not final]",
                unresolved=["{{DESIGN.TYPE}}"],
                origin="PLACEHOLDER",
            )
            return [
                _enrich(
                    b,
                    resolution_status="PROPOSED",
                    display_as_final=False,
                    knowledge_gaps=[
                        {
                            "domain": "DESIGN",
                            "question": "Design missing — proposed ExpertDecision is not final",
                            "importance": "CRITICAL",
                            "blocking": True,
                        }
                    ],
                )
            ], [], ["{{DESIGN.TYPE}}"]
        b = _block(
            type_="TEXT",
            block_code="DESIGN.MISSING",
            text="{{DESIGN.TYPE}}",
            unresolved=["{{DESIGN.TYPE}}"],
            origin="PLACEHOLDER",
        )
        return [
            _enrich(
                b,
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[
                    {
                        "domain": "DESIGN",
                        "question": "Canonical study design is missing",
                        "importance": "CRITICAL",
                        "blocking": True,
                    }
                ],
            )
        ], [], ["{{DESIGN.TYPE}}"]

    display = resolve_display(str(dtype), context="design", fallback=None)
    if not display or display == str(dtype):
        display = resolve_display(str(dtype), context="design_long", fallback=str(dtype))
    if find_raw_enums_in_text(display):
        display = resolve_display(str(dtype), context="design_short", fallback="{{DESIGN.TYPE}}")
    periods = design.get("periods")
    seq = design.get("sequences")
    lines = [f"Дизайн исследования: {display}."]
    if periods is not None:
        lines.append(f"Число периодов: {periods}.")
    if seq:
        lines.append(f"Последовательности: {seq}.")
    text = " ".join(lines)
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="DESIGN.CANONICAL",
                text=text,
                origin="SOURCE_DERIVED",
                rule_id="DESIGN.CANONICAL",
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            canonical_source="design.type",
            content_type="CANONICAL_VALUE",
        )
    ], [], find_unresolved_markers(text)


def gen_objectives_12b1(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    study = ctx.get("study") or {}
    primary = study.get("primary_objective") or study.get("objective")
    design = ctx.get("design") or {}
    dtype = design.get("type") or consistency.get("design")
    design_disp = (
        resolve_display(str(dtype), context="design", fallback=None) if dtype else None
    )
    test_n = _product_name(ctx.get("product"))
    ref_n = _product_name(ctx.get("reference_product"))
    if primary:
        text = str(primary)
        if find_raw_enums_in_text(text):
            text = "{{OBJECTIVES.PRIMARY}}"
        blocks = [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="OBJECTIVES.PRIMARY",
                    text=text,
                    origin="SOURCE_DERIVED",
                    rule_id="OBJECTIVES.STUDY",
                ),
                resolution_status="RESOLVED" if "{{" not in text else "UNRESOLVED",
                display_as_final="{{" not in text,
                canonical_source="study.primary_objective",
            )
        ]
        return blocks, [], find_unresolved_markers(blocks)
    templ = be_objective_template(
        design_display=design_disp if design_disp and not find_raw_enums_in_text(design_disp) else None,
        test_name=test_n,
        reference_name=ref_n,
    )
    if templ:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="OBJECTIVES.BE_TEMPLATE",
                    text=templ,
                    origin="RULE_DERIVED",
                    rule_id="OBJECTIVES.BE",
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="GENERATED_TEXT",
                canonical_source="design+product+reference",
            )
        ], [], []
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="OBJECTIVES.MISSING",
                text="{{OBJECTIVES.PRIMARY}}",
                unresolved=["{{OBJECTIVES.PRIMARY}}"],
                origin="PLACEHOLDER",
            ),
            resolution_status="UNRESOLVED",
            display_as_final=False,
        )
    ], [], ["{{OBJECTIVES.PRIMARY}}"]


def gen_treatment_12b1(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    food_raw = (ctx.get("food") or {}).get("condition") or (ctx.get("design") or {}).get(
        "food_condition"
    )
    food = (
        resolve_display(str(food_raw), context="food", fallback=None) if food_raw else None
    )
    dose = (ctx.get("product") or {}).get("dosage")
    route = (ctx.get("product") or {}).get("route")
    parts = ["Лечение включает введение тестового (T) и референтного (R) препаратов."]
    unresolved = []
    if food:
        parts.append(f"Условие пищи: {food}.")
    else:
        parts.append("Условие пищи: {{FOOD.CONDITION}}.")
        unresolved.append("{{FOOD.CONDITION}}")
    if dose:
        parts.append(f"Доза: {dose}.")
    if route:
        parts.append(f"Путь введения: {resolve_display(str(route), fallback=str(route))}.")
    # Explicitly do NOT invent kcal / water / timing
    text = " ".join(parts)
    assert "kcal" not in text.lower()
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="TREATMENT.CANONICAL",
                text=text,
                origin="SOURCE_DERIVED",
                unresolved=unresolved,
            ),
            resolution_status="RESOLVED" if not unresolved else "UNRESOLVED",
            display_as_final=not unresolved,
            canonical_source="food+product",
        )
    ], [], unresolved


def gen_washout_12b1(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    wash = ctx.get("washout") or {}
    approved = _latest_approved(ctx, "WASHOUT")
    proposed = any(
        str(d.get("decision_type")) == "WASHOUT" and str(d.get("status")).upper() == "PROPOSED"
        for d in _decisions(ctx)
    )
    val = wash.get("selected_value")
    unit = wash.get("unit") or "day"
    if val is None and approved:
        fv = approved.get("final_value") or {}
        val = fv.get("selected_value") or fv.get("days") or fv.get("value")
        unit = fv.get("unit") or unit
    if val is None:
        status = "PROPOSED" if proposed else "UNRESOLVED"
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="WASHOUT.MISSING",
                    text="{{WASHOUT.VALUE}}"
                    + (" [PROPOSED — not final]" if proposed else ""),
                    unresolved=["{{WASHOUT.VALUE}}"],
                    origin="PLACEHOLDER",
                ),
                resolution_status=status,
                display_as_final=False,
                knowledge_gaps=[
                    {
                        "domain": "WASHOUT",
                        "question": "Washout not approved in canonical study",
                        "importance": "HIGH",
                        "blocking": True,
                    }
                ],
            )
        ], [], ["{{WASHOUT.VALUE}}"]
    text = f"Период отмывки (washout): {val} {unit}."
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="WASHOUT.CANONICAL",
                text=text,
                origin="SOURCE_DERIVED",
                rule_id="WASHOUT.CANONICAL",
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            canonical_source="washout.selected_value",
            expert_decision_id=str(approved["id"]) if approved and approved.get("id") else None,
        )
    ], [], []


def gen_sampling_plan_12b1(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    sampling_c = get_canonical_sampling_plan(ctx)
    points = list(sampling_c.points or [])
    # Prefer canonical; ignore old table text
    if not points:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="SAMPLING.MISSING",
                    text="{{SAMPLING.POINTS}}",
                    unresolved=["{{SAMPLING.POINTS}}"],
                    origin="PLACEHOLDER",
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[
                    {
                        "domain": "SAMPLING",
                        "question": "Canonical SamplingPlan missing",
                        "importance": "HIGH",
                        "blocking": True,
                    }
                ],
            )
        ], [], ["{{SAMPLING.POINTS}}"]

    # Order + dedupe by time
    seen = set()
    ordered = []
    for p in sorted(points, key=lambda x: float(x.get("time_h") or 0)):
        t = float(p.get("time_h") or 0)
        if t in seen:
            continue
        seen.add(t)
        ordered.append(p)

    tmax = None
    for a in ctx.get("analytes") or []:
        if a.get("tmax") is not None:
            tmax = a.get("tmax")
            break
    lines = sampling_summary_lines(
        points=ordered,
        analytes=list(ctx.get("analytes") or []),
        tmax=tmax,
        last_point=ordered[-1].get("time_h") if ordered else None,
        points_per_period=int(sampling_c.points_per_period)
        if getattr(sampling_c, "points_per_period", None) is not None
        else len(ordered),
    )
    text = "Сводка плана отбора проб (канонический SamplingPlan).\n" + "\n".join(lines)
    src: list[str] = []
    sampling = ctx.get("sampling") or {}
    if isinstance(sampling.get("source_ids"), list):
        src = list(sampling["source_ids"])
    blocks = [
        _enrich(
            _block(
                type_="TEXT",
                block_code="SAMPLING.SUMMARY",
                text=text,
                origin="CALCULATED",
                rule_id="PK.SAMPLING",
                source_ids=src,
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            canonical_source="sampling.points",
            content_type="CANONICAL_VALUE",
        ),
        _enrich(
            _block(
                type_="TABLE",
                table_key="BLOOD_SAMPLING",
                origin="CALCULATED",
                rule_id="PK.SAMPLING",
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="TABLE",
            canonical_source="sampling.points",
        ),
    ]
    return blocks, src, []


def gen_subjects_rationale_12b1(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    counts = get_canonical_subject_counts(ctx)
    # Never use template text as source
    eval_n = counts.evaluable_n
    rand_n = counts.randomized_n
    unresolved = []
    eval_s = str(eval_n) if eval_n is not None else "{{SUBJECTS.EVALUABLE_N}}"
    rand_s = str(rand_n) if rand_n is not None else "{{SUBJECTS.RANDOMIZED_N}}"
    if eval_n is None:
        unresolved.append("{{SUBJECTS.EVALUABLE_N}}")
    if rand_n is None:
        unresolved.append("{{SUBJECTS.RANDOMIZED_N}}")
    text = (
        f"Планируемое число оцениваемых субъектов: {eval_s}; "
        f"рандомизированных субъектов: {rand_s} "
        f"(источник: SubjectPlan / {counts.source})."
    )
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="SUBJECTS.N.CANONICAL",
                text=text,
                origin="CALCULATED",
                rule_id="SUBJECTS.N",
                unresolved=unresolved,
            ),
            resolution_status="RESOLVED" if not unresolved else "UNRESOLVED",
            display_as_final=not unresolved,
            canonical_source="subject_plan",
        )
    ], [], unresolved


CORE_12B1_GENERATORS: dict[str, Any] = {
    "test_product": gen_test_product_12b1,
    "reference_product": gen_reference_product_12b1,
    "design": gen_design_12b1,
    "objectives": gen_objectives_12b1,
    "treatment": gen_treatment_12b1,
    "washout_rationale": gen_washout_12b1,
    "sampling_plan": gen_sampling_plan_12b1,
    "subjects_rationale": gen_subjects_rationale_12b1,
}
