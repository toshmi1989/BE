"""Phase 12B.3 — sections 9–15 generators.

No new statistical algorithms. No invented defaults (alpha/power/dropout/BE 80–125).
No Potvin B/C numerics. No template-as-truth. No global heading overlay.
"""

from __future__ import annotations

from typing import Any

from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.content_resolver import filter_decision_for_render
from app.domain.display_value_registry import find_raw_enums_in_text, resolve_display
from app.domain.org_render import (
    financing_block,
    insurance_block,
    orgs_by_roles,
    publication_block,
    resolve_sponsor,
)
from app.domain.protocol_consistency import find_unresolved_markers
from app.domain.protocol_sections import SectionDef
from app.domain.static_blocks import STATIC_VERIFIED

_ETHICS_ROLES = {"ETHICS_COMMITTEE", "IEC", "IRB", "ETHICS"}

_POLICY_FIELD_MAP: dict[str, tuple[str, str, str]] = {
    # kind -> (ctx/config field, marker, gap question)
    "stopping": ("stopping_rules", "{{STATISTICS.STOPPING_RULES}}", "Stopping rules missing — not invented"),
    "missing": ("missing_data_policy", "{{STATISTICS.MISSING_DATA}}", "Missing-data policy missing — not invented"),
    "deviations": ("sap_deviations", "{{STATISTICS.SAP_DEVIATIONS}}", "SAP deviation policy missing — not invented"),
    "outliers": ("outliers_policy", "{{STATISTICS.OUTLIERS}}", "Outlier policy missing — not invented"),
    "descriptive": ("descriptive_stats", "{{STATISTICS.DESCRIPTIVE}}", "Descriptive-stats policy missing — not invented"),
    "anova": ("anova_methods", "{{STATISTICS.ANOVA}}", "ANOVA / analysis methods missing — not invented"),
    "safety_stats": ("safety_analysis", "{{STATISTICS.SAFETY_ANALYSIS}}", "Safety analysis policy missing — not invented"),
    "populations": ("analysis_populations", "{{STATISTICS.POPULATIONS}}", "Analysis populations policy missing — not invented"),
}

_POLICY_DECISION_TYPES: dict[str, str] = {
    "stopping": "STOPPING_RULES",
    "missing": "MISSING_DATA_POLICY",
    "deviations": "SAP_DEVIATIONS",
    "outliers": "OUTLIERS_POLICY",
    "descriptive": "DESCRIPTIVE_STATS",
    "anova": "ANOVA_METHODS",
    "safety_stats": "SAFETY_STATS",
    "populations": "ANALYSIS_POPULATIONS",
}


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
        "STATIC_VERIFIED"
        if block.get("origin") == "STATIC_VERIFIED"
        else ("CANONICAL_VALUE" if display_as_final else "PLACEHOLDER")
    )
    for k, v in extra.items():
        block[k] = v
    text = block.get("text")
    if text and find_raw_enums_in_text(str(text)):
        block["text"] = "{{DISPLAY.ENUM}}"
        block["unresolved"] = list(set((block.get("unresolved") or []) + ["{{DISPLAY.ENUM}}"]))
        block["resolution_status"] = "UNRESOLVED"
        block["display_as_final"] = False
    scrubbed = []
    for it in list(block.get("items") or []):
        if find_raw_enums_in_text(str(it)):
            block["resolution_status"] = "UNRESOLVED"
            block["display_as_final"] = False
            block["unresolved"] = list(set((block.get("unresolved") or []) + ["{{DISPLAY.ENUM}}"]))
            continue
        scrubbed.append(it)
    if block.get("items") is not None:
        block["items"] = scrubbed
    return block


def _gap(domain: str, question: str, *, importance: str = "HIGH", blocking: bool = True, **extra: Any) -> dict:
    g = {"domain": domain, "question": question, "importance": importance, "blocking": blocking}
    g.update(extra)
    return g


def _fmt_pct(value: float | int | None) -> str | None:
    if value is None:
        return None
    v = float(value)
    if 0 < v <= 1:
        return f"{v * 100:.0f}%"
    return f"{v:g}%"


def _fmt_alpha(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{float(value):g}".replace(".", ",")


def _cfg(ctx: dict) -> dict:
    return dict(ctx.get("statistical_config") or {})


def _ss(ctx: dict) -> dict:
    return dict(ctx.get("sample_size") or {})


def _cv_selection(ctx: dict) -> dict:
    return dict(ctx.get("cv_selection") or {})


def _admin(ctx: dict) -> dict:
    return dict(ctx.get("study_administration") or {})


def _source_ids(*entities: dict | None) -> list[str]:
    out: list[str] = []
    for ent in entities:
        if not ent:
            continue
        if ent.get("id"):
            out.append(str(ent["id"]))
        for sid in ent.get("source_ids") or []:
            out.append(str(sid))
        prov = ent.get("provenance") or {}
        for sid in prov.get("source_ids") or []:
            out.append(str(sid))
    return list(dict.fromkeys(out))


def _payload(decision: dict | None) -> dict:
    if not decision:
        return {}
    return dict(decision.get("payload") or decision.get("decision_payload") or {})


def _unresolved_block(
    *,
    block_code: str,
    marker: str,
    domain: str,
    question: str,
    **gap_extra: Any,
) -> tuple[list[dict], list[str], list[str]]:
    gaps = [_gap(domain, question, **gap_extra)]
    return (
        [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code=block_code,
                    text=marker,
                    unresolved=[marker],
                    origin="PLACEHOLDER",
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=gaps,
                content_type="PLACEHOLDER",
            )
        ],
        [],
        [marker],
    )


def _mentions_potvin(text: str | None) -> bool:
    if not text:
        return False
    t = str(text).lower()
    return "potvin" in t


def _design_display(ctx: dict, variables: dict) -> tuple[str | None, list[str]]:
    design = ctx.get("design") or {}
    code = design.get("type") or variables.get("design_type_code")
    unresolved: list[str] = []
    if not code:
        unresolved.append("{{DESIGN.TYPE}}")
        return None, unresolved
    disp = resolve_display(str(code), context="design", fallback=str(code))
    if find_raw_enums_in_text(disp):
        unresolved.append("{{DESIGN.TYPE}}")
        return "{{DESIGN.TYPE}}", unresolved
    return disp, unresolved


# ---- Section 9: Statistics ----


def gen_statistical_method_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    cfg = _cfg(ctx)
    design_disp, design_unres = _design_display(ctx, variables)
    gaps: list[dict] = []
    unresolved: list[str] = list(design_unres)
    parts: list[str] = []

    method = cfg.get("analysis_method") or cfg.get("method")
    transform = cfg.get("transformation")
    software = cfg.get("software")
    lo = cfg.get("be_lower")
    hi = cfg.get("be_upper")
    alpha = cfg.get("alpha")

    if design_disp and design_disp != "{{DESIGN.TYPE}}":
        parts.append(f"Основной статистический анализ выполняется в рамках дизайна ({design_disp}).")
    elif "{{DESIGN.TYPE}}" in unresolved:
        gaps.append(_gap("STATISTICS", "Design type missing for statistical method narrative"))

    if method:
        parts.append(f"Метод анализа: {method}.")
    else:
        unresolved.append("{{STATISTICS.ANALYSIS_METHOD}}")
        gaps.append(_gap("STATISTICS", "analysis_method missing — not invented"))

    if transform:
        parts.append(f"Преобразование: {resolve_display(str(transform), context='stats', fallback=str(transform))}.")

    if alpha is not None:
        a = _fmt_alpha(float(alpha))
        parts.append(f"Уровень значимости α={a}.")
    # intentionally no 0.05 default

    if lo is not None and hi is not None:
        parts.append(
            f"Критерий BE: 90% ДИ отношения средних в пределах "
            f"{float(lo) * 100:g}%–{float(hi) * 100:g}%."
        )
    else:
        unresolved.append("{{STATISTICS.BE_LIMITS}}")
        gaps.append(_gap("STATISTICS", "BE limits missing — 80–125% not invented"))

    if software:
        parts.append(f"ПО: {software}.")

    # Adaptive / Potvin: render only if approved; never invent algorithms
    design = ctx.get("design") or {}
    design_type = str(design.get("type") or "").upper()
    adaptive = "ADAPTIVE" in design_type or bool(design.get("stage_configuration"))
    method_str = str(method or "")
    potvin_like = _mentions_potvin(method_str) or _mentions_potvin(cfg.get("algorithm_version"))
    approved_adaptive = _latest_approved(ctx, "ADAPTIVE_STATS") or _latest_approved(ctx, "POTVIN_METHOD")
    if adaptive or potvin_like:
        if approved_adaptive:
            payload = _payload(approved_adaptive)
            note = payload.get("text") or payload.get("method") or method
            if note:
                parts.append(f"Адаптивная/approved конфигурация: {note}.")
        else:
            gaps.append(
                _gap(
                    "STATISTICS",
                    "Adaptive/Potvin configuration unverified — no Potvin algorithm invented",
                    related_rule_id="STAT.POTVIN_UNVERIFIED",
                )
            )
            unresolved.append("{{STATISTICS.ADAPTIVE}}")

    if not parts:
        return _unresolved_block(
            block_code="STAT.METHOD.MISSING",
            marker="{{STATISTICS.METHOD}}",
            domain="STATISTICS",
            question="Statistical method inputs missing — no invented narrative",
        )

    text = " ".join(parts)
    src = _source_ids(cfg)
    final = len(unresolved) == 0
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="STAT.METHOD",
                text=text,
                unresolved=unresolved,
                origin="SOURCE_DERIVED",
                source_ids=src,
                rule_id="STATISTICS.METHOD",
            ),
            resolution_status="RESOLVED" if final else ("PROPOSED" if parts else "UNRESOLVED"),
            display_as_final=final,
            content_type="CANONICAL_VALUE" if final else "PLACEHOLDER",
            canonical_source="statistical_config+design",
            knowledge_gaps=gaps,
        )
    ], src, unresolved


def gen_sample_size_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    counts = get_canonical_subject_counts(ctx)
    ss = _ss(ctx)
    cfg = _cfg(ctx)
    cv = _cv_selection(ctx)
    gaps: list[dict] = []
    unresolved: list[str] = []
    blocks: list[dict] = []
    src: list[str] = []

    # SubjectPlan owns protocol randomized N — never substitute SampleSizeCalculation
    calc_eval = counts.sample_size_evaluable_n if counts.sample_size_evaluable_n is not None else ss.get("evaluable_n")
    calc_rand = counts.sample_size_randomized_n if counts.sample_size_randomized_n is not None else ss.get("randomized_n")

    # Prefer SubjectPlan for displayed protocol N; calculated values labeled separately
    protocol_eval = counts.evaluable_n
    protocol_rand = counts.randomized_n if counts.source == "subject_plan" else None
    if counts.source != "subject_plan":
        # Fallback path: evaluable may come from sample_size_fallback but randomized stays unresolved
        if counts.source == "sample_size_fallback":
            protocol_eval = counts.evaluable_n
            protocol_rand = None
            gaps.append(
                _gap(
                    "STATISTICS",
                    "SubjectPlan randomized N missing — SampleSizeCalculation must not substitute randomized N",
                    related_rule_id="STAT.N_RANDOMIZED_MISSING",
                )
            )
            unresolved.append("{{SUBJECTS.RANDOMIZED_N}}")
        else:
            gaps.append(
                _gap(
                    "STATISTICS",
                    "SubjectPlan / sample size N missing",
                    related_rule_id="STAT.N_CALCULATED_MISSING",
                )
            )
            unresolved.extend(["{{SUBJECTS.EVALUABLE_N}}", "{{SUBJECTS.RANDOMIZED_N}}"])

    if protocol_rand is None and counts.source == "subject_plan" and counts.randomized_n is None:
        gaps.append(
            _gap(
                "STATISTICS",
                "SubjectPlan.planned_randomized_n missing",
                related_rule_id="STAT.N_RANDOMIZED_MISSING",
            )
        )
        unresolved.append("{{SUBJECTS.RANDOMIZED_N}}")

    if protocol_eval is None:
        gaps.append(
            _gap(
                "STATISTICS",
                "Evaluable N missing from SubjectPlan/canonical",
                related_rule_id="STAT.N_CALCULATED_MISSING",
            )
        )
        unresolved.append("{{SUBJECTS.EVALUABLE_N}}")

    if counts.diverges_from_sample_size:
        gaps.append(
            _gap(
                "STATISTICS",
                "SubjectPlan N diverges from SampleSizeCalculation (semantic mismatch)",
                related_rule_id="STAT.N_SEMANTIC_MISMATCH",
            )
        )

    # Power / alpha / dropout — only if present (no defaults)
    power = cfg.get("power")
    if power is None and isinstance(ss.get("inputs_snapshot"), dict):
        power = ss["inputs_snapshot"].get("power")
    alpha = cfg.get("alpha")
    if alpha is None and isinstance(ss.get("inputs_snapshot"), dict):
        alpha = ss["inputs_snapshot"].get("alpha")
    dropout = None
    if isinstance(ss.get("inputs_snapshot"), dict):
        dropout = ss["inputs_snapshot"].get("dropout_pct")
    if dropout is None:
        dropout = ss.get("dropout_pct")

    power_s = _fmt_pct(power)
    alpha_s = _fmt_alpha(float(alpha)) if alpha is not None else None
    dropout_s = _fmt_pct(dropout)

    if power is None:
        gaps.append(_gap("STATISTICS", "Power missing — 80% not invented", importance="MEDIUM", blocking=False))
    if alpha is None:
        gaps.append(_gap("STATISTICS", "Alpha missing for sample-size narrative — 0.05 not invented", importance="MEDIUM", blocking=False))
    if dropout is None:
        gaps.append(_gap("STATISTICS", "Dropout % missing — not invented", importance="MEDIUM", blocking=False))

    # CV + provenance
    selected_cv = cv.get("selected_cv")
    if selected_cv is None:
        selected_cv = ss.get("selected_cv") or ss.get("cv_used")
    cv_param = cv.get("parameter") or ss.get("parameter")
    source_study_ids = list(cv.get("source_study_ids") or [])
    if selected_cv is None:
        gaps.append(
            _gap("STATISTICS", "CV missing for sample-size rationale", related_rule_id="STAT.CV_MISSING")
        )
        unresolved.append("{{STATISTICS.CV}}")
    elif not source_study_ids:
        gaps.append(
            _gap(
                "STATISTICS",
                "CV present without source_study_ids provenance",
                related_rule_id="STAT.CV_MISSING_SOURCE",
            )
        )

    lines: list[str] = []
    eval_disp = str(protocol_eval) if protocol_eval is not None else "{{SUBJECTS.EVALUABLE_N}}"
    rand_disp = str(protocol_rand) if protocol_rand is not None else "{{SUBJECTS.RANDOMIZED_N}}"
    lines.append(
        f"Планируемое число субъектов (SubjectPlan): оцениваемых субъектов N={eval_disp}; "
        f"рандомизированных N={rand_disp}."
    )
    if calc_eval is not None or calc_rand is not None:
        # Keep calculated values distinct — never presented as SubjectPlan randomized N
        calc_bits = []
        if calc_eval is not None:
            calc_bits.append(f"evaluable_n={calc_eval}")
        if calc_rand is not None:
            calc_bits.append(f"randomized_n={calc_rand} (SampleSizeCalculation, не SubjectPlan)")
        lines.append("Результаты расчёта SampleSizeCalculation: " + ", ".join(calc_bits) + ".")
        if (
            counts.source == "subject_plan"
            and counts.randomized_n is not None
            and calc_rand is not None
            and int(counts.randomized_n) != int(calc_rand)
        ):
            lines.append(
                f"Семантическое различие: SubjectPlan.randomized_n={counts.randomized_n} ≠ "
                f"SampleSizeCalculation.randomized_n={calc_rand}."
            )

    rationals: list[str] = []
    if power_s:
        rationals.append(f"мощность {power_s}")
    if alpha_s:
        rationals.append(f"α={alpha_s}")
    if dropout_s:
        rationals.append(f"dropout {dropout_s}")
    if selected_cv is not None:
        cv_txt = f"CVintra={selected_cv:g}%"
        if cv_param:
            cv_txt += f" ({cv_param})"
        rationals.append(cv_txt)
    if rationals:
        lines.append("Расчёт размера выборки выполнен с учётом: " + "; ".join(rationals) + ".")
    if source_study_ids:
        lines.append("Источники CV (source_study_ids): " + ", ".join(str(x) for x in source_study_ids) + ".")
        src.extend(str(x) for x in source_study_ids)

    method = ss.get("method") or ss.get("algorithm_version")
    if method and _mentions_potvin(str(method)):
        approved = _latest_approved(ctx, "POTVIN_METHOD") or _latest_approved(ctx, "ADAPTIVE_STATS")
        if not approved:
            gaps.append(
                _gap(
                    "STATISTICS",
                    "Potvin/adaptive sample-size method unverified — algorithm not invented",
                    related_rule_id="STAT.POTVIN_UNVERIFIED",
                )
            )
            unresolved.append("{{STATISTICS.POTVIN}}")
        else:
            lines.append(f"Утверждённый метод: {method}.")

    text = " ".join(lines)
    src.extend(_source_ids(ss, cv, cfg))
    src = list(dict.fromkeys(src))

    # Not final if unresolved critical N or CV provenance missing when CV used
    # Semantic mismatch SubjectPlan vs SampleSizeCalculation is documented, not a silent substitute
    critical_unres = [
        u
        for u in unresolved
        if u
        in {
            "{{SUBJECTS.RANDOMIZED_N}}",
            "{{SUBJECTS.EVALUABLE_N}}",
            "{{STATISTICS.CV}}",
            "{{STATISTICS.POTVIN}}",
        }
    ]
    cv_prov_ok = selected_cv is None or bool(source_study_ids)
    final = not critical_unres and cv_prov_ok

    blocks.append(
        _enrich(
            _block(
                type_="TEXT",
                block_code="STAT.SAMPLE_SIZE",
                text=text,
                unresolved=list(dict.fromkeys(unresolved)),
                origin="CALCULATED",
                rule_id="STATISTICS.SAMPLE_SIZE",
                source_ids=src,
            ),
            resolution_status="RESOLVED" if final else "UNRESOLVED",
            display_as_final=final,
            content_type="CANONICAL_VALUE" if final else "PLACEHOLDER",
            canonical_source="subject_plan+sample_size+cv_selection",
            knowledge_gaps=gaps,
            subject_plan_randomized_n=protocol_rand,
            sample_size_randomized_n=int(calc_rand) if calc_rand is not None else None,
            sample_size_evaluable_n=int(calc_eval) if calc_eval is not None else None,
            diverges_from_sample_size=counts.diverges_from_sample_size,
            cv_source_study_ids=source_study_ids,
        )
    )
    # Only emit CV_EVIDENCE TABLE when registry will include it (cv_studies / selection rows).
    # Emitting an orphan table_key caused QA.TABLE.UNRESOLVED (table_errors=1).
    from app.domain.protocol_tables import build_tables as _build_tables

    if any(t.get("table_key") == "CV_EVIDENCE" for t in _build_tables(ctx, consistency)):
        blocks.append(
            _enrich(
                _block(type_="TABLE", table_key="CV_EVIDENCE", origin="SOURCE_DERIVED"),
                resolution_status="PROPOSED" if not source_study_ids else "RESOLVED",
                display_as_final=bool(source_study_ids),
                content_type="TABLE",
            )
        )
    blocks.append(
        _enrich(
            _block(
                type_="REFERENCE",
                target_type="section",
                target_id="SYNOPSIS",
                display_text="см. Synopsis (N)",
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="REFERENCE",
        )
    )
    return blocks, src, list(dict.fromkeys(unresolved))


def gen_alpha_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    cfg = _cfg(ctx)
    alpha = cfg.get("alpha")
    approved = _latest_approved(ctx, "STATISTICAL_ALPHA") or _latest_approved(ctx, "STATISTICAL_CONFIG")
    if alpha is None and approved:
        alpha = _payload(approved).get("alpha")
    if alpha is None:
        return _unresolved_block(
            block_code="STAT.ALPHA.MISSING",
            marker="{{STATISTICS.ALPHA}}",
            domain="STATISTICS",
            question="Alpha missing — 0.05 not invented",
            related_rule_id="STAT.UNAPPROVED_PARAMETERS",
        )
    a = _fmt_alpha(float(alpha))
    text = f"Уровень значимости α={a} (двусторонний) для построения 90% доверительного интервала."
    src = _source_ids(cfg, approved)
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="STAT.ALPHA",
                text=text,
                origin="SOURCE_DERIVED",
                rule_id="STATISTICS.ALPHA",
                source_ids=src,
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="CANONICAL_VALUE",
            canonical_source="statistical_config.alpha",
        )
    ], src, []


def gen_be_criteria_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    cfg = _cfg(ctx)
    lo = cfg.get("be_lower")
    hi = cfg.get("be_upper")
    approved = _latest_approved(ctx, "BE_CRITERIA") or _latest_approved(ctx, "STATISTICAL_CONFIG")
    if (lo is None or hi is None) and approved:
        payload = _payload(approved)
        lo = lo if lo is not None else payload.get("be_lower")
        hi = hi if hi is not None else payload.get("be_upper")
    if lo is None or hi is None:
        return _unresolved_block(
            block_code="STAT.BE.MISSING",
            marker="{{STATISTICS.BE_LIMITS}}",
            domain="STATISTICS",
            question="BE limits missing — 80–125% not invented",
            related_rule_id="STAT.UNAPPROVED_PARAMETERS",
        )
    text = f"BE: {float(lo) * 100:g}% ≤ 90% CI (T/R) ≤ {float(hi) * 100:g}%"
    src = _source_ids(cfg, approved)
    return [
        _enrich(
            _block(
                type_="FORMULA",
                block_code="STAT.BE_CRITERIA",
                text=text,
                origin="SOURCE_DERIVED",
                rule_id="STATISTICS.BE_LIMITS",
                source_ids=src,
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="CANONICAL_VALUE",
            canonical_source="statistical_config.be_limits",
        )
    ], src, []


def gen_stats_policy_12b3(kind: str):
    field, marker, question = _POLICY_FIELD_MAP.get(
        kind, (kind, "{{STATISTICS.POLICY}}", f"Statistics policy '{kind}' missing — not invented")
    )
    decision_type = _POLICY_DECISION_TYPES.get(kind, kind.upper())

    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        cfg = _cfg(ctx)
        policies = dict(ctx.get("stats_policies") or {})
        text_val = (
            cfg.get(field)
            or policies.get(field)
            or policies.get(kind)
            or cfg.get(f"{kind}_text")
            or cfg.get(f"{kind}_policy")
        )
        approved = _latest_approved(ctx, decision_type)
        if not text_val and approved:
            payload = _payload(approved)
            text_val = payload.get("text") or payload.get("policy") or payload.get(field)

        # Populations: can compose from SubjectPlan without inventing policy prose
        if kind == "populations" and not text_val:
            counts = get_canonical_subject_counts(ctx)
            if counts.evaluable_n is not None:
                text_val = (
                    f"Анализ биоэквивалентности выполняется в популяции оцениваемых субъектов "
                    f"(N={counts.evaluable_n})."
                )
                if counts.randomized_n is not None:
                    text_val += (
                        f" Популяция рандомизированных субъектов: N={counts.randomized_n} "
                        f"(SubjectPlan; не подменяется SampleSizeCalculation)."
                    )
                return [
                    _enrich(
                        _block(
                            type_="TEXT",
                            block_code="STAT.POPULATIONS",
                            text=text_val,
                            origin="SOURCE_DERIVED",
                            source_ids=_source_ids(cfg),
                        ),
                        resolution_status="RESOLVED",
                        display_as_final=True,
                        content_type="CANONICAL_VALUE",
                        canonical_source="subject_plan",
                    )
                ], _source_ids(cfg), []

        # ANOVA / descriptive: only from canonical analysis_method / transformation
        if kind in {"anova", "descriptive"} and not text_val:
            method = cfg.get("analysis_method") or cfg.get("method")
            transform = cfg.get("transformation")
            design_disp, design_unres = _design_display(ctx, variables)
            bits: list[str] = []
            if kind == "anova":
                if method:
                    bits.append(f"Метод: {method}.")
                if design_disp and design_disp != "{{DESIGN.TYPE}}":
                    bits.append(f"Дизайн: {design_disp}.")
                if transform:
                    bits.append(f"Преобразование: {transform}.")
            elif kind == "descriptive":
                # Only if config explicitly defines descriptive policy fields
                desc = cfg.get("descriptive_stats_spec") or policies.get("descriptive_stats_spec")
                if desc:
                    bits.append(str(desc))
            if bits and not design_unres:
                text_val = " ".join(bits)
            elif bits and design_unres:
                return _unresolved_block(
                    block_code=f"STAT.{kind.upper()}.DESIGN",
                    marker="{{DESIGN.TYPE}}",
                    domain="STATISTICS",
                    question=question,
                )

        if not text_val:
            return _unresolved_block(
                block_code=f"STAT.{kind.upper()}.MISSING",
                marker=marker,
                domain="STATISTICS",
                question=question,
                related_rule_id="STAT.UNAPPROVED_PARAMETERS",
            )

        src = _source_ids(cfg, approved)
        # Expert-approved policies are final; bare config text without provenance → PROPOSED
        final = bool(approved) or bool(_source_ids(cfg))
        status = "RESOLVED" if final else "PROPOSED"
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code=f"STAT.{kind.upper()}",
                    text=str(text_val),
                    origin="EXPERT_DECISION" if approved else "SOURCE_DERIVED",
                    source_ids=src,
                    rule_id=f"STATISTICS.{kind.upper()}",
                ),
                resolution_status=status,
                display_as_final=final,
                content_type="EXPERT_DECISION" if approved else ("CANONICAL_VALUE" if final else "CONDITION"),
                knowledge_gaps=[]
                if final
                else [
                    _gap(
                        "STATISTICS",
                        f"{kind} policy present without approved decision / provenance",
                        importance="MEDIUM",
                        blocking=False,
                    )
                ],
            )
        ], src, []

    return _inner


# ---- Section 10: Data access / study management ----


def gen_data_access_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    """Section 10 — prefer STATIC_VERIFIED admin boilerplate; study-specific only if canonical."""
    admin = _admin(ctx)
    blocks: list[dict] = []
    src: list[str] = []
    gaps: list[dict] = []

    # STATIC_VERIFIED compliance / deviations / retention boilerplate (classified)
    static_notes = [
        ("ADMIN.10.2", "Соблюдение протокола обеспечивается в соответствии со стандартными процедурами центра."),
        ("ADMIN.10.3", "Отклонения от протокола документируются и оцениваются согласно GCP."),
        ("ADMIN.10.4", "Доступ к данным исследования предоставляется уполномоченным лицам в объёме, необходимом для мониторинга, аудита и регуляторной инспекции."),
    ]
    for block_id, text in static_notes:
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code=block_id,
                    text=text,
                    origin="STATIC_VERIFIED",
                    rule_id=STATIC_VERIFIED,
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="STATIC_VERIFIED",
                canonical_source="static_blocks",
            )
        )

    # Study-specific data-access / monitoring — only if present
    study_text = admin.get("data_access_policy") or admin.get("monitoring_policy") or (ctx.get("data_access") or {}).get("policy")
    if study_text:
        sids = _source_ids(admin, ctx.get("data_access") if isinstance(ctx.get("data_access"), dict) else None)
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="DATA.ACCESS.STUDY",
                    text=str(study_text),
                    origin="SOURCE_DERIVED",
                    source_ids=sids,
                ),
                resolution_status="RESOLVED" if sids else "PROPOSED",
                display_as_final=bool(sids),
                content_type="CANONICAL_VALUE" if sids else "CONDITION",
                canonical_source="study_administration",
            )
        )
        src.extend(sids)
    else:
        gaps.append(
            _gap(
                "DATA_ACCESS",
                "Study-specific data-access policy absent — STATIC_VERIFIED boilerplate only",
                importance="LOW",
                blocking=False,
            )
        )

    if gaps and blocks:
        blocks[0]["knowledge_gaps"] = list(blocks[0].get("knowledge_gaps") or []) + gaps
    return blocks, list(dict.fromkeys(src)), []


# ---- Sections 11–13: Quality / Ethics / Data records ----


def gen_quality_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    admin = _admin(ctx)
    quality = ctx.get("quality") or {}
    text = admin.get("quality_policy") or quality.get("policy") or quality.get("text")
    if not text:
        # STATIC_VERIFIED shell — no invented monitoring visit counts
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="QUALITY.STATIC",
                    text=(
                        "Обеспечение качества проводится в соответствии с GCP и стандартными "
                        "процедурами спонсора/центра. Частота мониторинга и аудит-график "
                        "не задаются без канонического источника."
                    ),
                    origin="STATIC_VERIFIED",
                    rule_id=STATIC_VERIFIED,
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="STATIC_VERIFIED",
                knowledge_gaps=[
                    _gap(
                        "QUALITY",
                        "Study-specific quality/monitoring schedule absent — not invented",
                        importance="MEDIUM",
                        blocking=False,
                    )
                ],
            )
        ], [], []
    src = _source_ids(admin, quality if isinstance(quality, dict) else None)
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="QUALITY.POLICY",
                text=str(text),
                origin="SOURCE_DERIVED",
                source_ids=src,
            ),
            resolution_status="RESOLVED" if src else "PROPOSED",
            display_as_final=bool(src),
            content_type="CANONICAL_VALUE" if src else "CONDITION",
            canonical_source="study_administration.quality",
        )
    ], src, []


def gen_ethics_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    admin = _admin(ctx)
    gaps: list[dict] = []
    unresolved: list[str] = []
    blocks: list[dict] = []
    src: list[str] = []

    # Ethical principles — STATIC_VERIFIED shell only
    blocks.append(
        _enrich(
            _block(
                type_="TEXT",
                block_code="ETHICS.PRINCIPLES",
                text=(
                    "Исследование проводится в соответствии с этическими принципами "
                    "Хельсинкской декларации и требованиями GCP."
                ),
                origin="STATIC_VERIFIED",
                rule_id=STATIC_VERIFIED,
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="STATIC_VERIFIED",
        )
    )

    # Committee: study_administration ethics fields OR orgs_by_roles — never invent name
    committee_name = (
        admin.get("ethics_committee")
        or admin.get("ethics_committee_name")
        or admin.get("iec_name")
        or admin.get("irb_name")
    )
    committee_orgs = orgs_by_roles(ctx, _ETHICS_ROLES)
    if not committee_name and committee_orgs:
        committee_name = committee_orgs[0].get("name")
        src.extend(_source_ids(committee_orgs[0]))

    if committee_name:
        approval = admin.get("ethics_approval_number") or admin.get("ethics_approval_date")
        text = f"Этический комитет / IEC/IRB: {committee_name}."
        if approval:
            text += f" Сведения об одобрении: {approval}."
        src.extend(_source_ids(admin))
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="ETHICS.COMMITTEE",
                    text=text,
                    origin="SOURCE_DERIVED",
                    source_ids=list(dict.fromkeys(src)),
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
                canonical_source="study_administration|organizations.ethics",
            )
        )
    else:
        unresolved.append("{{ETHICS.COMMITTEE}}")
        gaps.append(
            _gap(
                "ETHICS",
                "Ethics committee name missing — not invented",
                related_rule_id="QA.ETHICS.MISSING_REQUIRED_VALUE",
                importance="HIGH",
                blocking=False,
            )
        )
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="ETHICS.COMMITTEE.MISSING",
                    text="{{ETHICS.COMMITTEE}}",
                    unresolved=["{{ETHICS.COMMITTEE}}"],
                    origin="PLACEHOLDER",
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=gaps[-1:],
                content_type="PLACEHOLDER",
            )
        )

    consent = admin.get("informed_consent") or admin.get("informed_consent_text")
    if consent:
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="ETHICS.CONSENT",
                    text=str(consent),
                    origin="SOURCE_DERIVED",
                    source_ids=_source_ids(admin),
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
            )
        )
    else:
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="ETHICS.CONSENT.STATIC",
                    text="Информированное согласие получается до любых процедур исследования.",
                    origin="STATIC_VERIFIED",
                    rule_id=STATIC_VERIFIED,
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="STATIC_VERIFIED",
            )
        )

    # Insurance if canonical (via financing helpers / admin)
    ins_text, ins_src = insurance_block(ctx)
    if ins_text:
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="ETHICS.INSURANCE",
                    text=f"Страхование субъектов: {ins_text}",
                    origin="SOURCE_DERIVED",
                    source_ids=ins_src,
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
            )
        )
        src.extend(ins_src)

    # Retention years only if present
    retention = admin.get("retention_years") or admin.get("data_retention_years") or admin.get("record_retention_years")
    if retention is not None:
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="ETHICS.RETENTION",
                    text=f"Срок хранения документации: {retention} лет.",
                    origin="SOURCE_DERIVED",
                    source_ids=_source_ids(admin),
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
            )
        )

    if gaps and blocks:
        first = blocks[0]
        first["knowledge_gaps"] = list(first.get("knowledge_gaps") or []) + [
            g for g in gaps if g not in (first.get("knowledge_gaps") or [])
        ]
    return blocks, list(dict.fromkeys(src)), unresolved


def gen_data_records_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    admin = _admin(ctx)
    records = ctx.get("data_records") or {}
    gaps: list[dict] = []
    blocks: list[dict] = []
    src: list[str] = []

    blocks.append(
        _enrich(
            _block(
                type_="TEXT",
                block_code="DATA.RECORDS.STATIC",
                text=(
                    "Исходные документы, CRF и электронные записи ведутся и хранятся "
                    "в соответствии с GCP. Конфиденциальность персональных данных субъектов соблюдается."
                ),
                origin="STATIC_VERIFIED",
                rule_id=STATIC_VERIFIED,
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="STATIC_VERIFIED",
        )
    )

    policy = admin.get("data_records_policy") or records.get("policy") or records.get("text")
    if policy:
        sids = _source_ids(admin, records if isinstance(records, dict) else None)
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="DATA.RECORDS.POLICY",
                    text=str(policy),
                    origin="SOURCE_DERIVED",
                    source_ids=sids,
                ),
                resolution_status="RESOLVED" if sids else "PROPOSED",
                display_as_final=bool(sids),
                content_type="CANONICAL_VALUE" if sids else "CONDITION",
            )
        )
        src.extend(sids)

    retention = (
        admin.get("retention_years")
        or admin.get("data_retention_years")
        or admin.get("record_retention_years")
        or (records.get("retention_years") if isinstance(records, dict) else None)
    )
    if retention is not None:
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="DATA.RETENTION",
                    text=f"Срок хранения записей исследования: {retention} лет.",
                    origin="SOURCE_DERIVED",
                    source_ids=_source_ids(admin),
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
                canonical_source="study_administration.retention_years",
            )
        )
    else:
        gaps.append(
            _gap(
                "DATA_RECORDS",
                "Retention period missing — years not invented",
                related_rule_id="QA.DATA.MISSING_SOURCE",
                importance="MEDIUM",
                blocking=False,
            )
        )
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="DATA.RETENTION.MISSING",
                    text="{{DATA.RETENTION_YEARS}}",
                    unresolved=["{{DATA.RETENTION_YEARS}}"],
                    origin="PLACEHOLDER",
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=gaps[-1:],
                content_type="PLACEHOLDER",
            )
        )

    return blocks, list(dict.fromkeys(src)), find_unresolved_markers(blocks)


def gen_standard_text_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    """Dispatcher for section codes 11 / 12 / 13 (quality / ethics / data records)."""
    code = str(section.section_code or "")
    root = code.split(".", 1)[0]
    if root == "11" or code.startswith("11"):
        return gen_quality_12b3(section, ctx, variables, consistency)
    if root == "12" or code.startswith("12"):
        return gen_ethics_12b3(section, ctx, variables, consistency)
    if root == "13" or code.startswith("13"):
        return gen_data_records_12b3(section, ctx, variables, consistency)
    # Unknown standard_text target — gap, do not invent
    marker = f"{{{{SECTION.{code}.TEXT}}}}"
    return _unresolved_block(
        block_code="STANDARD.TEXT.UNKNOWN",
        marker=marker,
        domain="ADMIN",
        question=f"No 12B.3 standard_text handler for section {code}",
    )


# ---- Sections 14–15: Financing / publications ----


def gen_financing_insurance_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks: list[dict] = []
    unresolved: list[str] = []
    src: list[str] = []
    gaps: list[dict] = []

    sponsor = resolve_sponsor(ctx)
    if sponsor and sponsor.get("name"):
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="FIN.SPONSOR",
                    text=f"Спонсор: {sponsor['name']}.",
                    origin="SOURCE_DERIVED",
                    source_ids=_source_ids(sponsor),
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
                canonical_source="sponsor",
            )
        )
        src.extend(_source_ids(sponsor))

    ins_text, ins_src = insurance_block(ctx)
    if ins_text:
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="FIN.INSURANCE",
                    text=f"Страхование. {ins_text}",
                    origin="SOURCE_DERIVED",
                    source_ids=ins_src,
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
            )
        )
        src.extend(ins_src)
    else:
        unresolved.append("{{INSURANCE.DETAILS}}")
        gaps.append(_gap("ADMIN", "Insurance details missing — not invented", related_rule_id="QA.ADMIN.INSURANCE_UNRESOLVED"))
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="FIN.INSURANCE.MISSING",
                    text="{{INSURANCE.DETAILS}}",
                    unresolved=["{{INSURANCE.DETAILS}}"],
                    origin="PLACEHOLDER",
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=gaps[-1:],
            )
        )

    fin_text, fin_src = financing_block(ctx)
    if fin_text:
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="FIN.FINANCING",
                    text=f"Финансирование. {fin_text}",
                    origin="SOURCE_DERIVED",
                    source_ids=fin_src,
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="CANONICAL_VALUE",
            )
        )
        src.extend(fin_src)
    else:
        unresolved.append("{{FINANCING.DETAILS}}")
        gaps.append(_gap("ADMIN", "Financing details missing — not invented"))
        blocks.append(
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="FIN.FINANCING.MISSING",
                    text="{{FINANCING.DETAILS}}",
                    unresolved=["{{FINANCING.DETAILS}}"],
                    origin="PLACEHOLDER",
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=gaps[-1:],
            )
        )

    return blocks, list(dict.fromkeys(src)), unresolved


def gen_publications_12b3(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    text, src = publication_block(ctx)
    if not text:
        return _unresolved_block(
            block_code="PUB.POLICY.MISSING",
            marker="{{PUBLICATION.POLICY}}",
            domain="PUBLICATION",
            question="Publication policy missing — contractual clauses not invented",
            related_rule_id="QA.PUBLICATION.UNAPPROVED_CLAUSE",
        )
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="PUB.POLICY",
                text=text,
                origin="SOURCE_DERIVED",
                source_ids=src,
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="CANONICAL_VALUE",
            canonical_source="study_administration.publication",
        )
    ], src, find_unresolved_markers(text)


# Do NOT overlay "heading" globally.
CORE_12B3_GENERATORS: dict[str, Any] = {
    "statistical_method": gen_statistical_method_12b3,
    "sample_size": gen_sample_size_12b3,
    "alpha": gen_alpha_12b3,
    "be_criteria": gen_be_criteria_12b3,
    "stopping_rules": gen_stats_policy_12b3("stopping"),
    "missing_data_policy": gen_stats_policy_12b3("missing"),
    "sap_deviations": gen_stats_policy_12b3("deviations"),
    "analysis_populations": gen_stats_policy_12b3("populations"),
    "statistical_analysis": gen_stats_policy_12b3("anova"),
    "descriptive_stats": gen_stats_policy_12b3("descriptive"),
    "anova_methods": gen_stats_policy_12b3("anova"),
    "outliers": gen_stats_policy_12b3("outliers"),
    "safety_analysis": gen_stats_policy_12b3("safety_stats"),
    "data_access": gen_data_access_12b3,
    "standard_text": gen_standard_text_12b3,
    "financing_insurance": gen_financing_insurance_12b3,
    "publications": gen_publications_12b3,
}
