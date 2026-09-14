"""Phase 30 — Product-specific knowledge field catalog (no second AI architecture).

Requirement for each field comes from template registry / study context, not from
assuming every field is mandatory for every protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Configurable source priority (higher index = lower priority). Prefer SmPC first.
SOURCE_PRIORITY: tuple[str, ...] = (
    "SMPC",
    "OHLP",
    "REGULATORY_OFFICIAL",
    "VERIFIED_REGULATORY",
    "SCIENTIFIC_LITERATURE",
    "RESEARCH_PROVIDER",
    "OTHER",
)


@dataclass(frozen=True)
class ProductKnowledgeField:
    category: str
    field_path: str
    title_ru: str
    gap_code: str | None
    template_blocks: tuple[str, ...]
    required_for_final_pharmacology: bool = False
    planning_fact: bool = False  # expected Tmax / t½ — not observed post-study


PRODUCT_KNOWLEDGE_FIELDS: tuple[ProductKnowledgeField, ...] = (
    ProductKnowledgeField(
        "PRODUCT_IDENTITY",
        "product.trade_name",
        "Торговое наименование",
        "MISSING_PRODUCT_IDENTITY",
        ("pharm.2.1.mechanism_cml", "product.names"),
    ),
    ProductKnowledgeField(
        "ACTIVE_SUBSTANCE",
        "product.inn",
        "МНН / действующее вещество",
        "MISSING_PRODUCT_IDENTITY",
        ("product.names",),
    ),
    ProductKnowledgeField(
        "PHARMACOLOGICAL_CLASS",
        "product.pharmacological_class",
        "Фармакологическая группа",
        "MISSING_PRODUCT_PHARMACOLOGY",
        ("pharm.2.1.mechanism_cml", "pharm.2.8.properties"),
        required_for_final_pharmacology=True,
    ),
    ProductKnowledgeField(
        "MECHANISM_OF_ACTION",
        "product.mechanism",
        "Механизм действия",
        "MISSING_PRODUCT_PHARMACOLOGY",
        ("pharm.2.1.mechanism_cml", "pharm.2.8.properties"),
        required_for_final_pharmacology=True,
    ),
    ProductKnowledgeField(
        "THERAPEUTIC_INFORMATION",
        "product.pharmacology",
        "Терапевтическая / фармакологическая информация",
        "MISSING_PRODUCT_PHARMACOLOGY",
        ("pharm.2.1.mechanism_cml", "pharm.2.8.properties"),
        required_for_final_pharmacology=True,
    ),
    ProductKnowledgeField(
        "CHEMICAL_INFORMATION",
        "product.chemical_formula",
        "Химическая формула",
        "MISSING_PRODUCT_CHEMISTRY",
        ("pharm.2.1.chemistry",),
    ),
    ProductKnowledgeField(
        "CHEMICAL_INFORMATION",
        "product.molecular_weight",
        "Молекулярная масса",
        "MISSING_PRODUCT_CHEMISTRY",
        ("pharm.2.1.chemistry",),
    ),
    ProductKnowledgeField(
        "TMAX",
        "pk.expected_tmax",
        "Ожидаемый Tmax (планирование)",
        "MISSING_TMAX_FOR_SAMPLING",
        (),
        planning_fact=True,
    ),
    ProductKnowledgeField(
        "HALF_LIFE",
        "pk.expected_t_half",
        "Ожидаемый t½ (планирование)",
        "MISSING_HALF_LIFE_FOR_WASHOUT",
        (),
        planning_fact=True,
    ),
    ProductKnowledgeField(
        "FOOD_EFFECT",
        "food.effect_summary",
        "Влияние пищи",
        "MISSING_MEAL_COMPOSITION",
        (),
    ),
    ProductKnowledgeField(
        "CONTRAINDICATIONS",
        "product.contraindications",
        "Противопоказания",
        "MISSING_PRODUCT_SAFETY",
        (),
    ),
    ProductKnowledgeField(
        "INTERACTIONS",
        "product.interactions",
        "Лекарственные взаимодействия",
        "MISSING_PRODUCT_SAFETY",
        (),
    ),
    ProductKnowledgeField(
        "RELEVANT_SAFETY",
        "product.safety_summary",
        "Ключевые сведения по безопасности",
        "MISSING_PRODUCT_SAFETY",
        (),
    ),
)


# Map AI / deterministic field_name → canonical field_path
FIELD_NAME_TO_PATH: dict[str, str] = {
    "tmax": "pk.expected_tmax",
    "expected_tmax": "pk.expected_tmax",
    "half_life": "pk.expected_t_half",
    "t_half": "pk.expected_t_half",
    "expected_t_half": "pk.expected_t_half",
    "mechanism": "product.mechanism",
    "mechanism_of_action": "product.mechanism",
    "pharmacology": "product.pharmacology",
    "pharmacological_class": "product.pharmacological_class",
    "chemical_formula": "product.chemical_formula",
    "molecular_weight": "product.molecular_weight",
    "inn": "product.inn",
    "active_substance": "product.inn",
    "trade_name": "product.trade_name",
    "contraindications": "product.contraindications",
    "interactions": "product.interactions",
    "safety": "product.safety_summary",
    "food_effect": "food.effect_summary",
}


def fields_for_final_pharmacology() -> list[ProductKnowledgeField]:
    return [f for f in PRODUCT_KNOWLEDGE_FIELDS if f.required_for_final_pharmacology]


def source_rank(kind: str | None) -> int:
    k = str(kind or "OTHER").upper()
    try:
        return SOURCE_PRIORITY.index(k)
    except ValueError:
        return len(SOURCE_PRIORITY) - 1


def prefer_higher_priority_source(
    existing_kind: str | None,
    candidate_kind: str | None,
) -> bool:
    """True if candidate should be preferred over existing (lower rank = better)."""
    return source_rank(candidate_kind) < source_rank(existing_kind)


def catalog_as_list() -> list[dict[str, Any]]:
    return [
        {
            "category": f.category,
            "field_path": f.field_path,
            "title_ru": f.title_ru,
            "gap_code": f.gap_code,
            "template_blocks": list(f.template_blocks),
            "required_for_final_pharmacology": f.required_for_final_pharmacology,
            "planning_fact": f.planning_fact,
        }
        for f in PRODUCT_KNOWLEDGE_FIELDS
    ]
