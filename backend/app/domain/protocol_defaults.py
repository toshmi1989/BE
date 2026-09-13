"""Regulatory defaults for an EAEU bioequivalence protocol — Phase 30.

A value belongs here only when a regulation prescribes it, or when the field
agrees on it as a planning assumption. Drug-specific quantities — Tmax, t½,
CVintra, the analyte, meal composition — are deliberately absent: no regulation
states them, so nothing here may invent them.

Every default carries the citation that justifies it and stays editable by the
expert. The point is to stop asking the writer to type constants the regulation
already fixed, not to hide where a value came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Provenance kinds. REGULATORY already exists in the statistics SOURCE_ROLES
# vocabulary; CONVENTION marks a planning assumption that is not law.
REGULATORY = "REGULATORY_REQUIREMENT"
CONVENTION = "PLANNING_CONVENTION"

EAEU_BE_RULES = (
    "Правила проведения исследований биоэквивалентности лекарственных препаратов "
    "в рамках ЕАЭС (Решение Совета ЕЭК № 85 от 03.11.2016)"
)

PLANNING_PRACTICE = "Общепринятое допущение при планировании исследования БЭ"


@dataclass(frozen=True)
class ProtocolDefault:
    """One value the writer should not have to type, with the reason it is there."""

    field_path: str
    title: str
    value: Any
    kind: str
    citation: str
    unit: str | None = None
    note: str | None = None

    @property
    def is_regulatory(self) -> bool:
        return self.kind == REGULATORY

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": self.field_path,
            "title": self.title,
            "value": self.value,
            "kind": self.kind,
            "citation": self.citation,
            "unit": self.unit,
            "note": self.note,
            "editable": True,
        }


def _d(
    field_path: str,
    title: str,
    value: Any,
    kind: str,
    citation: str,
    *,
    unit: str | None = None,
    note: str | None = None,
) -> ProtocolDefault:
    return ProtocolDefault(
        field_path=field_path,
        title=title,
        value=value,
        kind=kind,
        citation=citation,
        unit=unit,
        note=note,
    )


DEFAULTS: dict[str, ProtocolDefault] = {
    d.field_path: d
    for d in (
        _d(
            "pk.primary_parameters",
            "Основные параметры биоэквивалентности",
            ["Cmax", "AUC0-t"],
            REGULATORY,
            f"{EAEU_BE_RULES}: биоэквивалентность оценивают по Cmax и AUC0-t",
            note="Для препаратов с модифицированным высвобождением набор может отличаться.",
        ),
        _d(
            "statistics.analysis_population",
            "Популяция анализа",
            "PK_ANALYSIS_SET",
            REGULATORY,
            f"{EAEU_BE_RULES}: в фармакокинетический анализ включают субъектов "
            "с оцениваемыми профилями концентраций в обоих периодах",
        ),
        _d(
            "statistics.confidence_interval",
            "Доверительный интервал",
            0.90,
            REGULATORY,
            f"{EAEU_BE_RULES}: двусторонний 90% доверительный интервал",
            unit="%",
        ),
        _d(
            "statistics.acceptance_interval",
            "Границы приемлемости биоэквивалентности",
            # Both engines work on the ratio scale; the percent form is wording only
            (0.80, 1.25),
            REGULATORY,
            f"{EAEU_BE_RULES}: 80,00–125,00% для отношения средних геометрических",
            unit="%",
            note="Для препаратов с узким терапевтическим индексом границы сужаются.",
        ),
        _d(
            "statistics.transformation",
            "Преобразование данных",
            "LOG",
            REGULATORY,
            f"{EAEU_BE_RULES}: Cmax и AUC анализируют после логарифмического преобразования",
        ),
        _d(
            "statistics.method",
            "Статистическая модель",
            "ANOVA_LOG_2X2",
            REGULATORY,
            f"{EAEU_BE_RULES}: дисперсионный анализ (ANOVA) логарифмированных данных "
            "перекрёстного исследования 2×2",
        ),
        _d(
            "statistics.power",
            "Мощность исследования",
            0.80,
            REGULATORY,
            f"{EAEU_BE_RULES}: мощность исследования не менее 80%",
            unit="%",
        ),
        _d(
            "pk.parameters",
            "Рассчитываемые фармакокинетические параметры",
            ["Cmax", "AUC0-t", "AUC0-inf", "Tmax", "t1/2", "kel"],
            REGULATORY,
            f"{EAEU_BE_RULES}: стандартный набор параметров для отчёта об исследовании БЭ",
        ),
        _d(
            "washout.min_half_lives",
            "Минимальная длительность отмывки",
            5,
            REGULATORY,
            f"{EAEU_BE_RULES}: период отмывки не менее 5 периодов полувыведения",
            unit="периодов полувыведения",
            note="Рассчитывается из t½, поэтому без t½ длительность в часах не выводится.",
        ),
        _d(
            "sample_size.expected_ratio",
            "Ожидаемое отношение средних (GMR)",
            0.95,
            CONVENTION,
            f"{PLANNING_PRACTICE}: GMR 0,95 как консервативное отклонение от единицы",
            note="Норматив значения не задаёт — это допущение планирования.",
        ),
        _d(
            "sample_size.dropout_percent",
            "Допущение по выбыванию субъектов",
            10.0,
            CONVENTION,
            f"{PLANNING_PRACTICE}: запас 10% на выбывание субъектов",
            unit="%",
            note="Норматив значения не задаёт — это допущение планирования.",
        ),
    )
}

# Facts the defaults write into the decision context. Sample-size assumptions are
# passed to the calculator as arguments instead, so they are not context facts.
CONTEXT_DEFAULT_PATHS: tuple[str, ...] = (
    "pk.primary_parameters",
    "pk.parameters",
    "statistics.analysis_population",
    "statistics.confidence_interval",
    "statistics.acceptance_interval",
    "statistics.transformation",
    "statistics.method",
)


def default_for(field_path: str) -> ProtocolDefault | None:
    return DEFAULTS.get(field_path)


def regulated_field_paths() -> frozenset[str]:
    """Every field the platform can fill without asking the writer."""
    return frozenset(DEFAULTS)


def statistics_plan_defaults() -> dict[str, Any]:
    """Keyword arguments for `recompute_statistics_plan`.

    The regulation is a verified rule, which is exactly the provenance the
    statistics engine accepts for a PRIMARY BE selection.
    """
    return {
        "confidence_level": DEFAULTS["statistics.confidence_interval"].value,
        "confidence_level_source": REGULATORY,
        "acceptance_interval": DEFAULTS["statistics.acceptance_interval"].value,
        "acceptance_source": REGULATORY,
        "acceptance_wording": f"{ACCEPTANCE_WORDING} (ЕАЭС)",
        "transformation": DEFAULTS["statistics.transformation"].value,
        "transformation_source": REGULATORY,
        "model": DEFAULTS["statistics.method"].value,
        "model_source": REGULATORY,
        "analysis_population": DEFAULTS["statistics.analysis_population"].value,
        "analysis_population_source": REGULATORY,
        "primary_be_parameters": list(DEFAULTS["pk.primary_parameters"].value),
        "primary_be_source": "VERIFIED_RULE",
    }


ACCEPTANCE_WORDING = "80,00–125,00%"


def sample_size_defaults() -> dict[str, Any]:
    """Keyword arguments for `calculate_sample_size_authoritative`.

    Alpha follows from the 90% interval by the engine's own TOST rule, so it is
    stated here with the same regulatory provenance rather than re-derived.
    """
    ci = float(DEFAULTS["statistics.confidence_interval"].value)
    lower, upper = DEFAULTS["statistics.acceptance_interval"].value
    return {
        "expected_ratio": DEFAULTS["sample_size.expected_ratio"].value,
        "expected_ratio_source": CONVENTION,
        "alpha": round((1.0 - ci) / 2.0, 12),
        "alpha_source": REGULATORY,
        "power": DEFAULTS["statistics.power"].value,
        "power_source": REGULATORY,
        "be_lower": float(lower),
        "be_upper": float(upper),
        "be_limits_source": REGULATORY,
        "dropout_percent": DEFAULTS["sample_size.dropout_percent"].value,
        "dropout_source": CONVENTION,
        "inflation_method": "DIVIDE_BY_RETAINMENT_RATE",
    }


def apply_defaults_to_context(ctx: Any) -> list[str]:
    """Fill regulated facts the documents did not provide. Never overwrites.

    Returns the field paths that were filled, so the caller can recompute only
    what actually changed and record the act in the audit trail.
    """
    if ctx is None:
        return []
    facts = getattr(ctx, "structured_facts", None)
    if not isinstance(facts, dict):
        return []
    statuses = getattr(ctx, "fact_statuses", None)
    sources = getattr(ctx, "fact_sources", None)

    applied: list[str] = []
    for path in CONTEXT_DEFAULT_PATHS:
        spec = DEFAULTS[path]
        if facts.get(path) is not None:
            continue
        value = spec.value
        if path == "statistics.acceptance_interval":
            # Context facts are what extraction produces — keep the readable wording
            value = "80.00-125.00"
        elif isinstance(value, tuple):
            value = list(value)
        elif isinstance(value, list):
            value = list(value)
        facts[path] = value
        if isinstance(statuses, dict):
            statuses[path] = "VERIFIED"
        if isinstance(sources, dict):
            sources[path] = spec.kind
        applied.append(path)
    return applied
