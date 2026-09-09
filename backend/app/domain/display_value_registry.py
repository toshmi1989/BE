"""DisplayValueRegistry — centralized enum/code → human-readable text.

Status of translations is PROPOSED workflow text until a verified linguistic/
regulatory source is attached. Never emit raw enum codes into protocol DOCX.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DisplayValue:
    code: str
    language: str
    human_text: str
    context: str
    version: str = "1"
    status: str = "PROPOSED"  # not VERIFIED regulatory


# code → DisplayValue (default language ru, context=general unless noted)
_REGISTRY: dict[tuple[str, str, str], DisplayValue] = {}


def _reg(code: str, human_text: str, *, context: str = "general", language: str = "ru") -> None:
    _REGISTRY[(code, language, context)] = DisplayValue(
        code=code,
        language=language,
        human_text=human_text,
        context=context,
    )


# Design
_reg(
    "CROSSOVER_2X2",
    "рандомизированное открытое перекрёстное двухпериодное двухпоследовательное исследование",
    context="design",
)
_reg("CROSSOVER_2X2", "перекрёстный 2×2", context="design_short")
_reg(
    "CROSSOVER_2X2",
    "двухпериодное перекрёстное исследование 2×2",
    context="design_long",
)
_reg(
    "REPLICATE_2X2X4",
    "репликативное перекрёстное исследование 2×2×4",
    context="design",
)
_reg("PARALLEL", "параллельное исследование", context="design")
_reg("ADAPTIVE", "адаптивное исследование", context="design")
_reg("CUSTOM", "исследование с пользовательским дизайном", context="design")
_reg(
    "REPLICATE_2X2X4",
    "репликативное четырёхпериодное перекрёстное исследование 2×2×4",
    context="design_long",
)

# AUC / PK semantic display (PROPOSED linguistic mapping)
_reg("AUC_0_LAST", "AUC0-x", context="auc")
_reg("AUC_0_72H", "AUC0-72", context="auc")
_reg("AUC_0_INF", "AUC0-inf", context="auc")
_reg("AUC_0_LAST_OVER_INF", "AUC0-x/AUC0-inf", context="auc")
_reg("AUC_0_72H_OVER_INF", "AUC0-72/AUC0-inf", context="auc")

# Food
_reg("FED", "после приёма пищи", context="food")
_reg("FASTING", "натощак", context="food")
_reg("FASTING_AND_FED", "натощак и после приёма пищи", context="food")
_reg("HIGH_CALORIE", "высококалорийный завтрак", context="meal")
_reg("STANDARD", "стандартный приём пищи", context="meal")
_reg("LOW_FAT", "низкожировой приём пищи", context="meal")

# Sampling reasons
_reg("BASELINE", "исходный уровень (до дозы)", context="sampling_reason")
_reg("ABSORPTION", "фаза абсорбции", context="sampling_reason")
_reg("TMAX_CAPTURE", "захват Tmax", context="sampling_reason")
_reg("DISTRIBUTION", "фаза распределения", context="sampling_reason")
_reg("TERMINAL_PHASE", "терминальная фаза элиминации", context="sampling_reason")
_reg("FINAL", "финальная точка наблюдения", context="sampling_reason")

# Reference purchased
_reg("PURCHASED", "закуплен", context="purchased_status")
_reg("NOT_PURCHASED", "не закуплен", context="purchased_status")
_reg("UNKNOWN", "статус закупки неизвестен", context="purchased_status")
_reg("PLANNED", "планируется закупка", context="purchased_status")

# Blinding / selection
_reg("OPEN", "открытое исследование (без маскировки)", context="blinding")
_reg("OPEN_LABEL", "открытое исследование (без маскировки)", context="blinding")
_reg("DOUBLE_BLIND", "двойное слепое исследование", context="blinding")
_reg("SINGLE_BLIND", "простое слепое исследование", context="blinding")
_reg("SINGLE_STUDY", "на основании одного исследования", context="selection_method")
_reg("META_ANALYSIS", "мета-анализ", context="selection_method")
_reg("SmPC", "инструкция по медицинскому применению (SmPC)", context="source_type")
_reg("GUIDELINE", "руководство / guideline", context="source_type")
_reg("PUBLICATION", "публикация", context="source_type")
_reg("REGULATORY", "регуляторный источник", context="source_type")

# Known raw enums that must never appear verbatim in DOCX body
RAW_ENUM_CODES: frozenset[str] = frozenset(
    {
        "CROSSOVER_2X2",
        "REPLICATE_2X2X4",
        "PARALLEL",
        "ADAPTIVE",
        "FED",
        "FASTING",
        "FASTING_AND_FED",
        "HIGH_CALORIE",
        "BASELINE",
        "ABSORPTION",
        "TMAX_CAPTURE",
        "DISTRIBUTION",
        "TERMINAL_PHASE",
        "FINAL",
        "NOT_PURCHASED",
        "PURCHASED",
    }
)


def resolve_display(
    code: str | None,
    *,
    context: str = "general",
    language: str = "ru",
    fallback: str | None = None,
) -> str:
    """HumanReadableValueResolver — single entry point for display strings."""
    if code is None or code == "":
        return fallback if fallback is not None else ""
    key = (str(code), language, context)
    if key in _REGISTRY:
        return _REGISTRY[key].human_text
    # try general context
    gen = (str(code), language, "general")
    if gen in _REGISTRY:
        return _REGISTRY[gen].human_text
    if fallback is not None:
        return fallback
    return str(code)


def get_display_value(
    code: str, *, context: str = "general", language: str = "ru"
) -> DisplayValue | None:
    return _REGISTRY.get((code, language, context)) or _REGISTRY.get((code, language, "general"))


def list_display_values() -> list[dict[str, Any]]:
    return [
        {
            "code": v.code,
            "language": v.language,
            "human_text": v.human_text,
            "context": v.context,
            "version": v.version,
            "status": v.status,
        }
        for v in sorted(_REGISTRY.values(), key=lambda x: (x.code, x.context))
    ]


def find_raw_enums_in_text(text: str) -> list[str]:
    """Detect forbidden raw enum tokens in document text (word-boundary-ish)."""
    import re

    found: list[str] = []
    for code in RAW_ENUM_CODES:
        # Match as whole token (not substring of longer identifier awkwardly)
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(code)}(?![A-Za-z0-9_])", text or ""):
            found.append(code)
    return sorted(set(found))


# Alias used in requirements
HumanReadableValueResolver = resolve_display
