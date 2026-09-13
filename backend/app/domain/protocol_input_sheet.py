"""The protocol input sheet — Phase 30.

One list of everything a bioequivalence protocol needs, with what we already
have and where it came from. This replaces three overlapping surfaces that each
answered "what is missing" in their own vocabulary: the gap catalogue, domain
coverage, and the per-engine blocking reasons.

Reading rules, in priority order:

1. the documents the writer uploaded,
2. what the regulation prescribes,
3. what AI research proposed — always marked as awaiting a human look,
4. what the expert typed.

A value found in the writer's own document counts as ready: they supplied it.
Only a value the platform found on the internet asks for confirmation. Nothing
is ever invented: a row with no source stays MISSING and says so in the draft.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.decision_store import get_context, list_decisions, put_context, put_decisions
from app.domain.protocol_defaults import (
    CONVENTION,
    REGULATORY,
    apply_defaults_to_context,
    default_for,
)
from app.domain.research_decision_bridge import recompute_affected_decisions
from app.domain.research_evidence_store import list_claims
from app.domain.sample_size_engine_classes import SAMPLE_SIZE_PK_PARAMETERS
from app.domain.sample_size_store import list_calculations
from app.domain.statistics_engine_classes import ANALYSIS_POPULATIONS
from app.domain.statistics_store import latest_plan as latest_statistics_plan
from app.domain.study_workspace import aggregate_conflicts, find_study_package
from app.domain.workspace_gaps import GAP_CATALOG, resolve_gap_manually

# How a row gets filled
MANUAL = "MANUAL"  # expert types it
RESEARCH = "RESEARCH"  # AI searches open sources, expert confirms
CHOICE = "CHOICE"  # pick from a closed list
DOCUMENT = "DOCUMENT"  # only an uploaded document can supply it
DERIVED = "DERIVED"  # an engine computes it from other rows

# Where a value came from — writer-facing, no raw enums
FROM_DOCUMENT = "FROM_DOCUMENT"
FROM_REGULATION = "FROM_REGULATION"
FROM_EXPERT = "FROM_EXPERT"
NEEDS_CONFIRM = "NEEDS_CONFIRM"
COMPUTED = "COMPUTED"
CONFLICT = "CONFLICT"
MISSING = "MISSING"

READY_STATUSES: frozenset[str] = frozenset(
    {FROM_DOCUMENT, FROM_REGULATION, FROM_EXPERT, COMPUTED}
)

# `fact_sources` carries the document type a value was extracted from
DOCUMENT_SOURCES: frozenset[str] = frozenset(
    {"SYNOPSIS", "DESIGN", "SMPC", "CHECKLIST", "PREVIOUS_PROTOCOL", "SYNOPSIS_DESIGN"}
)

GROUPS: tuple[tuple[str, str], ...] = (
    ("ADMIN", "Административная часть"),
    ("PRODUCTS", "Препараты"),
    ("DESIGN", "Дизайн исследования"),
    ("SUBJECTS", "Субъекты"),
    ("PK", "Фармакокинетика и отбор проб"),
    ("FOOD", "Условия приёма"),
    ("STATS", "Статистика и размер выборки"),
    ("SAFETY", "Безопасность"),
)

GROUP_TITLES: dict[str, str] = dict(GROUPS)


@dataclass(frozen=True)
class SheetSpec:
    """One thing the protocol needs."""

    key: str
    title: str
    why: str
    group: str
    section: str
    fill: tuple[str, ...]
    required: bool = True
    unit: str | None = None
    numeric: bool = False
    options: tuple[str, ...] = ()
    gap_code: str | None = None
    requires_pk_parameter: bool = False
    note: str | None = None
    aliases: tuple[str, ...] = field(default=())


def _s(*args: Any, **kwargs: Any) -> SheetSpec:
    return SheetSpec(*args, **kwargs)


SHEET_CATALOG: tuple[SheetSpec, ...] = (
    # --- Administrative -----------------------------------------------------
    _s(
        "study.protocol_number",
        "Номер протокола",
        "Идентифицирует протокол на титульном листе и во всех разделах.",
        "ADMIN",
        "GENERAL",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "study.title",
        "Название исследования",
        "Полное название выносится на титульный лист.",
        "ADMIN",
        "GENERAL",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "sponsor.name",
        "Спонсор",
        "Указывается в общих сведениях и в обязательствах сторон.",
        "ADMIN",
        "GENERAL",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "cro.name",
        "Организация-исполнитель (CRO)",
        "Указывается в общих сведениях.",
        "ADMIN",
        "GENERAL",
        (MANUAL, DOCUMENT),
        required=False,
    ),
    _s(
        "investigator.name",
        "Главный исследователь",
        "Указывается в общих сведениях.",
        "ADMIN",
        "GENERAL",
        (MANUAL, DOCUMENT),
        required=False,
    ),
    # --- Products -----------------------------------------------------------
    _s(
        "test_product.name",
        "Исследуемый препарат",
        "Название препарата в разделе о препаратах и в дизайне.",
        "PRODUCTS",
        "PRODUCTS",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "test_product.active_substance",
        "Действующее вещество",
        "Определяет предмет исследования и аналит для биоаналитики.",
        "PRODUCTS",
        "PRODUCTS",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "test_product.dose",
        "Дозировка исследуемого препарата",
        "Доза должна совпадать с дозой препарата сравнения.",
        "PRODUCTS",
        "DOSING",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "test_product.dosage_form",
        "Лекарственная форма",
        "Определяет путь введения и условия приёма.",
        "PRODUCTS",
        "PRODUCTS",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "reference_product.name",
        "Препарат сравнения",
        "Референтный препарат обязателен для оценки биоэквивалентности.",
        "PRODUCTS",
        "PRODUCTS",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "reference_product.dose",
        "Дозировка препарата сравнения",
        "Сравнение проводится в одинаковой дозе.",
        "PRODUCTS",
        "DOSING",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "reference_product.marketing_authorization_holder",
        "Владелец регистрационного удостоверения препарата сравнения",
        "Подтверждает выбор референтного препарата.",
        "PRODUCTS",
        "PRODUCTS",
        (MANUAL, DOCUMENT),
        required=False,
    ),
    # --- Design -------------------------------------------------------------
    _s(
        "design.crossover",
        "Перекрёстный дизайн",
        "Определяет структуру периодов и статистическую модель.",
        "DESIGN",
        "DESIGN",
        (CHOICE, DOCUMENT),
        options=("Да", "Нет"),
    ),
    _s(
        "design.periods",
        "Число периодов",
        "Задаёт число приёмов препарата и объём отбора проб.",
        "DESIGN",
        "DESIGN",
        (MANUAL, DOCUMENT),
        numeric=True,
    ),
    _s(
        "design.sequences",
        "Последовательности приёма",
        "Определяет схему рандомизации.",
        "DESIGN",
        "DESIGN",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "washout.duration",
        "Период отмывки",
        "Между периодами должно пройти не менее 5 периодов полувыведения.",
        "DESIGN",
        "DESIGN",
        (DERIVED, MANUAL),
        unit="сут",
        note="Выводится из t½; при заданном t½ считается автоматически.",
    ),
    # --- Subjects -----------------------------------------------------------
    _s(
        "subjects.type",
        "Категория субъектов",
        "Определяет критерии включения.",
        "SUBJECTS",
        "SUBJECTS",
        (MANUAL, DOCUMENT),
        required=False,
    ),
    _s(
        "subjects.sex",
        "Пол субъектов",
        "Входит в критерии включения.",
        "SUBJECTS",
        "SUBJECTS",
        (MANUAL, DOCUMENT),
    ),
    _s(
        "subjects.age_min",
        "Минимальный возраст",
        "Входит в критерии включения.",
        "SUBJECTS",
        "SUBJECTS",
        (MANUAL, DOCUMENT),
        numeric=True,
        unit="лет",
    ),
    _s(
        "subjects.age_max",
        "Максимальный возраст",
        "Входит в критерии включения.",
        "SUBJECTS",
        "SUBJECTS",
        (MANUAL, DOCUMENT),
        numeric=True,
        unit="лет",
        required=False,
    ),
    _s(
        "subjects.randomized_n",
        "Число рандомизированных субъектов",
        "Сверяется с расчётным размером выборки.",
        "SUBJECTS",
        "SUBJECTS",
        (MANUAL, DOCUMENT),
        numeric=True,
    ),
    # --- PK and sampling ----------------------------------------------------
    _s(
        "pk.expected_tmax",
        "Ожидаемый Tmax",
        "Определяет частоту заборов вокруг предполагаемого Cmax.",
        "PK",
        "SAMPLING",
        (RESEARCH, MANUAL),
        unit="ч",
        gap_code="MISSING_TMAX_FOR_SAMPLING",
        note="Плановое значение из ОХЛП или литературы, а не наблюдаемый Tmax.",
    ),
    _s(
        "pk.expected_t_half",
        "Период полувыведения (t½)",
        "Задаёт длительность отбора проб и период отмывки.",
        "PK",
        "SAMPLING",
        (RESEARCH, MANUAL),
        unit="ч",
        numeric=True,
        gap_code="MISSING_HALF_LIFE_FOR_WASHOUT",
    ),
    _s(
        "pk.parameters",
        "Рассчитываемые PK-параметры",
        "Перечень параметров для расчёта и отчёта.",
        "PK",
        "PK",
        (CHOICE, DOCUMENT),
    ),
    _s(
        "sampling.times",
        "Схема отбора проб",
        "Точки отбора должны покрывать Cmax и терминальную фазу.",
        "PK",
        "SAMPLING",
        (DERIVED, MANUAL),
        note="Строится из Tmax и t½.",
    ),
    _s(
        "bioanalysis.analyte",
        "Определяемый аналит",
        "Биоаналитика и PK-параметры считаются для конкретного вещества.",
        "PK",
        "PK",
        (MANUAL, RESEARCH),
        gap_code="MISSING_ANALYTE",
    ),
    _s(
        "bioanalysis.matrix",
        "Биологическая матрица",
        "Обычно плазма крови; входит в раздел биоаналитики.",
        "PK",
        "PK",
        (MANUAL, DOCUMENT),
        required=False,
    ),
    # --- Food ---------------------------------------------------------------
    _s(
        "food.condition",
        "Условия приёма относительно пищи",
        "Натощак или после приёма пищи — определяет процедуры дня приёма.",
        "FOOD",
        "FOOD",
        (CHOICE, DOCUMENT),
        options=("FASTING", "FED", "BOTH"),
    ),
    _s(
        "food.calorie_target",
        "Состав стандартного приёма пищи",
        "Нужен только для fed-условий.",
        "FOOD",
        "FOOD",
        (RESEARCH, MANUAL),
        unit="ккал",
        required=False,
        gap_code="MISSING_MEAL_COMPOSITION",
    ),
    # --- Statistics ---------------------------------------------------------
    _s(
        "pk.primary_parameters",
        "Основные параметры биоэквивалентности",
        "По ним оценивается биоэквивалентность.",
        "STATS",
        "STATISTICS",
        (CHOICE,),
        gap_code="MISSING_PRIMARY_BE_SELECTION",
    ),
    _s(
        "cv_intra",
        "Внутрииндивидуальная вариабельность (CVintra)",
        "Без неё нельзя рассчитать размер выборки.",
        "STATS",
        "STATISTICS",
        (RESEARCH, MANUAL),
        unit="%",
        numeric=True,
        gap_code="MISSING_CVINTRA",
        requires_pk_parameter=True,
        note="Нужна именно within-subject вариабельность для конкретного PK-параметра.",
    ),
    _s(
        "statistics.method",
        "Статистическая модель",
        "Модель анализа основных параметров.",
        "STATS",
        "STATISTICS",
        (CHOICE,),
    ),
    _s(
        "statistics.transformation",
        "Преобразование данных",
        "Логарифмирование Cmax и AUC перед анализом.",
        "STATS",
        "STATISTICS",
        (CHOICE,),
        options=("LOG", "NONE"),
    ),
    _s(
        "statistics.confidence_interval",
        "Доверительный интервал",
        "Интервал для отношения средних геометрических.",
        "STATS",
        "STATISTICS",
        (CHOICE,),
    ),
    _s(
        "statistics.acceptance_interval",
        "Границы приемлемости",
        "Диапазон, в который должен попасть доверительный интервал.",
        "STATS",
        "STATISTICS",
        (MANUAL,),
    ),
    _s(
        "statistics.analysis_population",
        "Популяция анализа",
        "Правило включения субъектов в фармакокинетический анализ.",
        "STATS",
        "STATISTICS",
        (CHOICE,),
        options=ANALYSIS_POPULATIONS,
    ),
    _s(
        "sample_size.randomized_n",
        "Расчётный размер выборки",
        "Считается из CVintra по нормативным параметрам.",
        "STATS",
        "STATISTICS",
        (DERIVED,),
        numeric=True,
        note="Считается автоматически, как только задана CVintra.",
    ),
    # --- Safety -------------------------------------------------------------
    _s(
        "safety.monitoring",
        "Контроль безопасности",
        "Объём наблюдения за субъектами.",
        "SAFETY",
        "SAFETY",
        (MANUAL, DOCUMENT),
        required=False,
    ),
    _s(
        "safety.adverse_events",
        "Регистрация нежелательных явлений",
        "Порядок сбора и оценки нежелательных явлений.",
        "SAFETY",
        "SAFETY",
        (MANUAL, DOCUMENT),
        required=False,
    ),
)

SHEET_BY_KEY: dict[str, SheetSpec] = {s.key: s for s in SHEET_CATALOG}

# Field paths the decision context uses under a different name than the sheet
FACT_ALIASES: dict[str, tuple[str, ...]] = {
    "pk.expected_tmax": ("pk.Tmax",),
    "pk.expected_t_half": ("pk.t_half",),
    "cv_intra": ("cvintra", "statistics.cvintra"),
    "food.calorie_target": ("food.fat_target",),
}


def _fact_paths(spec: SheetSpec) -> tuple[str, ...]:
    return (spec.key,) + FACT_ALIASES.get(spec.key, ())


def _usable_value(spec: SheetSpec, value: Any) -> bool:
    """Extractors record a bare `True` to mean "the document mentions this".

    For a quantity that flag is not an answer: Tmax = True tells the writer
    nothing and must never make the row look filled.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return not (spec.numeric or spec.unit is not None)
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _display(value: Any, spec: SheetSpec) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if spec.key == "statistics.acceptance_interval" and isinstance(value, (list, tuple)):
        low, high = value
        scale = 100.0 if float(high) <= 2 else 1.0
        return f"{float(low) * scale:.2f}–{float(high) * scale:.2f}%".replace(".", ",")
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    text = str(value)
    if spec.key == "statistics.confidence_interval":
        try:
            return f"{float(value) * 100:.0f}%" if float(value) <= 1 else f"{float(value):.0f}%"
        except (TypeError, ValueError):
            return text
    if spec.unit and spec.unit not in text:
        return f"{text} {spec.unit}"
    return text


def _candidate_index(package: Any) -> dict[str, Any]:
    """Best candidate per field path from the uploaded documents."""
    if package is None:
        return {}
    prefer = {"SYNOPSIS": 3, "SYNOPSIS_DESIGN": 3, "DESIGN": 2, "SMPC": 2, "CHECKLIST": 1}
    best: dict[str, Any] = {}
    for c in package.candidates:
        if c.status == "REJECTED":
            continue
        current = best.get(c.field_path)
        if current is None:
            best[c.field_path] = c
            continue
        if c.status == "VERIFIED" and current.status != "VERIFIED":
            best[c.field_path] = c
        elif current.status != "VERIFIED" and prefer.get(c.document_type, 0) > prefer.get(
            current.document_type, 0
        ):
            best[c.field_path] = c
    return best


def _ai_proposals(study_id: str, spec: SheetSpec) -> list[dict[str, Any]]:
    """Research claims offered for this row but not yet confirmed by a human."""
    if spec.gap_code is None:
        return []
    meta = GAP_CATALOG.get(spec.gap_code)
    if meta is None:
        return []
    from app.domain.workspace_gaps import _claim_matches, _proposal

    out: list[dict[str, Any]] = []
    for claim in list_claims(study_id=study_id):
        if not _claim_matches(meta, claim):
            continue
        if claim.extraction_method == "MANUAL":
            continue
        if claim.verification_status == "VERIFIED":
            continue
        out.append(_proposal(claim))
    return out


def _derived_value(study_id: str, spec: SheetSpec, facts: dict[str, Any]) -> Any:
    if spec.key == "sample_size.randomized_n":
        calcs = list_calculations(study_id)
        latest = calcs[-1] if calcs else None
        return latest.randomized_n if latest else None
    if spec.key == "washout.duration":
        half_life = facts.get("pk.expected_t_half") or facts.get("pk.t_half")
        try:
            hours = float(half_life) * 5.0
        except (TypeError, ValueError):
            return None
        return round(hours / 24.0, 1)
    return None


def _conflict_choices(conflict: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The competing values, so the row itself can carry the choice."""
    if not conflict:
        return []
    out: list[dict[str, Any]] = []
    for value, source in (
        (conflict.get("value_a"), conflict.get("source_a")),
        (conflict.get("value_b"), conflict.get("source_b")),
    ):
        if value is None:
            continue
        out.append({"value": value, "source": source, "display": str(value)})
    return out


def _row_options(spec: SheetSpec) -> list[str]:
    if spec.options:
        return list(spec.options)
    if spec.key == "pk.primary_parameters":
        return list(SAMPLE_SIZE_PK_PARAMETERS)
    if spec.key == "cv_intra":
        return []
    return []


def build_input_sheet(study_id: str, *, package_id: str | None = None) -> dict[str, Any]:
    """Everything the protocol needs, in one list, with the source of each value."""
    ctx = get_context(study_id, package_id=package_id)
    facts: dict[str, Any] = dict(getattr(ctx, "structured_facts", {}) or {})
    sources: dict[str, str] = dict(getattr(ctx, "fact_sources", {}) or {})

    package = find_study_package(study_id, package_id)
    candidates = _candidate_index(package)
    conflict_fields = {
        str(c.get("field") or c.get("field_path")): c
        for c in aggregate_conflicts(study_id, package_id=package_id)
        if str(c.get("status") or "OPEN") == "OPEN"
    }

    rows: list[dict[str, Any]] = []
    for spec in SHEET_CATALOG:
        paths = _fact_paths(spec)
        conflict = next((conflict_fields[p] for p in paths if p in conflict_fields), None)

        value: Any = None
        origin: str | None = None
        source_text: str | None = None
        for path in paths:
            candidate_value = facts.get(path)
            if _usable_value(spec, candidate_value):
                value = candidate_value
                origin = sources.get(path)
                break

        proposals = _ai_proposals(study_id, spec)

        if conflict is not None:
            status = CONFLICT
            source_text = "Документы дают разные значения — выберите верное"
            value = None
        elif value is not None:
            # A value from the writer's own document counts as supplied. Only a
            # value the platform found elsewhere asks for a human look.
            if origin in {REGULATORY, CONVENTION}:
                status = FROM_REGULATION
                spec_default = default_for(spec.key)
                source_text = spec_default.citation if spec_default else "Норматив"
            elif origin == "EXPERT_INPUT":
                status = FROM_EXPERT
                source_text = "Внесено экспертом"
            elif origin in DOCUMENT_SOURCES:
                status = FROM_DOCUMENT
                source_text = f"Из документа: {origin}"
            else:
                cand = next((candidates[p] for p in paths if p in candidates), None)
                if cand is not None:
                    status = FROM_DOCUMENT
                    source_text = f"Из документа: {cand.document_type}"
                else:
                    status = NEEDS_CONFIRM
                    source_text = "Предложено платформой — нужна проверка"
        elif DERIVED in spec.fill and (derived := _derived_value(study_id, spec, facts)) is not None:
            status = COMPUTED
            value = derived
            source_text = "Рассчитано платформой"
        elif proposals:
            status = NEEDS_CONFIRM
            source_text = "Найдено ИИ в открытых источниках — нужна проверка"
        else:
            status = MISSING
            source_text = None

        rows.append(
            {
                "key": spec.key,
                "title": spec.title,
                "why": spec.why,
                "note": spec.note,
                "group": spec.group,
                "group_title": GROUP_TITLES[spec.group],
                "section": spec.section,
                "unit": spec.unit,
                "numeric": spec.numeric,
                "required": spec.required,
                "fill": list(spec.fill),
                "options": _row_options(spec),
                "requires_pk_parameter": spec.requires_pk_parameter,
                "pk_parameter_options": list(SAMPLE_SIZE_PK_PARAMETERS)
                if spec.requires_pk_parameter
                else [],
                "value": value if not isinstance(value, tuple) else list(value),
                "display": _display(value, spec),
                "status": status,
                "ready": status in READY_STATUSES,
                "source": source_text,
                "proposals": proposals,
                "conflict": conflict,
                "conflict_choices": _conflict_choices(conflict),
                "gap_code": spec.gap_code,
            }
        )

    required_rows = [r for r in rows if r["required"]]
    missing_required = [r for r in required_rows if not r["ready"]]
    groups = [
        {
            "id": gid,
            "title": title,
            "total": len([r for r in rows if r["group"] == gid]),
            "ready": len([r for r in rows if r["group"] == gid and r["ready"]]),
        }
        for gid, title in GROUPS
    ]

    return {
        "study_id": study_id,
        "analysed": bool(package and package.candidates),
        "groups": groups,
        "rows": rows,
        "counts": {
            "total": len(rows),
            "ready": len([r for r in rows if r["ready"]]),
            "required": len(required_rows),
            "required_ready": len(required_rows) - len(missing_required),
            "missing": len([r for r in rows if r["status"] == MISSING]),
            "needs_confirm": len([r for r in rows if r["status"] == NEEDS_CONFIRM]),
            "conflicts": len([r for r in rows if r["status"] == CONFLICT]),
        },
        # A draft is always available; only the final version needs a full sheet
        "can_draft": True,
        "can_finalize": not missing_required,
        "blocking": [
            {"key": r["key"], "title": r["title"], "status": r["status"]}
            for r in missing_required
        ],
        "study_mutated": False,
    }


def fill_row(
    study_id: str,
    key: str,
    *,
    value: Any,
    actor: str,
    rationale: str = "",
    unit: str | None = None,
    pk_parameter: str | None = None,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Write one row. Gap-backed rows keep the audited research/claim machinery."""
    spec = SHEET_BY_KEY.get(key)
    if spec is None:
        raise ValueError(f"Неизвестная строка ведомости: {key}")
    if DERIVED in spec.fill and len(spec.fill) == 1:
        raise ValueError(f"«{spec.title}» рассчитывается платформой и не вводится вручную")
    if not str(actor or "").strip():
        raise ValueError("Требуется автор ввода")

    if spec.gap_code and spec.gap_code in GAP_CATALOG:
        meta = GAP_CATALOG[spec.gap_code]
        if MANUAL in meta["resolution"]:
            return resolve_gap_manually(
                study_id,
                spec.gap_code,
                value=value,
                rationale=rationale or f"Внесено экспертом: {spec.title}",
                actor=actor,
                unit=unit or spec.unit,
                pk_parameter=pk_parameter,
                package_id=package_id,
            )

    return _write_fact(
        study_id,
        spec,
        value,
        actor=actor,
        package_id=package_id,
    )


def _coerce(value: Any, spec: SheetSpec) -> Any:
    if spec.numeric:
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"«{spec.title}»: ожидается число") from exc
    if spec.options and isinstance(value, str) and value not in spec.options:
        # Yes/No rows are stored as booleans
        if set(spec.options) == {"Да", "Нет"}:
            return value == "Да"
        raise ValueError(f"«{spec.title}»: допустимые значения — {', '.join(spec.options)}")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"«{spec.title}»: значение обязательно")
    return value


def _write_fact(
    study_id: str,
    spec: SheetSpec,
    value: Any,
    *,
    actor: str,
    package_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_context(study_id, package_id=package_id)
    if ctx is None:
        raise ValueError("Сначала загрузите и интерпретируйте документы")

    coerced = _coerce(value, spec)
    applied = [spec.key]
    ctx.structured_facts[spec.key] = coerced
    ctx.fact_statuses[spec.key] = "VERIFIED"
    ctx.fact_sources[spec.key] = "EXPERT_INPUT"
    for alias in FACT_ALIASES.get(spec.key, ()):
        ctx.structured_facts[alias] = coerced
        ctx.fact_statuses[alias] = "VERIFIED"
        ctx.fact_sources[alias] = "EXPERT_INPUT"
        applied.append(alias)

    previous = list_decisions(study_id, package_id=package_id)
    result = recompute_affected_decisions(ctx, applied_fields=applied, previous=previous)
    put_context(study_id, ctx, package_id=package_id)
    decisions = result["decisions"]
    if decisions:
        put_decisions(study_id, decisions, package_id=package_id)

    return {
        "key": spec.key,
        "value": coerced,
        "applied_fields": applied,
        "recomputed_domains": result.get("recomputed_domains") or [],
        "actor": actor,
        "study_mutated": False,
    }


# What a re-read of the documents must not throw away
PRESERVED_SOURCES: frozenset[str] = frozenset({"EXPERT_INPUT", REGULATORY, CONVENTION})


def preserved_facts(study_id: str, package_id: str | None = None) -> list[tuple[str, Any, str]]:
    """Facts a person entered, or the regulation supplied, with their provenance."""
    ctx = get_context(study_id, package_id=package_id)
    if ctx is None:
        return []
    sources = dict(getattr(ctx, "fact_sources", {}) or {})
    facts = dict(getattr(ctx, "structured_facts", {}) or {})
    return [
        (path, facts[path], source)
        for path, source in sources.items()
        if source in PRESERVED_SOURCES and path in facts
    ]


def restore_preserved_facts(ctx: Any, preserved: list[tuple[str, Any, str]]) -> None:
    """Re-extraction may add documents, but it must never lose expert input."""
    for path, value, source in preserved:
        ctx.structured_facts[path] = value
        ctx.fact_statuses[path] = "VERIFIED"
        ctx.fact_sources[path] = source
        if path in {"pk.expected_tmax", "pk.Tmax"}:
            ctx.tmax = value
        elif path in {"pk.expected_t_half", "pk.t_half"}:
            ctx.half_life = value
        elif path == "cv_intra":
            ctx.cvintra = value


def refresh_context_from_package(study_id: str, package: Any) -> dict[str, Any]:
    """Rebuild the decision context from the documents, keeping supplied values.

    Called after anything that changes what the documents say — an upload, or a
    resolved conflict — so the sheet reflects the change on the next read
    instead of after another trip through the pipeline.
    """
    from app.domain.decision_context import build_context_from_package
    from app.domain.decision_engine import recompute_decisions

    preserved = preserved_facts(study_id, package.package_id)
    ctx = build_context_from_package(package, study_id=study_id or package.study_id)
    restore_preserved_facts(ctx, preserved)
    put_context(study_id, ctx, package_id=package.package_id)
    decisions = recompute_decisions(ctx)
    put_decisions(study_id, decisions, package_id=package.package_id)
    return {"package_id": package.package_id, "decisions": len(decisions)}


def resolve_conflict_row(
    study_id: str,
    key: str,
    *,
    value: Any,
    actor: str,
    rationale: str,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Pick the right value when the documents disagree, without leaving the row.

    The choice goes through the same conflict machinery the review screen uses,
    so the audit trail and the "never auto-resolve" guard both stay intact.
    """
    from app.domain.study_input_conflicts import FieldConflict, resolve_conflict
    from app.domain.study_input_coverage import build_input_coverage
    from app.domain.study_input_package import verify_candidate
    from app.domain.study_input_store import put_package

    spec = SHEET_BY_KEY.get(key)
    if spec is None:
        raise ValueError(f"Неизвестная строка ведомости: {key}")
    if not str(rationale or "").strip():
        raise ValueError("Обоснование выбора обязательно")
    if not str(actor or "").strip():
        raise ValueError("Требуется автор выбора")

    package = find_study_package(study_id, package_id)
    if package is None:
        raise ValueError("Пакет документов не найден")

    paths = set(_fact_paths(spec))
    raw = next(
        (
            c
            for c in package.conflicts
            if str(c.get("field_path")) in paths and str(c.get("status") or "OPEN") == "OPEN"
        ),
        None,
    )
    if raw is None:
        raise ValueError(f"Для «{spec.title}» нет открытого противоречия")

    chosen = None
    for candidate_id in raw.get("candidate_ids") or []:
        candidate = next((c for c in package.candidates if c.id == candidate_id), None)
        if candidate is not None and str(candidate.value) == str(value):
            chosen = candidate
            break
    if chosen is None:
        raise ValueError("Выбранное значение не встречается ни в одном документе")

    conflict = FieldConflict(
        conflict_id=str(raw["conflict_id"]),
        field_path=str(raw["field_path"]),
        candidate_ids=list(raw.get("candidate_ids") or []),
        values=list(raw.get("values") or []),
        sources=list(raw.get("sources") or []),
        status=str(raw.get("status") or "OPEN"),
        outcome=raw.get("outcome"),
        severity=str(raw.get("severity") or "HIGH"),
    )
    resolve_conflict(
        conflict,
        reviewer=actor,
        outcome="SELECT_VALUE",
        reason=rationale,
        selected_candidate_id=chosen.id,
    )
    verify_candidate(chosen, reviewer=actor)
    package.conflicts = [
        conflict.to_dict() if c.get("conflict_id") == conflict.conflict_id else c
        for c in package.conflicts
    ]
    package.coverage = build_input_coverage(package)
    put_package(package)
    # The chosen value is now unambiguous — let the context pick it up at once
    refresh_context_from_package(study_id, package)
    fill_regulatory_defaults(study_id, package_id=package.package_id)

    return {
        "key": spec.key,
        "field_path": conflict.field_path,
        "value": chosen.value,
        "conflict_id": conflict.conflict_id,
        "selected_candidate_id": chosen.id,
        "actor": actor,
        "study_mutated": False,
    }


def fill_regulatory_defaults(
    study_id: str,
    *,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Put the values the regulation prescribes into the context.

    Called by the orchestrator right after interpretation, so the writer never
    types a constant that the EAEU rules already fixed.
    """
    ctx = get_context(study_id, package_id=package_id)
    if ctx is None:
        return {"applied_fields": [], "recomputed_domains": []}
    applied = apply_defaults_to_context(ctx)
    if not applied:
        return {"applied_fields": [], "recomputed_domains": []}
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


def unresolved_for_protocol(study_id: str, *, package_id: str | None = None) -> list[dict[str, Any]]:
    """Rows a draft must mark as not yet supplied, instead of silently omitting."""
    sheet = build_input_sheet(study_id, package_id=package_id)
    return [
        {"key": r["key"], "title": r["title"], "section": r["section"], "status": r["status"]}
        for r in sheet["rows"]
        if not r["ready"] and r["required"]
    ]


def statistics_plan_status(study_id: str) -> str | None:
    plan = latest_statistics_plan(study_id)
    return plan.status if plan else None
