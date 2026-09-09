"""Phase 12B.2 — sections 5–8 generators (eligibility / procedures / PK / bio / safety).

Overlays existing GENERATORS. No medical invention. No template-as-truth.
PROPOSED never becomes final without approved ExpertDecision / verified source.
"""

from __future__ import annotations

from typing import Any

from app.domain.bioanalysis_plan import bioanalysis_plan_from_dict, empty_bioanalysis_plan
from app.domain.canonical_sampling import get_canonical_sampling_plan
from app.domain.content_resolver import filter_decision_for_render
from app.domain.criteria_rules import evaluate_criteria
from app.domain.display_value_registry import find_raw_enums_in_text, resolve_display
from app.domain.eligibility_render import render_eligibility_list
from app.domain.pk_semantic import display_auc_metric, resolve_auc_metric_type, standard_pk_profile
from app.domain.procedure_schedule import compose_procedure_schedule
from app.domain.protocol_consistency import find_unresolved_markers
from app.domain.protocol_sections import SectionDef
from app.domain.sample_processing import SampleProcessingDefinition, empty_sample_processing
from app.domain.safety_plan import build_safety_procedure_view, safety_plan_from_dict


def _block(**kwargs: Any) -> dict:
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
        if str(d.get("decision_type")) == decision_type and filter_decision_for_render(d) is not None
    ]
    if not approved:
        return None
    return max(approved, key=lambda d: str(d.get("decided_at") or d.get("created_at") or ""))


def _enrich(block: dict, *, resolution_status: str, display_as_final: bool, **extra: Any) -> dict:
    block = dict(block)
    block["resolution_status"] = resolution_status
    block["display_as_final"] = display_as_final
    block["content_type"] = block.get("content_type") or (
        "CANONICAL_VALUE" if display_as_final else "PLACEHOLDER"
    )
    for k, v in extra.items():
        block[k] = v
    text = block.get("text")
    if text and find_raw_enums_in_text(str(text)):
        block["text"] = "{{DISPLAY.ENUM}}"
        block["unresolved"] = list(set((block.get("unresolved") or []) + ["{{DISPLAY.ENUM}}"]))
        block["resolution_status"] = "UNRESOLVED"
        block["display_as_final"] = False
    # Also scrub list items for raw enums
    scrubbed_items = []
    for it in list(block.get("items") or []):
        s = str(it)
        if find_raw_enums_in_text(s):
            # Drop raw tokens — mark block non-final rather than leaking enums
            block["resolution_status"] = "UNRESOLVED"
            block["display_as_final"] = False
            block["unresolved"] = list(set((block.get("unresolved") or []) + ["{{DISPLAY.ENUM}}"]))
            continue
        scrubbed_items.append(it)
    if block.get("items") is not None:
        block["items"] = scrubbed_items
    return block


def _gap(domain: str, question: str, *, importance: str = "HIGH", blocking: bool = True, **extra: Any) -> dict:
    g = {
        "domain": domain,
        "question": question,
        "importance": importance,
        "blocking": blocking,
    }
    g.update(extra)
    return g


def _na_forbidden(text: str | None) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return t in {"n/a", "na", "n.a.", "not applicable", "as applicable", "standard"}


def _sample_processing_from_ctx(ctx: dict) -> SampleProcessingDefinition:
    raw = ctx.get("sample_processing") or {}
    if not raw:
        bio = bioanalysis_plan_from_dict(ctx.get("bioanalysis_plan"))
        # Map known bio fields into processing shell without inventing missing ones
        sp = empty_sample_processing()
        if bio.anticoagulant:
            sp.anticoagulant = bio.anticoagulant
        if bio.centrifugation or bio.centrifugation_time or bio.centrifugation_temperature:
            parts = [p for p in (bio.centrifugation, bio.centrifugation_temperature, bio.centrifugation_time) if p]
            sp.centrifugation = "; ".join(str(p) for p in parts) if parts else None
        if bio.storage_temperature or bio.storage_duration:
            parts = [p for p in (bio.storage_temperature, bio.storage_duration) if p]
            sp.storage = "; ".join(str(p) for p in parts) if parts else None
        if bio.matrix:
            sp.sample_type = bio.matrix
        if bio.source_ids:
            sp.source_ids = list(bio.source_ids)
        if any(getattr(sp, k) for k in ("anticoagulant", "centrifugation", "storage", "sample_type")):
            sp.status = "PARTIAL"
            sp.notes = "Projected from BioanalysisPlan — missing fields remain unresolved"
        return sp
    known = {f.name for f in SampleProcessingDefinition.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in raw.items() if k in known}
    return SampleProcessingDefinition(**kwargs)


# ---- Section 5: Eligibility ----


def _criteria_context(ctx: dict) -> dict[str, Any]:
    """Inputs for CriteriaRuleSet — never invent SmPC values."""
    evidence = list(ctx.get("evidence_claims") or [])
    smpc_ids = [
        str(e.get("id") or e.get("claim_id") or "")
        for e in evidence
        if str(e.get("source_type") or e.get("type") or "").upper() in {"SMPC", "ОХЛП", "LABEL"}
        or "smpc" in str(e.get("title") or "").lower()
    ]
    smpc_ids = [x for x in smpc_ids if x]
    tmax = None
    for a in ctx.get("analytes") or []:
        if a.get("tmax") is not None:
            tmax = float(a["tmax"])
            break
        if a.get("tmax_max") is not None:
            tmax = float(a["tmax_max"])
            break
    meta = ctx.get("criteria_meta") or {}
    return {
        "smpc_evidence_claim_ids": smpc_ids or list(meta.get("smpc_evidence_claim_ids") or []),
        "has_cyp_mentions": bool(meta.get("has_cyp_mentions")),
        "has_contraindications": bool(meta.get("has_contraindications")),
        "has_smoking_enzyme_link": bool(meta.get("has_smoking_enzyme_link")),
        "contraception_days_from_smpc": meta.get("contraception_days_from_smpc"),
        "tmax_h": tmax if tmax is not None else meta.get("tmax_h"),
    }


def gen_eligibility_category_12b2(category: str):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        elig = ctx.get("eligibility") or {}
        rows = list(elig.get(category) or [])
        marker = f"{{{{ELIGIBILITY.{category.upper()}}}}}"
        blocks: list[dict] = []
        src: list[str] = []
        unresolved: list[str] = []
        gaps: list[dict] = []

        if not rows:
            gaps.append(_gap("ELIGIBILITY", f"Missing {category} criteria in canonical eligibility set"))
            blocks.append(
                _enrich(
                    _block(
                        type_="TEXT",
                        block_code=f"ELIG.{category.upper()}.MISSING",
                        text=marker,
                        unresolved=[marker],
                        origin="PLACEHOLDER",
                    ),
                    resolution_status="UNRESOLVED",
                    display_as_final=False,
                    knowledge_gaps=gaps,
                    content_type="PLACEHOLDER",
                    canonical_source=f"eligibility.{category}",
                )
            )
            return blocks, src, [marker]

        items = render_eligibility_list(rows, numbered=True)
        # Strip forbidden N/A invent
        clean_items = []
        for it in items:
            if _na_forbidden(it.split(". ", 1)[-1] if ". " in it else it):
                gaps.append(_gap("ELIGIBILITY", f"Forbidden N/A-style criterion in {category}", blocking=True))
                continue
            clean_items.append(it)
            for r in rows:
                for sid in r.get("source_ids") or []:
                    src.append(str(sid))

        blocks.append(
            _enrich(
                _block(
                    type_="NUMBERED_LIST",
                    block_code=f"ELIG.{category.upper()}.LIST",
                    items=clean_items,
                    origin="SOURCE_DERIVED",
                    source_ids=list(dict.fromkeys(src)),
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
                canonical_source=f"eligibility.{category}",
            )
        )

        # CriteriaRuleSet overlays — PROPOSED unless approved decision
        crit = evaluate_criteria(**_criteria_context(ctx))
        approved_elig = _latest_approved(ctx, "ELIGIBILITY_OVERLAY") or _latest_approved(
            ctx, "CRITERIA_SET"
        )
        for ov in crit.drug_specific_overlays:
            ov_type = str(ov.get("type") or "")
            if ov_type == "VOMITING_WINDOW_PROPOSED":
                status = "PROPOSED"
                final = False
                # Only APPROVED ExpertDecision can elevate; never auto-verify CRIT-05
                if approved_elig and str(approved_elig.get("payload", {}).get("vomiting") or "").upper() == "APPROVED":
                    status = "RESOLVED"
                    final = True
                text = (
                    f"[REVIEW REQUIRED] Предложенное окно рвоты: 2 × Tmax "
                    f"(Tmax={ov.get('tmax_h')}, окно={ov.get('proposed_window_h')} ч). "
                    f"Правило CRIT-05 — PROPOSED, не verified policy."
                )
                blocks.append(
                    _enrich(
                        _block(
                            type_="TEXT",
                            block_code="ELIG.VOMITING.PROPOSED",
                            text=text,
                            origin="RULE_DERIVED",
                            rule_id="CRIT-05",
                        ),
                        resolution_status=status,
                        display_as_final=final,
                        content_type="EXPERT_DECISION" if final else "CONDITION",
                        knowledge_gaps=[]
                        if final
                        else [
                            _gap(
                                "ELIGIBILITY",
                                "Vomiting rule CRIT-05 is PROPOSED — ExpertDecision required for final",
                                importance="MEDIUM",
                                blocking=False,
                                related_rule_id="CRIT-05",
                            )
                        ],
                    )
                )
            elif ov_type == "CONTRACEPTION":
                days = ov.get("days")
                if days is None:
                    gaps.append(_gap("ELIGIBILITY", "Contraception period missing from SmPC", related_rule_id="CRIT-07"))
                else:
                    blocks.append(
                        _enrich(
                            _block(
                                type_="TEXT",
                                block_code="ELIG.CONTRACEPTION",
                                text=f"Контрацепция: период {days} дн. (источник: SmPC evidence).",
                                origin="SOURCE_DERIVED",
                                rule_id="CRIT-07",
                                source_ids=list(ov.get("evidence_claim_ids") or crit.drug_specific_overlays and []),
                            ),
                            resolution_status="RESOLVED",
                            display_as_final=True,
                            content_type="EVIDENCE_DERIVED",
                            canonical_source="criteria.contraception_days_from_smpc",
                        )
                    )
            elif ov_type in {"CYP", "CONTRAINDICATION"}:
                evid = list(ov.get("evidence_claim_ids") or [])
                if not evid:
                    gaps.append(
                        _gap(
                            "ELIGIBILITY",
                            f"{ov_type} overlay requires SmPC/evidence provenance",
                            related_rule_id="CRIT-03" if ov_type == "CYP" else "CRIT-04",
                        )
                    )
                    blocks.append(
                        _enrich(
                            _block(
                                type_="TEXT",
                                block_code=f"ELIG.{ov_type}.GAP",
                                text=f"{{{{ELIGIBILITY.{ov_type}}}}}",
                                unresolved=[f"{{{{ELIGIBILITY.{ov_type}}}}}"],
                            ),
                            resolution_status="UNRESOLVED",
                            display_as_final=False,
                            knowledge_gaps=gaps[-1:],
                        )
                    )
                else:
                    blocks.append(
                        _enrich(
                            _block(
                                type_="TEXT",
                                block_code=f"ELIG.{ov_type}",
                                text=str(ov.get("note") or ov_type),
                                origin="SOURCE_DERIVED",
                                source_ids=evid,
                            ),
                            resolution_status="RESOLVED",
                            display_as_final=True,
                            content_type="EVIDENCE_DERIVED",
                        )
                    )

        for g in crit.knowledge_gaps:
            gaps.append(g)

        meta = ctx.get("criteria_meta") or {}
        if meta.get("require_smoking") and not meta.get("has_smoking_enzyme_link") and not meta.get(
            "smoking_evidence_ids"
        ):
            gaps.append(
                _gap(
                    "ELIGIBILITY",
                    "Smoking restriction requested without enzyme-link evidence",
                    related_rule_id="CRIT-06",
                )
            )
            blocks.append(
                _enrich(
                    _block(
                        type_="TEXT",
                        block_code="ELIG.SMOKING.GAP",
                        text="{{ELIGIBILITY.SMOKING}}",
                        unresolved=["{{ELIGIBILITY.SMOKING}}"],
                    ),
                    resolution_status="UNRESOLVED",
                    display_as_final=False,
                    knowledge_gaps=gaps[-1:],
                )
            )

        if gaps and blocks:
            # attach gaps to first block for persistence
            first = blocks[0]
            first["knowledge_gaps"] = list(first.get("knowledge_gaps") or []) + gaps

        return blocks, list(dict.fromkeys(src)), unresolved

    return _inner


# ---- Section 6: Procedures ----


def gen_procedures_timeline_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    schedule = compose_procedure_schedule(ctx)
    items = []
    for p in schedule.procedures:
        # Human-readable name only — do not append raw category/stage enum codes
        label = p.name or p.code
        items.append(f"{p.sequence_order}. {label}")
    if not items:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="PROC.SCHEDULE.MISSING",
                    text="{{PROCEDURE.SCHEDULE}}",
                    unresolved=["{{PROCEDURE.SCHEDULE}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[_gap("PROCEDURE", "ProcedureSchedule empty — insufficient canonical inputs")],
            )
        ], [], ["{{PROCEDURE.SCHEDULE}}"]

    # Schedule itself is structural PROPOSED until expert confirms clinical battery
    status = "RESOLVED" if schedule.status in {"RESOLVED", "APPROVED"} else "PROPOSED"
    # Structural markers from canonical design/sampling are OK for draft; final needs approval if PROPOSED
    display_final = status == "RESOLVED"
    if schedule.procedures and all(
        str(p.origin) == "SOURCE_DERIVED" for p in schedule.procedures
    ):
        # Structural composition from canonical plans — eligible for draft+review content,
        # but mark PROPOSED for clinical completeness (no invented battery)
        status = "PROPOSED"
        display_final = False

    blocks = [
        _enrich(
            _block(
                type_="NUMBERED_LIST",
                block_code="PROC.SCHEDULE.SEQUENCE",
                items=items,
                origin="SOURCE_DERIVED",
            ),
            resolution_status=status,
            display_as_final=display_final,
            content_type="PROCEDURE",
            canonical_source="procedure_schedule",
            knowledge_gaps=[
                _gap(
                    "PROCEDURE",
                    "ProcedureSchedule is structural/PROPOSED — clinical battery not invented",
                    importance="MEDIUM",
                    blocking=False,
                )
            ]
            if not display_final
            else [],
        ),
        _enrich(
            _block(type_="TABLE", table_key="SCHEDULE_OF_ASSESSMENTS", origin="SOURCE_DERIVED"),
            resolution_status="PROPOSED",
            display_as_final=False,
            content_type="TABLE",
        ),
    ]
    return blocks, [], []


def gen_treatment_detail_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    product = ctx.get("product") or {}
    ref = ctx.get("reference_product") or {}
    design = ctx.get("design") or {}
    food = ctx.get("food") or {}
    unresolved: list[str] = []
    gaps: list[dict] = []

    dose = product.get("dosage")
    form = product.get("dosage_form")
    route = product.get("route") or design.get("route")
    test_name = product.get("trade_name") or product.get("inn")
    ref_name = ref.get("trade_name") or ref.get("inn")
    periods = design.get("periods")
    sequences = design.get("sequences")

    if not test_name:
        unresolved.append("{{PRODUCT.NAME}}")
        gaps.append(_gap("PROCEDURE", "Test product missing for dosing narrative"))
    if not dose:
        unresolved.append("{{PRODUCT.DOSAGE}}")
        gaps.append(_gap("PROCEDURE", "Dose missing for dosing narrative"))

    food_cond = food.get("condition")
    food_disp = resolve_display(str(food_cond), context="food") if food_cond else None
    if food_cond and food_disp == food_cond and find_raw_enums_in_text(str(food_cond)):
        food_disp = "{{FOOD.CONDITION}}"
        unresolved.append("{{FOOD.CONDITION}}")

    # Never invent meal kcal/fat/water
    meal_bits = []
    for forbidden_key in ("calories", "kcal", "fat_pct", "fat_percent", "water_ml", "meal_composition"):
        if food.get(forbidden_key) is not None:
            # Only render if present in canonical — do not invent; if present, include with provenance
            meal_bits.append(f"{forbidden_key}={food.get(forbidden_key)}")

    lines = [
        f"Тестовый препарат: {test_name or '{{PRODUCT.NAME}}'}; доза: {dose or '{{PRODUCT.DOSAGE}}'}"
        + (f"; форма: {form}" if form else "")
        + (f"; путь: {route}" if route else "")
        + ".",
    ]
    if ref_name:
        lines.append(f"Референтный препарат: {ref_name}.")
    if periods:
        lines.append(f"Число периодов: {periods}.")
    if sequences:
        lines.append(f"Последовательности: {sequences}.")
    if food_disp:
        lines.append(f"Условие пищи: {food_disp}.")
    if meal_bits:
        lines.append("Параметры приёма пищи (канонические): " + "; ".join(meal_bits) + ".")

    text = " ".join(lines)
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="PROC.DOSING",
                text=text,
                unresolved=unresolved,
                origin="SOURCE_DERIVED",
            ),
            resolution_status="RESOLVED" if not unresolved else "UNRESOLVED",
            display_as_final=not unresolved,
            content_type="CANONICAL_VALUE",
            canonical_source="product+design+food",
            knowledge_gaps=gaps,
        )
    ], [], unresolved


def gen_washout_procedure_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    washout = ctx.get("washout") or {}
    approved = _latest_approved(ctx, "WASHOUT")
    value = washout.get("selected_value")
    unit = washout.get("unit") or washout.get("selected_unit")
    decision_status = str(washout.get("decision_status") or washout.get("status") or "").upper()

    if value is None and approved:
        payload = approved.get("payload") or approved.get("decision_payload") or {}
        value = payload.get("selected_value") or payload.get("value")
        unit = unit or payload.get("unit")

    if value is None:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="PROC.WASHOUT.MISSING",
                    text="{{WASHOUT.VALUE}}",
                    unresolved=["{{WASHOUT.VALUE}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[_gap("WASHOUT", "Canonical/approved washout missing")],
            )
        ], [], ["{{WASHOUT.VALUE}}"]

    if decision_status == "PROPOSED" and not approved:
        text = f"[REVIEW REQUIRED] Предложенный washout: {value} {unit or ''}".strip()
        return [
            _enrich(
                _block(type_="TEXT", block_code="PROC.WASHOUT.PROPOSED", text=text, origin="SOURCE_DERIVED"),
                resolution_status="PROPOSED",
                display_as_final=False,
                content_type="CONDITION",
                knowledge_gaps=[
                    _gap("WASHOUT", "Washout is PROPOSED — not final without ExpertDecision", blocking=False)
                ],
            )
        ], [], []

    text = f"Период отмывки (washout): {value} {unit or ''}".strip()
    return [
        _enrich(
            _block(type_="TEXT", block_code="PROC.WASHOUT", text=text, origin="SOURCE_DERIVED"),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="CANONICAL_VALUE",
            canonical_source="washout",
        )
    ], [], []


def gen_food_restrictions_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    food = ctx.get("food") or {}
    cond = food.get("condition")
    if not cond:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="PROC.FOOD.MISSING",
                    text="{{FOOD.CONDITION}}",
                    unresolved=["{{FOOD.CONDITION}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[_gap("FOOD", "Food condition missing")],
            )
        ], [], ["{{FOOD.CONDITION}}"]

    disp = resolve_display(str(cond), context="food")
    # Do not invent calories/fat/water
    invented_keys = ("meal_kcal", "calories", "fat_pct", "water_volume_ml", "breakfast")
    extra_lines = []
    for k in invented_keys:
        if food.get(k) is not None:
            extra_lines.append(f"{k}={food[k]} (каноническое значение)")

    text = f"Условие приёма пищи: {disp}."
    if extra_lines:
        text += " " + " ".join(extra_lines)
    return [
        _enrich(
            _block(type_="TEXT", block_code="PROC.FOOD", text=text, origin="SOURCE_DERIVED"),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="CONDITION",
            canonical_source="food.condition",
        )
    ], [], []


def gen_period_12b2(period: int):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        design = ctx.get("design") or {}
        periods = int(design.get("periods") or 0)
        if period > periods > 0:
            return [
                _enrich(
                    _block(
                        type_="TEXT",
                        text=f"Период {period} не применим для текущего дизайна ({periods} период(ов)).",
                        origin="RULE_DERIVED",
                    ),
                    resolution_status="RESOLVED",
                    display_as_final=True,
                    content_type="CONDITION",
                )
            ], [], []

        sampling = get_canonical_sampling_plan(ctx)
        food = ctx.get("food") or {}
        food_disp = (
            resolve_display(str(food.get("condition")), context="food") if food.get("condition") else None
        )
        n_pts = sampling.points_per_period or len(sampling.points or [])
        times = [p.get("time_h") for p in (sampling.points or [])]
        text = (
            f"Период {period}: процедуры приёма препарата; "
            f"отбор крови по каноническому SamplingPlan ({n_pts} точек"
            + (f": {times}" if times else "")
            + ")."
        )
        if food_disp:
            text += f" Условие пищи: {food_disp}."
        return [
            _enrich(
                _block(type_="TEXT", block_code=f"PROC.PERIOD_{period}", text=text, origin="SOURCE_DERIVED"),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="PROCEDURE",
                canonical_source="sampling+design+food",
            )
        ], [], []

    return _inner


def gen_sample_prep_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    sp = _sample_processing_from_ctx(ctx)
    unresolved_fields = sp.unresolved_fields()
    lines = []
    if sp.sample_type:
        lines.append(f"Матрица/тип образца: {sp.sample_type}.")
    if sp.anticoagulant:
        lines.append(f"Антикоагулянт: {sp.anticoagulant}.")
    if sp.centrifugation:
        lines.append(f"Центрифугирование: {sp.centrifugation}.")
    if sp.storage:
        lines.append(f"Хранение: {sp.storage}.")
    if sp.processing_steps:
        lines.append("Шаги: " + "; ".join(sp.processing_steps) + ".")

    if not lines:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="PROC.SAMPLE_PREP.MISSING",
                    text="{{SAMPLE_PROCESSING.DEFINITION}}",
                    unresolved=["{{SAMPLE_PROCESSING.DEFINITION}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[
                    _gap(
                        "SAMPLE_PROCESSING",
                        "SampleProcessingDefinition empty — no anticoagulant/centrifugation defaults",
                    )
                ],
                content_type="PLACEHOLDER",
            )
        ], list(sp.source_ids), ["{{SAMPLE_PROCESSING.DEFINITION}}"]

    gaps = []
    if unresolved_fields:
        gaps.append(
            _gap(
                "SAMPLE_PROCESSING",
                f"Unresolved sample processing fields: {unresolved_fields}",
                importance="MEDIUM",
                blocking=False,
            )
        )
    text = "Подготовка образцов (канонический SampleProcessing/BioanalysisPlan): " + " ".join(lines)
    has_prov = bool(sp.source_ids or sp.evidence_claim_ids)
    if not has_prov:
        gaps.append(
            _gap(
                "SAMPLE_PROCESSING",
                "Sample processing values lack source_ids / evidence_claim_ids",
                importance="HIGH",
                blocking=True,
            )
        )
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="PROC.SAMPLE_PREP",
                text=text,
                origin="SOURCE_DERIVED",
                source_ids=list(sp.source_ids),
            ),
            resolution_status="RESOLVED" if has_prov and not unresolved_fields else "PROPOSED",
            display_as_final=bool(has_prov and not unresolved_fields),
            content_type="PROCEDURE",
            canonical_source="sample_processing",
            knowledge_gaps=gaps,
            evidence_claim_ids=list(sp.evidence_claim_ids),
        )
    ], list(sp.source_ids), []


def gen_contraception_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    meta = ctx.get("criteria_meta") or {}
    days = meta.get("contraception_days_from_smpc")
    evid = list(meta.get("smpc_evidence_claim_ids") or [])
    if days is None:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="PROC.CONTRACEPTION.GAP",
                    text="{{CONTRACEPTION.PERIOD}}",
                    unresolved=["{{CONTRACEPTION.PERIOD}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[
                    _gap(
                        "ELIGIBILITY",
                        "Contraception period requires SmPC/evidence source",
                        related_rule_id="CRIT-07",
                    )
                ],
            )
        ], [], ["{{CONTRACEPTION.PERIOD}}"]
    if not evid:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="PROC.CONTRACEPTION.NO_SOURCE",
                    text="{{CONTRACEPTION.SOURCE}}",
                    unresolved=["{{CONTRACEPTION.SOURCE}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[_gap("ELIGIBILITY", "Contraception days present without evidence ids")],
            )
        ], [], ["{{CONTRACEPTION.SOURCE}}"]
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="PROC.CONTRACEPTION",
                text=f"Требования к контрацепции: период {days} дн. (SmPC evidence).",
                origin="SOURCE_DERIVED",
                source_ids=evid,
                rule_id="CRIT-07",
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="EVIDENCE_DERIVED",
        )
    ], evid, []


# ---- Section 7: PK / Bioanalysis ----


def gen_eval_parameters_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    approved_analyte = _latest_approved(ctx, "ANALYTE_SELECTION")
    approved_pk = _latest_approved(ctx, "PK_PARAMETER_SET")
    analytes = list(ctx.get("analytes") or [])
    pk_rows = list(ctx.get("pk_parameters") or [])

    blocks: list[dict] = []
    gaps: list[dict] = []

    if not analytes:
        gaps.append(_gap("ANALYTE", "No analytes in canonical study"))
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="PK.ANALYTE.MISSING",
                    text="{{ANALYTE.SELECTION}}",
                    unresolved=["{{ANALYTE.SELECTION}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=gaps,
            )
        )
    else:
        names = ", ".join(a.get("name") or a.get("code") or "?" for a in analytes)
        if approved_analyte:
            text = f"Фармакокинетический анализ будет выполнен для аналита(ов): {names}."
            blocks.append(
                _enrich(
                    _block(
                        type_="TEXT",
                        block_code="PK.ANALYTE.APPROVED",
                        text=text,
                        origin="EXPERT_DECISION",
                        source_ids=[str(approved_analyte.get("id") or "")],
                    ),
                    resolution_status="RESOLVED",
                    display_as_final=True,
                    content_type="EXPERT_DECISION",
                    expert_decision_id=str(approved_analyte.get("id") or ""),
                )
            )
        else:
            text = f"[REVIEW REQUIRED] Аналиты (PROPOSED / pending AnalyteSelectionDecision): {names}."
            blocks.append(
                _enrich(
                    _block(type_="TEXT", block_code="PK.ANALYTE.PROPOSED", text=text, origin="SOURCE_DERIVED"),
                    resolution_status="PROPOSED",
                    display_as_final=False,
                    knowledge_gaps=[
                        _gap("ANALYTE", "AnalyteSelectionDecision not APPROVED — not final")
                    ],
                )
            )

    # PK profile: prefer study pk_parameters; else standard proposed profile
    profile_params = []
    if pk_rows:
        for row in pk_rows:
            code = str(row.get("parameter_code") or row.get("code") or "")
            metric = resolve_auc_metric_type(code) or resolve_auc_metric_type(row.get("auc_metric_type"))
            if metric:
                label = display_auc_metric(metric)
            else:
                label = resolve_display(code, context="pk", fallback=code) if code else "{{PK.PARAMETER}}"
            profile_params.append({"code": code, "display": label, "metric": metric})
        status = "RESOLVED" if approved_pk else "PROPOSED"
        final = bool(approved_pk)
    else:
        profile = standard_pk_profile()
        for p in profile.parameters:
            metric = p.auc_metric_type
            label = display_auc_metric(metric) if metric else p.display_name
            profile_params.append({"code": p.code, "display": label, "metric": metric})
        status = "PROPOSED"
        final = False
        gaps.append(
            _gap(
                "PK",
                "Using STANDARD_PROPOSED PK profile — ExpertDecision PK_PARAMETER_SET required for final",
                importance="MEDIUM",
                blocking=False,
            )
        )

    # Ensure AUC0-x and AUC0-72 are distinct when both present
    displays = [p["display"] for p in profile_params]
    param_line = "Основными ФК параметрами являются: " + ", ".join(displays) + "."
    blocks.append(
        _enrich(
            _block(
                type_="TEXT",
                block_code="PK.PARAMETERS",
                text=param_line,
                origin="SOURCE_DERIVED" if pk_rows else "RULE_DERIVED",
            ),
            resolution_status=status,
            display_as_final=final,
            content_type="CANONICAL_VALUE" if final else "CONDITION",
            knowledge_gaps=gaps,
            auc_displays=displays,
        )
    )
    blocks.append(
        _enrich(
            _block(type_="TABLE", table_key="PK_PARAMETERS", origin="SOURCE_DERIVED"),
            resolution_status=status,
            display_as_final=final,
            content_type="TABLE",
        )
    )
    if len(analytes) > 1:
        names = ", ".join(a.get("name") or "{{ANALYTE.NAME}}" for a in analytes)
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="MULTI_ANALYTE_NOTE",
                    text=(
                        f"В исследовании оценивается более одного аналита ({len(analytes)}): {names}."
                    ),
                    origin="SOURCE_DERIVED",
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
                canonical_source="analytes",
            )
        )
    return blocks, [], []


def gen_eval_methods_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    sampling = get_canonical_sampling_plan(ctx)
    n = sampling.points_per_period or len(sampling.points or [])
    times = [p.get("time_h") for p in (sampling.points or [])]
    obs = ctx.get("observation") or {}
    dur = obs.get("selected_duration") or variables.get("observation_duration")
    unit = obs.get("unit") or variables.get("observation_unit") or "h"
    if not times and not n:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="PK.METHODS.MISSING",
                    text="{{SAMPLING.POINTS}}",
                    unresolved=["{{SAMPLING.POINTS}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[_gap("SAMPLING", "Canonical SamplingPlan missing for §7.2")],
            )
        ], [], ["{{SAMPLING.POINTS}}"]
    text = (
        f"Оценка PK выполняется по единому каноническому SamplingPlan "
        f"({n} точек на период: {times})"
    )
    if dur is not None:
        text += f" в течение {dur} {unit}"
    text += "."
    return [
        _enrich(
            _block(type_="TEXT", block_code="PK.METHODS", text=text, origin="SOURCE_DERIVED"),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="CANONICAL_VALUE",
            canonical_source="sampling.points",
        )
    ], [], []


def gen_bioanalysis_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    plan = bioanalysis_plan_from_dict(ctx.get("bioanalysis_plan"))
    if plan.status == "MISSING" and not any(
        getattr(plan, f) for f in ("analytical_method", "matrix", "lloq", "validation_status")
    ):
        plan = empty_bioanalysis_plan()

    analytes = ctx.get("analytes") or []
    names = ", ".join(a.get("name") or "?" for a in analytes) or None
    lines = []
    if names:
        lines.append(f"Аналиты: {names}.")
    if plan.matrix:
        lines.append(f"Матрица: {plan.matrix}.")
    if plan.analytical_method:
        lines.append(f"Метод: {plan.analytical_method}.")
    if plan.validation_status:
        lines.append(f"Статус валидации: {plan.validation_status}.")

    # Never invent HPLC-MS/MS or LLOQ
    if not plan.analytical_method:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="BIO.METHOD.MISSING",
                    text=(f"Биоаналитическое определение: {names}. " if names else "")
                    + "{{BIOANALYSIS.METHOD}}",
                    unresolved=["{{BIOANALYSIS.METHOD}}"],
                    source_ids=list(plan.source_ids),
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[
                    _gap("BIOANALYSIS", "analytical_method missing — no HPLC/LLOQ defaults")
                ],
                content_type="PLACEHOLDER",
            )
        ], list(plan.source_ids), ["{{BIOANALYSIS.METHOD}}"]

    status = str(plan.status or "").upper()
    if status in {"PROPOSED", "MISSING", ""}:
        res = "PROPOSED"
        final = False
    else:
        res = "RESOLVED"
        final = True
    if not plan.source_ids and res == "RESOLVED":
        # study-specific without provenance
        res = "PROPOSED"
        final = False

    text = " ".join(lines)
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="BIO.METHOD",
                text=text,
                origin="SOURCE_DERIVED",
                source_ids=list(plan.source_ids),
            ),
            resolution_status=res,
            display_as_final=final,
            content_type="EVIDENCE_DERIVED" if plan.source_ids else "CONDITION",
            canonical_source="bioanalysis_plan",
            knowledge_gaps=[]
            if final
            else [_gap("BIOANALYSIS", "BioanalysisPlan not final / missing provenance", blocking=False)],
        )
    ], list(plan.source_ids), []


def gen_bio_detail_12b2(kind: str):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        plan = bioanalysis_plan_from_dict(ctx.get("bioanalysis_plan"))
        field_map = {
            "method": ("analytical_method", "{{BIOANALYSIS.METHOD}}"),
            "validation": ("validation_status", "{{BIOANALYSIS.VALIDATION}}"),
            "analysis": ("sample_preparation", "{{BIOANALYSIS.SAMPLE_ANALYSIS}}"),
            "acceptance": ("acceptance_criteria", "{{BIOANALYSIS.RUN_ACCEPTANCE}}"),
        }
        field, marker = field_map.get(kind, (None, "{{BIOANALYSIS.FIELD}}"))
        val = getattr(plan, field, None) if field else None
        if not val:
            return [
                _enrich(
                    _block(
                        type_="TEXT",
                        block_code=f"BIO.{kind.upper()}.MISSING",
                        text=marker,
                        unresolved=[marker],
                    ),
                    resolution_status="UNRESOLVED",
                    display_as_final=False,
                    knowledge_gaps=[_gap("BIOANALYSIS", f"{field or kind} missing — no invented defaults")],
                )
            ], [], [marker]
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code=f"BIO.{kind.upper()}",
                    text=str(val),
                    origin="SOURCE_DERIVED",
                    source_ids=list(plan.source_ids),
                ),
                resolution_status="RESOLVED" if plan.source_ids else "PROPOSED",
                display_as_final=bool(plan.source_ids),
                content_type="EVIDENCE_DERIVED" if plan.source_ids else "CONDITION",
            )
        ], list(plan.source_ids), []

    return _inner


# ---- Section 8: Safety ----


def _safety_block(code: str, title: str, plan_attr: str, ctx: dict) -> tuple[list[dict], list[str], list[str]]:
    plan = safety_plan_from_dict(ctx.get("safety_plan"))
    block = getattr(plan, plan_attr, None)
    enabled = plan_attr in plan.enabled_categories()
    schedule_view = build_safety_procedure_view(ctx)
    timing_items = [
        f"{p.sequence_order}. {p.name}"
        for p in schedule_view.procedures
        if plan_attr.upper() in str(p.category).upper()
        or (plan_attr == "vital_signs" and p.category == "VITALS")
        or (plan_attr == "physical_exam" and "EXAM" in str(p.category).upper())
    ]

    if not enabled and not block:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code=f"SAFETY.{code}.UNSET",
                    text=f"{{{{SAFETY.{code}}}}}",
                    unresolved=[f"{{{{SAFETY.{code}}}}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[
                    _gap(
                        "SAFETY",
                        f"{title} not defined in SafetyPlan — assessment not invented",
                    )
                ],
                content_type="PLACEHOLDER",
            )
        ], [], [f"{{{{SAFETY.{code}}}}}"]

    # Present but unverified library → PROPOSED
    status = str(plan.status or "").upper()
    if status in {"MISSING", "PROPOSED", "UNVERIFIED", ""}:
        res = "PROPOSED"
        final = False
    else:
        res = "RESOLVED"
        final = True

    detail = ""
    if isinstance(block, dict):
        items = block.get("items") or block.get("assessments") or []
        if items:
            detail = " " + "; ".join(str(i) for i in items)
        # timing must come from schedule, not invented
        if block.get("timing") or block.get("times"):
            detail += f" Время (из SafetyPlan): {block.get('timing') or block.get('times')}."

    text = f"{title}:{detail}" if detail else f"{title}: включено в SafetyPlan."
    blocks = [
        _enrich(
            _block(
                type_="TEXT",
                block_code=f"SAFETY.{code}",
                text=text,
                origin="SOURCE_DERIVED",
                source_ids=list(plan.source_ids),
            ),
            resolution_status=res,
            display_as_final=final,
            content_type="CANONICAL_VALUE" if final else "CONDITION",
            knowledge_gaps=[]
            if final
            else [
                _gap(
                    "SAFETY",
                    f"{title} is unverified/PROPOSED — not final safety policy",
                    importance="MEDIUM",
                    blocking=False,
                )
            ],
        )
    ]
    if timing_items:
        blocks.append(
            _enrich(
                _block(
                    type_="NUMBERED_LIST",
                    block_code=f"SAFETY.{code}.SCHEDULE",
                    items=timing_items,
                    origin="SOURCE_DERIVED",
                ),
                resolution_status=res,
                display_as_final=final,
                content_type="PROCEDURE",
                canonical_source="procedure_schedule",
            )
        )
    return blocks, list(plan.source_ids), []


def gen_safety_standard_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    plan = safety_plan_from_dict(ctx.get("safety_plan"))
    cats = plan.enabled_categories()
    if not cats:
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="SAFETY.PARAMS.MISSING",
                    text="{{SAFETY.PLAN}}",
                    unresolved=["{{SAFETY.PLAN}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[
                    _gap("SAFETY", "SafetyPlan empty — standard checklist not invented")
                ],
            )
        ], [], ["{{SAFETY.PLAN}}"]
    text = "Параметры безопасности (из SafetyPlan): " + ", ".join(cats) + "."
    status = str(plan.status or "").upper()
    final = status not in {"MISSING", "PROPOSED", "UNVERIFIED", ""}
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="SAFETY.PARAMS",
                text=text,
                origin="SOURCE_DERIVED",
                source_ids=list(plan.source_ids),
            ),
            resolution_status="RESOLVED" if final else "PROPOSED",
            display_as_final=final,
            content_type="CANONICAL_VALUE" if final else "CONDITION",
        )
    ], list(plan.source_ids), []


def gen_safety_methods_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    view = build_safety_procedure_view(ctx)
    if not view.procedures and not view.safety_plan.enabled_categories():
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="SAFETY.METHODS.MISSING",
                    text="{{SAFETY.METHODS}}",
                    unresolved=["{{SAFETY.METHODS}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[_gap("SAFETY", "No safety methods/schedule available")],
            )
        ], [], ["{{SAFETY.METHODS}}"]
    items = [f"{p.sequence_order}. {p.name} [{p.category}]" for p in view.procedures]
    if not items:
        items = [f"Категория SafetyPlan: {c}" for c in view.safety_plan.enabled_categories()]
    status = str(view.safety_plan.status or "").upper()
    final = status not in {"MISSING", "PROPOSED", "UNVERIFIED", ""}
    return [
        _enrich(
            _block(
                type_="NUMBERED_LIST",
                block_code="SAFETY.METHODS",
                items=items,
                origin="SOURCE_DERIVED",
            ),
            resolution_status="RESOLVED" if final else "PROPOSED",
            display_as_final=final,
            content_type="PROCEDURE",
            canonical_source="safety_plan+procedure_schedule",
        )
    ], list(view.safety_plan.source_ids), []


def gen_physical_exam_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return _safety_block("PHYS_EXAM", "Физикальное обследование", "physical_exam", ctx)


def gen_vital_signs_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return _safety_block("VITALS", "Жизненные показатели", "vital_signs", ctx)


def gen_safety_labs_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return _safety_block("LABS", "Лабораторные исследования безопасности", "laboratory_tests", ctx)


def gen_ae_framework_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    plan = safety_plan_from_dict(ctx.get("safety_plan"))
    if "AE" not in plan.enabled_categories() and "SAE" not in plan.enabled_categories():
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="SAFETY.AE.MISSING",
                    text="{{SAFETY.AE}}",
                    unresolved=["{{SAFETY.AE}}"],
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[_gap("SAFETY", "AE/SAE not defined in SafetyPlan — procedure not invented")],
            )
        ], [], ["{{SAFETY.AE}}"]
    parts = []
    if "AE" in plan.enabled_categories():
        parts.append("AE")
    if "SAE" in plan.enabled_categories():
        parts.append("SAE")
    text = "Регистрация " + "/".join(parts) + " согласно SafetyPlan."
    status = str(plan.status or "").upper()
    final = status not in {"MISSING", "PROPOSED", "UNVERIFIED", ""}
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="SAFETY.AE",
                text=text,
                origin="SOURCE_DERIVED",
                source_ids=list(plan.source_ids),
            ),
            resolution_status="RESOLVED" if final else "PROPOSED",
            display_as_final=final,
            content_type="CANONICAL_VALUE" if final else "CONDITION",
        )
    ], list(plan.source_ids), []


def gen_ae_followup_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return _safety_block("FOLLOW_UP", "Последующее наблюдение", "follow_up", ctx)


def gen_pregnancy_12b2(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return _safety_block("PREGNANCY", "Беременность", "pregnancy", ctx)


CORE_12B2_GENERATORS: dict[str, Any] = {
    "inclusion": gen_eligibility_category_12b2("inclusion"),
    "non_inclusion": gen_eligibility_category_12b2("non_inclusion"),
    "exclusion": gen_eligibility_category_12b2("exclusion"),
    "procedures_timeline": gen_procedures_timeline_12b2,
    "treatment_detail": gen_treatment_detail_12b2,
    "washout_procedure": gen_washout_procedure_12b2,
    "food_restrictions": gen_food_restrictions_12b2,
    "period_1": gen_period_12b2(1),
    "period_2": gen_period_12b2(2),
    "sample_prep": gen_sample_prep_12b2,
    "contraception": gen_contraception_12b2,
    "eval_parameters": gen_eval_parameters_12b2,
    "eval_methods_timing": gen_eval_methods_12b2,
    "bioanalysis": gen_bioanalysis_12b2,
    "analytical_method": gen_bio_detail_12b2("method"),
    "bio_validation": gen_bio_detail_12b2("validation"),
    "sample_analysis": gen_bio_detail_12b2("analysis"),
    "run_acceptance": gen_bio_detail_12b2("acceptance"),
    "safety_standard": gen_safety_standard_12b2,
    "safety_methods": gen_safety_methods_12b2,
    "physical_exam": gen_physical_exam_12b2,
    "vital_signs": gen_vital_signs_12b2,
    "safety_labs": gen_safety_labs_12b2,
    "ae_framework": gen_ae_framework_12b2,
    "ae_followup": gen_ae_followup_12b2,
    "pregnancy": gen_pregnancy_12b2,
}
