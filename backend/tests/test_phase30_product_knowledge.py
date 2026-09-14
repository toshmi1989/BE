"""Phase 30 — product knowledge catalog + template dependency."""

from __future__ import annotations

from app.domain.product_knowledge import (
    PRODUCT_KNOWLEDGE_FIELDS,
    catalog_as_list,
    fields_for_final_pharmacology,
    prefer_higher_priority_source,
    source_rank,
)
from app.domain.research_evidence_classes import GAP_TO_TASK
from app.domain.workspace_gaps import GAP_CATALOG


def test_product_knowledge_categories_present():
    cats = {f.category for f in PRODUCT_KNOWLEDGE_FIELDS}
    for needed in {
        "PRODUCT_IDENTITY",
        "ACTIVE_SUBSTANCE",
        "PHARMACOLOGICAL_CLASS",
        "MECHANISM_OF_ACTION",
        "THERAPEUTIC_INFORMATION",
        "TMAX",
        "HALF_LIFE",
        "RELEVANT_SAFETY",
    }:
        assert needed in cats
    assert fields_for_final_pharmacology()
    assert catalog_as_list()


def test_template_dependency_gaps_registered():
    assert "MISSING_PRODUCT_PHARMACOLOGY" in GAP_CATALOG
    assert "MISSING_PRODUCT_CHEMISTRY" in GAP_CATALOG
    assert "MISSING_PRODUCT_PHARMACOLOGY" in GAP_TO_TASK
    assert GAP_TO_TASK["MISSING_PRODUCT_PHARMACOLOGY"]["priority"] == "CRITICAL"


def test_source_priority_configurable():
    assert source_rank("SMPC") < source_rank("SCIENTIFIC_LITERATURE")
    assert prefer_higher_priority_source("OTHER", "SMPC") is True
    assert prefer_higher_priority_source("SMPC", "OTHER") is False
