"""Unified knowledge-gap surface for the protocol pipeline — Phase 29.

A gap is an input the source documents did not provide. Every gap names exactly
one way to close it: AI research plus expert verification, direct expert entry,
or an expert decision in an engine. A missing input gates only the steps that
consume it — never the whole protocol.
"""

from __future__ import annotations

from typing import Any

from app.domain.decision_store import (
    get_context,
    list_decisions,
    put_context,
    put_decisions,
)
from app.domain.research_decision_bridge import recompute_affected_decisions
from app.domain.research_evidence_engine import create_tasks_from_gaps
from app.domain.research_evidence_models import ResearchClaim, SourceResult
from app.domain.research_evidence_store import (
    list_claims,
    list_tasks,
    put_claim,
    put_result,
)
from app.domain.research_usability import apply_usability
from app.domain.sample_size_engine import ui_sample_size_panel
from app.domain.sample_size_engine_classes import SAMPLE_SIZE_PK_PARAMETERS
from app.domain.statistics_store import latest_plan as latest_statistics_plan

# Resolution routes
RESEARCH = "RESEARCH"  # AI search in open sources → PROPOSED → expert verify
MANUAL = "MANUAL"  # expert types the value with a rationale
EXPERT_DECISION = "EXPERT_DECISION"  # engine-side choice (statistics), not a value

GAP_CATALOG: dict[str, dict[str, Any]] = {
    "MISSING_TMAX_FOR_SAMPLING": {
        "title": "Ожидаемый Tmax",
        "why": "Нужен, чтобы поставить частые заборы вокруг предполагаемого Cmax.",
        "blocks": ("Sampling",),
        "claim_field": "pk.Tmax",
        "fact_field": "pk.expected_tmax",
        "unit": "ч",
        "numeric": False,  # допускается диапазон, например 2–4
        "resolution": (RESEARCH, MANUAL),
        "note": "Плановое значение из SmPC или литературы, а не наблюдаемый Tmax исследования.",
        "sources_hint": ("SmPC / ОХЛП", "Регуляторные документы", "Научная литература"),
    },
    "MISSING_HALF_LIFE_FOR_WASHOUT": {
        "title": "Период полувыведения (t½)",
        "why": "Определяет длительность отбора проб и период отмывки между периодами.",
        "blocks": ("Washout", "Sampling"),
        "claim_field": "pk.t_half",
        "fact_field": "pk.expected_t_half",
        "unit": "ч",
        "numeric": True,
        "resolution": (RESEARCH, MANUAL),
        "sources_hint": ("SmPC / ОХЛП", "Научная литература"),
    },
    "MISSING_CVINTRA": {
        "title": "Внутрииндивидуальная вариабельность (CVintra)",
        "why": "Без CVintra нельзя рассчитать размер выборки и статистический план.",
        "blocks": ("Sample Size", "Statistics"),
        "claim_field": "cv_intra",
        "fact_field": "cv_intra",
        "unit": "%",
        "numeric": True,
        "requires_pk_parameter": True,
        "resolution": (RESEARCH, MANUAL),
        "note": "Нужна именно within-subject вариабельность для конкретного PK-параметра.",
        "sources_hint": ("Публикации по биоэквивалентности", "Отчёты предыдущих исследований"),
    },
    "MISSING_MEAL_COMPOSITION": {
        "title": "Состав стандартного приёма пищи",
        "why": "Требуется для описания fed-условий приёма препарата.",
        "blocks": ("Food",),
        "claim_field": "food.calorie_target",
        "fact_field": "food.calorie_target",
        "unit": "ккал",
        "numeric": False,
        "resolution": (RESEARCH, MANUAL),
        "sources_hint": ("Регуляторные рекомендации", "SmPC / ОХЛП"),
    },
    "MISSING_ANALYTE": {
        "title": "Определяемый аналит",
        "why": "Биоаналитика и PK-параметры считаются для конкретного вещества.",
        "blocks": ("Analyte / PK",),
        "claim_field": "bioanalysis.analyte",
        "fact_field": "bioanalysis.analyte",
        "unit": None,
        "numeric": False,
        "resolution": (MANUAL, RESEARCH),
        "sources_hint": ("SmPC / ОХЛП", "Научная литература"),
    },
    "MISSING_PRIMARY_BE_SELECTION": {
        "title": "Основной endpoint биоэквивалентности (PRIMARY BE)",
        "why": "Выбор основного параметра — врачебное решение, платформа его не подставляет.",
        "blocks": ("Statistics", "Sample Size"),
        "claim_field": None,
        "fact_field": "pk.primary_parameters",
        "unit": None,
        "numeric": False,
        "resolution": (EXPERT_DECISION,),
        "note": "Закрывается в шаге «Решения», блок Statistics.",
    },
    "MISSING_ANALYSIS_POPULATION_RULE": {
        "title": "Популяция анализа",
        "why": "Правило включения субъектов в анализ задаёт эксперт, а не движок.",
        "blocks": ("Statistics",),
        "claim_field": None,
        "fact_field": "statistics.analysis_population",
        "unit": None,
        "numeric": False,
        "resolution": (EXPERT_DECISION,),
        "note": "Закрывается в шаге «Решения», блок Statistics.",
    },
}

# Engine codes that mean the same gap
CANONICAL_ALIASES: dict[str, str] = {
    "MISSING_VERIFIED_CVINTRA": "MISSING_CVINTRA",
    "MISSING_CVINTRA_CMAX": "MISSING_CVINTRA",
    "MISSING_CVINTRA_AUC": "MISSING_CVINTRA",
    "CV_PROPOSED_NOT_ALLOWED": "MISSING_CVINTRA",
    "CV_NOT_USABLE": "MISSING_CVINTRA",
    "MISSING_PRIMARY_PK_PARAMETER": "MISSING_PRIMARY_BE_SELECTION",
    "REQUIRES_EXPERT_SELECTION": "MISSING_PRIMARY_BE_SELECTION",
    "PRIMARY_BE_REQUIRES_EXPERT_SELECTION": "MISSING_PRIMARY_BE_SELECTION",
}

# Generic markers that repeat information already carried by a concrete gap
IGNORED_ENGINE_CODES: frozenset[str] = frozenset(
    {"REQUIRES_EXPERT_DECISION", "AI_CANNOT_APPROVE", "AI_CANNOT_SELECT_METHOD"}
)

DOMAIN_LABELS_RU: dict[str, str] = {
    "DESIGN": "Дизайн",
    "FOOD": "Пищевой режим",
    "WASHOUT": "Washout",
    "SAMPLING": "Sampling",
    "ANALYTE_PK": "Analyte / PK",
    "STATISTICS": "Statistics",
}

CV_FIELD_ALIASES: frozenset[str] = frozenset({"cv_intra", "cvintra", "statistics.cvintra"})


def _claim_matches(meta: dict[str, Any], claim: ResearchClaim) -> bool:
    field = meta.get("claim_field")
    if not field:
        return False
    fp = str(claim.field_path or "")
    if field == "cv_intra":
        return fp in CV_FIELD_ALIASES or bool(claim.cvintra)
    if field == "pk.Tmax":
        return fp in {"pk.Tmax", "pk.expected_tmax"}
    if field == "pk.t_half":
        return fp in {"pk.t_half", "pk.expected_t_half"}
    return fp == field


def _proposal(claim: ResearchClaim) -> dict[str, Any]:
    m = claim.measurement or {}
    value = claim.value
    if value is None:
        value = m.get("value")
    if value is None and m.get("range_low") is not None:
        value = f"{m.get('range_low')}–{m.get('range_high')}"
    return {
        "claim_id": claim.id,
        "value": value,
        "unit": claim.unit or m.get("unit"),
        "excerpt": claim.excerpt,
        "confidence": claim.confidence,
        "verification_status": claim.verification_status,
        "applicability": claim.applicability,
        "usable": claim.usability == "USABLE_FOR_DECISION",
        "extraction_method": claim.extraction_method,
        "pk_parameter": (claim.cvintra or {}).get("PK_parameter"),
    }


def _statistics_gap_codes(study_id: str) -> list[str]:
    """Concrete statistics gaps. Generic 'expert must decide' markers are dropped."""
    plan = latest_statistics_plan(study_id)
    if plan is None:
        return []
    codes: list[str] = []
    for b in plan.blocking_reasons or []:
        code = str(b)
        if code in IGNORED_ENGINE_CODES:
            continue
        canon = CANONICAL_ALIASES.get(code, code)
        if canon in GAP_CATALOG:
            codes.append(canon)
    has_primary = any(
        str(getattr(p, "role", "")) == "PRIMARY_BE" for p in (plan.parameters or [])
    )
    if not has_primary:
        codes.append("MISSING_PRIMARY_BE_SELECTION")
    return codes


def collect_study_gaps(study_id: str, *, package_id: str | None = None) -> dict[str, Any]:
    """Every input the package did not provide, with the one place to close it."""
    origins: dict[str, set[str]] = {}

    def add(raw_code: str, origin: str) -> None:
        code = str(raw_code or "")
        if not code or code in IGNORED_ENGINE_CODES:
            return
        canon = CANONICAL_ALIASES.get(code, code)
        if canon in GAP_CATALOG:
            origins.setdefault(canon, set()).add(origin)

    for d in list_decisions(study_id, package_id=package_id):
        label = DOMAIN_LABELS_RU.get(str(d.domain), str(d.domain))
        for g in d.knowledge_gaps or []:
            if isinstance(g, dict):
                add(str(g.get("code") or ""), label)
        for r in d.blocking_reasons or []:
            if isinstance(r, dict):
                add(str(r.get("blocking_reason_code") or r.get("code") or ""), label)

    # Engine inputs are only "missing" once the package has actually been analysed
    analysed = bool(origins) or get_context(study_id, package_id=package_id) is not None
    if analysed:
        try:
            ss_panel = ui_sample_size_panel(study_id)
            for b in ss_panel.get("blocking_reasons") or []:
                add(str(b), "Sample Size")
        except Exception:  # engine unavailable must not hide other gaps
            pass

        for code in _statistics_gap_codes(study_id):
            add(code, "Statistics")

    claims = list_claims(study_id=study_id)
    tasks_by_code = {t.knowledge_gap_code: t for t in list_tasks(study_id)}

    gaps: list[dict[str, Any]] = []
    for code, origin_set in origins.items():
        meta = GAP_CATALOG[code]
        proposals = [_proposal(c) for c in claims if _claim_matches(meta, c)]
        verified = [p for p in proposals if p["verification_status"] == "VERIFIED" and p["usable"]]
        if verified:
            status = "VERIFIED"
        elif proposals:
            status = "PROPOSED"
        else:
            status = "OPEN"
        task = tasks_by_code.get(code)
        gaps.append(
            {
                "code": code,
                "title": meta["title"],
                "why": meta["why"],
                "note": meta.get("note"),
                "blocks": list(meta["blocks"]),
                "blocked_by_this": ", ".join(meta["blocks"]),
                "requested_by": sorted(origin_set),
                "field_path": meta.get("fact_field"),
                "claim_field": meta.get("claim_field"),
                "unit": meta.get("unit"),
                "numeric": bool(meta.get("numeric")),
                "requires_pk_parameter": bool(meta.get("requires_pk_parameter")),
                "pk_parameter_options": list(SAMPLE_SIZE_PK_PARAMETERS)
                if meta.get("requires_pk_parameter")
                else [],
                "resolution": list(meta["resolution"]),
                "sources_hint": list(meta.get("sources_hint") or ()),
                "status": status,
                "proposals": proposals,
                "research_task_id": task.id if task else None,
                # Verified but the engine still reports it — needs apply/recompute
                "needs_apply": status == "VERIFIED",
                "severity": "WARNING",
                "scope": "STEP",
            }
        )

    order = {"OPEN": 0, "PROPOSED": 1, "VERIFIED": 2}
    gaps.sort(key=lambda g: (order.get(str(g["status"]), 3), str(g["title"])))

    resolved = [
        {
            "code": code,
            "title": GAP_CATALOG[code]["title"],
            "value": p["value"],
            "unit": p["unit"],
            "extraction_method": p["extraction_method"],
        }
        for code, meta in GAP_CATALOG.items()
        if code not in origins
        for c in claims
        if _claim_matches(meta, c)
        and c.verification_status == "VERIFIED"
        for p in [_proposal(c)]
    ]

    return {
        "study_id": study_id,
        "gaps": gaps,
        "resolved": resolved,
        "counts": {
            "total": len(gaps),
            "open": len([g for g in gaps if g["status"] == "OPEN"]),
            "proposed": len([g for g in gaps if g["status"] == "PROPOSED"]),
            "verified": len([g for g in gaps if g["status"] == "VERIFIED"]),
        },
        "protocol_frozen": False,
        "study_mutated": False,
    }


def _coerce_value(raw: Any, *, numeric: bool) -> Any:
    if numeric:
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Значение должно быть числом") from exc
    if isinstance(raw, (int, float)):
        return raw
    text = str(raw or "").strip()
    if not text:
        raise ValueError("Значение обязательно")
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return text


def resolve_gap_manually(
    study_id: str,
    code: str,
    *,
    value: Any,
    rationale: str,
    actor: str,
    unit: str | None = None,
    pk_parameter: str | None = None,
    source_note: str | None = None,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Expert supplies a missing value directly. Recorded as verified expert evidence."""
    canon = CANONICAL_ALIASES.get(code, code)
    meta = GAP_CATALOG.get(canon)
    if meta is None:
        raise ValueError(f"Неизвестный пробел: {code}")
    if MANUAL not in meta["resolution"]:
        raise ValueError(
            f"«{meta['title']}» закрывается экспертным решением в шаге «Решения», а не вводом значения"
        )
    if not str(rationale or "").strip():
        raise ValueError("Обоснование обязательно")
    if not str(actor or "").strip():
        raise ValueError("Требуется автор ввода")

    coerced = _coerce_value(value, numeric=bool(meta.get("numeric")))
    if meta.get("requires_pk_parameter"):
        if pk_parameter not in SAMPLE_SIZE_PK_PARAMETERS:
            raise ValueError(
                "Укажите PK-параметр: " + ", ".join(SAMPLE_SIZE_PK_PARAMETERS)
            )
        if not isinstance(coerced, float) or coerced <= 0:
            raise ValueError("CVintra должна быть положительным числом")

    task = None
    existing = {t.knowledge_gap_code: t for t in list_tasks(study_id)}
    if canon in existing:
        task = existing[canon]
    else:
        created = create_tasks_from_gaps(
            study_id,
            [{"code": canon, "title": meta["title"]}],
            package_id=package_id,
        )
        task = created[0] if created else None

    unit_value = unit or meta.get("unit")
    excerpt = str(rationale).strip()
    source = SourceResult(
        research_task_id=task.id if task else "",
        provider="LOCAL_DOCUMENTS",
        title=f"Экспертный ввод: {meta['title']}",
        source_type="OTHER",
        text_excerpt=source_note or excerpt,
        author=actor,
        study_id=study_id,
    )
    put_result(source)

    claim = ResearchClaim(
        claim_text=f"{meta['title']}: {coerced}{(' ' + unit_value) if unit_value else ''}",
        research_task_id=task.id if task else None,
        field_path=meta.get("claim_field"),
        value=coerced,
        unit=unit_value,
        source_result_id=source.id,
        excerpt=excerpt,
        extraction_method="MANUAL",
        confidence="HIGH",
        verification_status="VERIFIED",
        applicability="DIRECT",
        applicability_reason=excerpt,
        study_id=study_id,
    )
    if meta.get("requires_pk_parameter"):
        claim.cvintra = {
            "CV_value": coerced,
            "CV_unit": unit_value or "%",
            "PK_parameter": pk_parameter,
            "variability_type": "WITHIN_SUBJECT",
        }
    else:
        claim.measurement = {
            "parameter": meta["title"],
            "value": coerced,
            "unit": unit_value,
            "statistic_type": "POINT",
        }
    apply_usability(claim)
    put_claim(claim)

    applied = _write_expert_fact(
        study_id,
        meta,
        coerced,
        actor=actor,
        package_id=package_id,
    )

    return {
        "code": canon,
        "claim": claim.to_dict(),
        "applied_fields": applied["applied_fields"],
        "recomputed_domains": applied["recomputed_domains"],
        "study_mutated": False,
        "auto_approved": False,
    }


def _write_expert_fact(
    study_id: str,
    meta: dict[str, Any],
    value: Any,
    *,
    actor: str,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Put the expert value into the decision context and recompute what depends on it."""
    ctx = get_context(study_id, package_id=package_id)
    fact_field = meta.get("fact_field")
    if ctx is None or not fact_field:
        return {"applied_fields": [], "recomputed_domains": []}

    applied = [fact_field]
    ctx.structured_facts[fact_field] = value
    ctx.fact_statuses[fact_field] = "VERIFIED"
    ctx.fact_sources[fact_field] = "EXPERT_INPUT"

    claim_field = meta.get("claim_field")
    if claim_field and claim_field != fact_field:
        ctx.structured_facts[claim_field] = value
        ctx.fact_statuses[claim_field] = "VERIFIED"
        ctx.fact_sources[claim_field] = "EXPERT_INPUT"
        applied.append(claim_field)

    if fact_field == "pk.expected_tmax":
        ctx.tmax = value
    elif fact_field == "pk.expected_t_half":
        ctx.half_life = value if isinstance(value, (int, float)) else ctx.half_life
    elif fact_field == "cv_intra":
        ctx.cvintra = value if isinstance(value, (int, float)) else ctx.cvintra

    ctx.knowledge_gaps = [
        g
        for g in ctx.knowledge_gaps
        if str((g or {}).get("code") or "") not in _codes_for_fact(fact_field)
    ]

    previous = list_decisions(study_id, package_id=package_id)
    result = recompute_affected_decisions(ctx, applied_fields=applied, previous=previous)
    put_context(study_id, ctx, package_id=package_id)
    decisions = result["decisions"]
    if decisions:
        put_decisions(study_id, decisions, package_id=package_id)
    return {
        "applied_fields": applied,
        "recomputed_domains": result.get("recomputed_domains") or [],
    }


def _codes_for_fact(fact_field: str) -> set[str]:
    return {
        code
        for code, meta in GAP_CATALOG.items()
        if meta.get("fact_field") == fact_field
    }


def apply_verified_evidence(
    study_id: str,
    *,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Push verified, usable evidence into the context and recompute dependent steps."""
    from app.domain.research_decision_bridge import apply_verified_research_to_context

    ctx = get_context(study_id, package_id=package_id)
    if ctx is None:
        return {"applied_fields": [], "recomputed_domains": []}
    previous = list_decisions(study_id, package_id=package_id)
    ctx, applied = apply_verified_research_to_context(ctx, study_id=study_id)
    result = recompute_affected_decisions(ctx, applied_fields=applied, previous=previous)
    put_context(study_id, ctx, package_id=package_id)
    decisions = result["decisions"]
    if decisions:
        put_decisions(study_id, decisions, package_id=package_id)
    return {
        "applied_fields": applied,
        "recomputed_domains": result.get("recomputed_domains") or [],
    }
