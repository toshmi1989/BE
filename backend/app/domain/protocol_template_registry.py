"""Phase 29 — Template field registry for Workspace → DOCX.

Maps template dynamic areas to Workspace canonical / approved sources.
Does not invent medical rules. Golden and Legacy Project are never content sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TemplateField:
    template_id: str
    element_type: str  # HEADER | TABLE | SECTION | SYNOPSIS
    location: str
    source: str
    required: bool
    notes: str = ""


# Product-specific sample strings embedded in BE_Protocol_Template_v2.0
# Must be overwritten from study product or generation is blocked.
STALE_TEMPLATE_PRODUCT_TOKENS: tuple[str, ...] = (
    "Бозутиниб",
    "бозутиниб",
    "Бозутиниба",
    "бозутиниба",
    "Бозутинибу",
    "бозутинибу",
    "Бозутинибом",
    "бозутинибом",
    "Бозулиф",
    "бозулиф",
    "Бозулифа",
    "бозулифа",
    "Bosutinib",
    "bosutinib",
    "BOSUTINIB",
    "Bosulif",
    "bosulif",
    "BOSULIF",
)

# Tokens that mean the study itself is the Bosutinib template sample (allowed to keep)
BOSUTINIB_IDENTITY_MARKERS: tuple[str, ...] = (
    "бозутиниб",
    "bosutinib",
    "бозулиф",
    "bosulif",
)

TEMPLATE_FIELDS: tuple[TemplateField, ...] = (
    TemplateField(
        "header.test_product",
        "HEADER",
        "section.header",
        "study_ctx.product.trade_name|inn",
        True,
        "Template ships with Бозутиниб — must be study product",
    ),
    TemplateField(
        "header.protocol_code",
        "HEADER",
        "section.header",
        "study_ctx.study.protocol_number",
        True,
    ),
    TemplateField(
        "header.version",
        "HEADER",
        "section.header",
        "study_ctx.study.version|protocol_version",
        False,
    ),
    TemplateField(
        "T01.study_metadata",
        "TABLE",
        "tables[0]",
        "study + product + design + sponsor",
        True,
    ),
    TemplateField(
        "T03.synopsis",
        "TABLE",
        "tables[2] SYNOPSIS_N",
        "consistency_snapshot + subjects N",
        True,
    ),
    TemplateField(
        "T05.test_product",
        "TABLE",
        "tables[4] TEST_PRODUCT",
        "study_ctx.product (approved/canonical)",
        True,
    ),
    TemplateField(
        "T06.reference_product",
        "TABLE",
        "tables[5] REFERENCE_PRODUCT",
        "study_ctx.reference_product (approved/canonical; dose conflict blocks)",
        True,
    ),
    TemplateField(
        "T07.pk_parameters",
        "TABLE",
        "tables[6] PK_PARAMETERS",
        "approved StatisticsPlan / pk_parameters",
        False,
    ),
    TemplateField(
        "T08.schedule",
        "TABLE",
        "tables[7] SCHEDULE_OF_ASSESSMENTS",
        "procedure schedule when present; else PRESERVE static",
        False,
    ),
    TemplateField(
        "T10.blood_sampling",
        "TABLE",
        "tables[9] BLOOD_SAMPLING",
        "canonical sampling plan + verified Tmax/t½ deps",
        False,
    ),
    TemplateField(
        "T12.meal_timing",
        "TABLE",
        "tables[11] MEAL_TIMING",
        "approved food decision / meal facts",
        False,
    ),
    TemplateField(
        "T17.cv_sample_size",
        "TABLE",
        "tables[16] CV_EVIDENCE",
        "ACCEPTED sample size calculation",
        False,
    ),
    TemplateField(
        "sec.design",
        "SECTION",
        "4.2 / ACTIVE_SECTION_CODES",
        "approved design decision + display registry",
        True,
    ),
    TemplateField(
        "sec.sampling",
        "SECTION",
        "4.4.2",
        "canonical sampling",
        False,
    ),
    TemplateField(
        "sec.statistics",
        "SECTION",
        "9.7.*",
        "APPROVED StatisticsPlan",
        False,
    ),
)


def study_is_bosutinib_sample(product: dict[str, Any] | None) -> bool:
    blob = " ".join(
        str(product.get(k) or "")
        for k in ("trade_name", "inn", "name", "dosage_form")
        if product
    ).lower()
    return any(m in blob for m in BOSUTINIB_IDENTITY_MARKERS)


def registry_as_list() -> list[dict[str, Any]]:
    return [
        {
            "template_id": f.template_id,
            "element_type": f.element_type,
            "location": f.location,
            "source": f.source,
            "required": f.required,
            "notes": f.notes,
        }
        for f in TEMPLATE_FIELDS
    ]
