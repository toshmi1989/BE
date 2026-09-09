"""Protocol Decision Engine vocabulary — Phase 15.0.

Internal enums only. Human UI must use OPTION_LABELS_RU / display helpers.
No medical thresholds invented here.
"""

from __future__ import annotations

DECISION_DOMAINS: tuple[str, ...] = (
    "DESIGN",
    "FOOD",
    "WASHOUT",
    "SAMPLING",
    "ANALYTE_PK",
)

DECISION_STATUSES: tuple[str, ...] = (
    "DRAFT",
    "REVIEW_REQUIRED",
    "APPROVED",
    "REJECTED",
    "SUPERSEDED",
    "BLOCKED",
)

RECOMMENDATION_STATUSES: tuple[str, ...] = (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONTRADICTED",
    "BLOCKED",
)

CONFIDENCE_LEVELS: tuple[str, ...] = ("HIGH", "MEDIUM", "LOW", "NONE")

EVIDENCE_TYPES: tuple[str, ...] = (
    "REGULATORY_CLAIM",
    "REGULATORY_RULE",
    "PRODUCT_FACT",
    "SMPC_FACT",
    "LITERATURE_CLAIM",
    "ANALOGUE_STUDY",
    "PREVIOUS_PROTOCOL",
    "EXPERT_INTERVIEW",
    "EXPERT_RULE",
    "EXPERT_DECISION",
    "STRUCTURED_STUDY_FACT",
)

SUPPORT_LEVELS: tuple[str, ...] = (
    "SUPPORTS",
    "CONTRADICTS",
    "NEUTRAL",
    "CONTEXT_ONLY",
)

# Decision options by domain (internal)
DESIGN_OPTIONS: tuple[str, ...] = (
    "STANDARD_2X2_CROSSOVER",
    "REPLICATE_CROSSOVER",
    "ADAPTIVE_DESIGN",
    "PARALLEL_DESIGN",
)

FOOD_OPTIONS: tuple[str, ...] = (
    "FASTING",
    "FED",
    "FASTING_AND_FED",
    "FOOD_CONDITION_REQUIRES_EXPERT_DECISION",
)

WASHOUT_OPTIONS: tuple[str, ...] = (
    "FIXED_DURATION",
    "HALF_LIFE_DERIVED",
    "EXPERT_DEFINED",
    "INSUFFICIENT_EVIDENCE",
)

SAMPLING_OPTIONS: tuple[str, ...] = (
    "STANDARD_PROFILE",
    "EXTENDED_TERMINAL_PHASE",
    "ADAPTIVE_SAMPLING",
    "EXPERT_DEFINED",
)

ANALYTE_OPTIONS: tuple[str, ...] = (
    "PARENT_DRUG",
    "PARENT_AND_METABOLITE",
    "ACTIVE_METABOLITE",
    "ENDOGENOUS_ANALYTE",
    "EXPERT_DEFINED",
)

DOMAIN_OPTIONS: dict[str, tuple[str, ...]] = {
    "DESIGN": DESIGN_OPTIONS,
    "FOOD": FOOD_OPTIONS,
    "WASHOUT": WASHOUT_OPTIONS,
    "SAMPLING": SAMPLING_OPTIONS,
    "ANALYTE_PK": ANALYTE_OPTIONS,
}

# Human-readable labels (Russian) — never expose enums in UI
OPTION_LABELS_RU: dict[str, str] = {
    "STANDARD_2X2_CROSSOVER": "Стандартное перекрёстное двухпериодное исследование",
    "REPLICATE_CROSSOVER": "Репликативное перекрёстное исследование",
    "ADAPTIVE_DESIGN": "Адаптивный дизайн",
    "PARALLEL_DESIGN": "Параллельный дизайн",
    "FASTING": "Натощак",
    "FED": "После приёма пищи",
    "FASTING_AND_FED": "Натощак и после приёма пищи",
    "FOOD_CONDITION_REQUIRES_EXPERT_DECISION": "Условия приёма пищи требуют решения эксперта",
    "FIXED_DURATION": "Фиксированная длительность отмывочного периода",
    "HALF_LIFE_DERIVED": "Отмывочный период, рассчитанный по периоду полувыведения",
    "EXPERT_DEFINED": "Определено экспертом",
    "INSUFFICIENT_EVIDENCE": "Недостаточно доказательств",
    "STANDARD_PROFILE": "Стандартный профиль отбора проб",
    "EXTENDED_TERMINAL_PHASE": "Расширенная терминальная фаза",
    "ADAPTIVE_SAMPLING": "Адаптивный отбор проб",
    "PARENT_DRUG": "Исходное вещество (parent)",
    "PARENT_AND_METABOLITE": "Исходное вещество и метаболит",
    "ACTIVE_METABOLITE": "Активный метаболит",
    "ENDOGENOUS_ANALYTE": "Эндогенный аналит",
}

DOMAIN_LABELS_RU: dict[str, str] = {
    "DESIGN": "Дизайн исследования",
    "FOOD": "Условия приёма пищи",
    "WASHOUT": "Отмывочный период",
    "SAMPLING": "Отбор проб",
    "ANALYTE_PK": "Аналит / ФК",
}

RECOMMENDATION_STATUS_LABELS_RU: dict[str, str] = {
    "SUPPORTED": "Поддержано доказательствами",
    "PARTIALLY_SUPPORTED": "Частично поддержано",
    "INSUFFICIENT_EVIDENCE": "Недостаточно доказательств",
    "CONTRADICTED": "Противоречит доказательствам",
    "BLOCKED": "Заблокировано",
}

DECISION_STATUS_LABELS_RU: dict[str, str] = {
    "DRAFT": "Черновик",
    "REVIEW_REQUIRED": "Требуется проверка",
    "APPROVED": "Утверждено",
    "REJECTED": "Отклонено",
    "SUPERSEDED": "Устарело",
    "BLOCKED": "Заблокировано",
}

# Fields whose OPEN conflicts block product-identity-dependent decisions
CRITICAL_CONFLICT_FIELDS: frozenset[str] = frozenset(
    {
        "reference_product.dose",
        "reference_product.name",
        "test_product.dose",
    }
)

# DEPRECATED Phase 15.1: do not use for global blocking.
# Dependency registry (decision_dependency.DECISION_DEPENDENCY_REGISTRY) is SoT.
DOMAINS_BLOCKED_BY_REF_CONFLICT: frozenset[str] = frozenset()


def display_option(option: str) -> str:
    return OPTION_LABELS_RU.get(option, option)


def display_domain(domain: str) -> str:
    return DOMAIN_LABELS_RU.get(domain, domain)


def assert_no_enum_in_user_text(text: str) -> None:
    """Hard negative helper: user-facing strings must not leak internal enums."""
    forbidden = set(DESIGN_OPTIONS) | set(FOOD_OPTIONS) | set(WASHOUT_OPTIONS) | set(SAMPLING_OPTIONS) | set(
        ANALYTE_OPTIONS
    )
    for enum in forbidden:
        if enum in text:
            raise AssertionError(f"Internal enum leaked to user text: {enum}")
