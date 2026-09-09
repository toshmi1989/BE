"""Deterministic research task generation with dependencies — no LLM."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.domain.research_profile import SearchProfile


@dataclass
class ResearchTaskDraft:
    task_type: str
    priority: int
    query_profile: dict
    depends_on_tasks: list[str] = field(default_factory=list)
    status: str = "TODO"
    notes: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


TASK_DEPENDENCIES: dict[str, list[str]] = {
    "REFERENCE_PRODUCT": [],
    "REGISTRATION": ["REFERENCE_PRODUCT"],
    "PRODUCT_LABEL": ["REFERENCE_PRODUCT"],
    "PRODUCT_SPECIFIC_GUIDELINE": ["REFERENCE_PRODUCT"],
    "PK": ["PRODUCT_LABEL"],
    "ANALYTES": ["PK"],
    "BIOEQUIVALENCE_STUDIES": ["REFERENCE_PRODUCT", "PK"],
    "CV": ["BIOEQUIVALENCE_STUDIES"],
    "FOOD_CONDITION": ["PRODUCT_LABEL", "PRODUCT_SPECIFIC_GUIDELINE"],
    "SAFETY": ["PRODUCT_LABEL"],
}

TASK_PRIORITIES: dict[str, int] = {
    "REFERENCE_PRODUCT": 100,
    "REGISTRATION": 90,
    "PRODUCT_LABEL": 95,
    "PRODUCT_SPECIFIC_GUIDELINE": 85,
    "PK": 80,
    "ANALYTES": 75,
    "BIOEQUIVALENCE_STUDIES": 70,
    "CV": 65,
    "FOOD_CONDITION": 60,
    "SAFETY": 55,
}

ORDERED_TASK_TYPES = [
    "REFERENCE_PRODUCT",
    "REGISTRATION",
    "PRODUCT_LABEL",
    "PRODUCT_SPECIFIC_GUIDELINE",
    "PK",
    "ANALYTES",
    "BIOEQUIVALENCE_STUDIES",
    "CV",
    "FOOD_CONDITION",
    "SAFETY",
]


def generate_research_tasks(search: SearchProfile) -> list[ResearchTaskDraft]:
    has_identity = bool(search.inn or search.product_name)
    if not has_identity:
        return [
            ResearchTaskDraft(
                task_type="REFERENCE_PRODUCT",
                priority=100,
                query_profile={"terms": [], "notes": "INN/product missing — blocked"},
                depends_on_tasks=[],
                status="BLOCKED",
                notes="Provide INN or product name to unblock research tasks",
            )
        ]

    term_map = {
        "REFERENCE_PRODUCT": search.reference_search_terms,
        "REGISTRATION": search.reference_search_terms + search.guideline_search_terms,
        "PRODUCT_LABEL": search.reference_search_terms,
        "PRODUCT_SPECIFIC_GUIDELINE": search.guideline_search_terms,
        "PK": search.pk_search_terms,
        "ANALYTES": search.analyte_search_terms,
        "BIOEQUIVALENCE_STUDIES": search.bioequivalence_search_terms,
        "CV": search.cv_search_terms,
        "FOOD_CONDITION": search.food_search_terms,
        "SAFETY": search.pk_search_terms + ["safety", "adverse", "безопасность"],
    }
    tasks: list[ResearchTaskDraft] = []
    for ttype in ORDERED_TASK_TYPES:
        tasks.append(
            ResearchTaskDraft(
                task_type=ttype,
                priority=TASK_PRIORITIES[ttype],
                query_profile={
                    "terms": term_map[ttype],
                    "inn": search.inn,
                    "dosage": search.dosage,
                    "dosage_form": search.dosage_form,
                    "product_name": search.product_name,
                },
                depends_on_tasks=list(TASK_DEPENDENCIES.get(ttype, [])),
                status="TODO",
            )
        )
    return tasks
