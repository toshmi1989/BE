"""Phase 30.1 — Acceptance wiring smoke (not a substitute for docs runner)."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.domain.docx_profile import DOCX_GENERATOR_VERSION
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.product_knowledge import PRODUCT_KNOWLEDGE_FIELDS
from app.domain.template_contamination import has_verified_product_pharmacology


def test_phase30_1_version():
    assert Settings().app_version == "0.35.2"
    assert PROTOCOL_GENERATOR_VERSION == "0.35.2"
    assert DOCX_GENERATOR_VERSION == "0.35.2"
    assert get_settings().app_version == "0.35.2"


def test_final_pharmacology_requires_all_catalog_fields():
    required = [f.field_path for f in PRODUCT_KNOWLEDGE_FIELDS if f.required_for_final_pharmacology]
    assert set(required) == {
        "product.pharmacological_class",
        "product.mechanism",
        "product.pharmacology",
    }
    ctx = {
        "study_id": "UPDCB-02-BE-2026",
        "structured_facts": {"product.mechanism": "JAK1"},
        "fact_sources": {"product.mechanism": "VERIFIED_EVIDENCE"},
    }
    assert has_verified_product_pharmacology(ctx) is False
