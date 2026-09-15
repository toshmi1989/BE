"""Phase 30.3 — Template block classification registry.

STATIC_UNIVERSAL | DYNAMIC_REQUIRED | DYNAMIC_OPTIONAL | PRODUCT_SPECIFIC |
PROCEDURE_SPECIFIC | TABLE_DYNAMIC | FORM_DYNAMIC
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TemplateBlock:
    block_id: str
    section: str
    classification: str
    template_location: str
    source: str
    renderer: str
    required_for_final: bool
    validation: str
    notes: str = ""


TEMPLATE_BLOCKS: tuple[TemplateBlock, ...] = (
    TemplateBlock("cover.metadata", "Cover", "FORM_DYNAMIC", "tables[0]", "study+product+sponsor", "cover_mapping", True, "typed_cover"),
    TemplateBlock("synopsis.admin", "Synopsis", "TABLE_DYNAMIC", "tables[2]", "study+subjects+org", "synopsis_fill", True, "label_fill"),
    TemplateBlock("synopsis.subjects", "Synopsis", "TABLE_DYNAMIC", "tables[2]", "CanonicalSubjectCounts", "synopsis_fill", True, "typed_subjects"),
    TemplateBlock("general.info", "1.x", "DYNAMIC_OPTIONAL", "sections 1.*", "study", "section_generators", False, "source_or_preserve"),
    TemplateBlock("background", "2.x", "DYNAMIC_OPTIONAL", "sections 2.*", "evidence", "section_generators", False, "verified_or_clear"),
    TemplateBlock("test.product", "2.1.1", "PRODUCT_SPECIFIC", "tables[4]", "product.*", "product_mapping", True, "typed_product"),
    TemplateBlock("reference.product", "2.1.2", "PRODUCT_SPECIFIC", "tables[5]", "reference_product.*", "product_mapping", True, "typed_product"),
    TemplateBlock("test.composition", "2.1.1", "PRODUCT_SPECIFIC", "tables[4] composition rows", "product.composition", "product_mapping+contamination", True, "no_stale_composition"),
    TemplateBlock("reference.composition", "2.1.2", "PRODUCT_SPECIFIC", "tables[5] composition rows", "reference_product.composition", "product_mapping+contamination", True, "no_stale_composition"),
    TemplateBlock("dosage", "Cover/Products", "PRODUCT_SPECIFIC", "cover+T05/T06", "product.dosage", "typed Dose", True, "Dose"),
    TemplateBlock("dosage_form", "Cover/Products", "PRODUCT_SPECIFIC", "cover+T05/T06", "product.dosage_form", "typed string", True, "string_not_integer"),
    TemplateBlock("manufacturer", "Products", "PRODUCT_SPECIFIC", "T05/T06", "product.manufacturer", "product_mapping", True, "required_or_block"),
    TemplateBlock("route", "Products", "PRODUCT_SPECIFIC", "T05/T06", "product.route", "product_mapping", False, "optional"),
    TemplateBlock("storage", "Products", "PRODUCT_SPECIFIC", "T05/T06", "product.storage_conditions", "product_mapping", False, "optional"),
    TemplateBlock("pharmacology", "2.8", "PRODUCT_SPECIFIC", "section 2.8", "verified pharmacology", "contamination CLEAR_OR_BLOCK", True, "verified_or_clear"),
    TemplateBlock("chemistry", "2.1", "PRODUCT_SPECIFIC", "section 2.1", "verified chemistry", "contamination CLEAR_OR_BLOCK", True, "verified_or_clear"),
    TemplateBlock("dose.rationale", "2.x", "DYNAMIC_OPTIONAL", "section dose rationale", "study evidence", "generators", False, "source_or_block"),
    TemplateBlock("population", "Synopsis/6", "DYNAMIC_REQUIRED", "synopsis+eligibility", "eligibility", "generators", True, "required_lists"),
    TemplateBlock("observation", "4.x", "DYNAMIC_REQUIRED", "{{OBSERVATION.DURATION}}", "observation plan", "generators", True, "duration"),
    TemplateBlock("washout", "Synopsis/4", "PROCEDURE_SPECIFIC", "washout paragraphs", "washout.selected_value", "generators+consistency", True, "canonical_invariant"),
    TemplateBlock("objectives", "4.x", "DYNAMIC_OPTIONAL", "objectives", "study.objectives", "generators", False, "source_or_rule"),
    TemplateBlock("design", "4.x", "DYNAMIC_REQUIRED", "design sections", "design.type", "generators", True, "required"),
    TemplateBlock("pk.table", "4.1", "TABLE_DYNAMIC", "tables[6] PK_PARAMETERS", "pk_parameters/StatisticsPlan", "rebuild", True, "no_internal_ids"),
    TemplateBlock("sampling.table", "4.4.2", "TABLE_DYNAMIC", "tables[9] BLOOD_SAMPLING", "SamplingPlan", "rebuild", True, "SamplingPlan"),
    TemplateBlock("treatment", "4.x", "DYNAMIC_OPTIONAL", "treatment", "design+food", "generators", False, "source"),
    TemplateBlock("periods", "4.x", "DYNAMIC_OPTIONAL", "periods", "design.periods", "generators", False, "source"),
    TemplateBlock("eligibility.inclusion", "6.1", "DYNAMIC_REQUIRED", "{{ELIGIBILITY.INCLUSION}}", "eligibility.inclusion", "generators", True, "required_or_block"),
    TemplateBlock("eligibility.non_inclusion", "6.2", "DYNAMIC_REQUIRED", "{{ELIGIBILITY.NON_INCLUSION}}", "eligibility.non_inclusion", "generators", True, "required_or_block"),
    TemplateBlock("eligibility.exclusion", "6.3", "DYNAMIC_REQUIRED", "{{ELIGIBILITY.EXCLUSION}}", "eligibility.exclusion", "generators", True, "required_or_block"),
    TemplateBlock("concomitant", "6.x", "DYNAMIC_OPTIONAL", "concomitant", "study rules", "generators", False, "optional"),
    TemplateBlock("bioanalysis.method", "7.x", "DYNAMIC_REQUIRED", "{{BIOANALYSIS.METHOD}}", "bioanalysis_plan", "generators", True, "required_or_block"),
    TemplateBlock("bioanalysis.validation", "7.x", "DYNAMIC_REQUIRED", "{{BIOANALYSIS.VALIDATION}}", "bioanalysis_plan", "generators", True, "required_or_block"),
    TemplateBlock("bioanalysis.sample", "7.x", "DYNAMIC_REQUIRED", "{{BIOANALYSIS.SAMPLE_ANALYSIS}}", "bioanalysis_plan", "generators", True, "required_or_block"),
    TemplateBlock("bioanalysis.run", "7.x", "DYNAMIC_REQUIRED", "{{BIOANALYSIS.RUN_ACCEPTANCE}}", "bioanalysis_plan", "generators", True, "required_or_block"),
    TemplateBlock("safety.plan", "8.x", "DYNAMIC_REQUIRED", "{{SAFETY.PLAN}}", "safety_plan|STATIC_UNIVERSAL", "generators", True, "universal_or_source"),
    TemplateBlock("safety.methods", "8.x", "DYNAMIC_OPTIONAL", "{{SAFETY.METHODS}}", "safety_plan", "generators", False, "optional"),
    TemplateBlock("safety.labs", "8.x", "DYNAMIC_OPTIONAL", "{{SAFETY.LABS}}", "safety_plan", "generators", False, "optional"),
    TemplateBlock("safety.ae", "8.x", "DYNAMIC_OPTIONAL", "{{SAFETY.AE}}", "safety_plan", "generators", False, "optional"),
    TemplateBlock("statistics", "9.7", "DYNAMIC_REQUIRED", "statistics sections", "APPROVED StatisticsPlan", "generators", True, "PRIMARY_BE_approved"),
    TemplateBlock("quality", "9.x", "STATIC_UNIVERSAL", "quality", "template universal", "preserve", False, "static"),
    TemplateBlock("ethics", "10.x", "DYNAMIC_OPTIONAL", "{{ETHICS.COMMITTEE}}", "ethics", "generators", False, "optional"),
    TemplateBlock("data.management", "9.x", "DYNAMIC_OPTIONAL", "data mgmt", "study", "generators", False, "optional"),
    TemplateBlock("insurance", "11.x", "DYNAMIC_OPTIONAL", "{{INSURANCE.DETAILS}}", "insurance", "generators", False, "optional"),
    TemplateBlock("publications", "12.x", "STATIC_UNIVERSAL", "publications", "template universal", "preserve", False, "static"),
    TemplateBlock("appendices", "Appendix", "DYNAMIC_OPTIONAL", "appendices", "appendix_inventory", "generators", False, "optional"),
    TemplateBlock("references", "References", "DYNAMIC_OPTIONAL", "references", "sources", "generators", False, "optional"),
    TemplateBlock("toc", "TOC", "FORM_DYNAMIC", "TOC field", "renderer", "docx_toc", True, "toc_refreshed"),
    TemplateBlock("header.version_date", "Header", "FORM_DYNAMIC", "header/footer", "study.version+version_date", "hf_vars", True, "no_template_date"),
)


PRODUCT_SPECIFIC_FIELDS: frozenset[str] = frozenset(
    {
        "TEST_PRODUCT.COMPOSITION",
        "REFERENCE_PRODUCT.COMPOSITION",
        "DOSAGE",
        "MANUFACTURER",
        "DOSAGE_FORM",
        "ROUTE",
        "STRENGTH",
        "STORAGE",
        "PHARMACOLOGY",
        "CHEMISTRY",
    }
)


def registry_as_list() -> list[dict[str, Any]]:
    return [
        {
            "block_id": b.block_id,
            "section": b.section,
            "classification": b.classification,
            "template_location": b.template_location,
            "source": b.source,
            "renderer": b.renderer,
            "required_for_final": b.required_for_final,
            "validation": b.validation,
            "notes": b.notes,
        }
        for b in TEMPLATE_BLOCKS
    ]


def required_final_blocks() -> list[TemplateBlock]:
    return [b for b in TEMPLATE_BLOCKS if b.required_for_final]
