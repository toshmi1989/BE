"""Versioned DOCX template profile — presentation mapping only."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


TEMPLATE_ID = "BE_Protocol_Template"
TEMPLATE_VERSION = "v2.0"
TEMPLATE_FILENAME = "BE_Protocol_Template_v2.0.docx"
TEMPLATE_CHECKSUM_SHA256 = "8e6be6aa6f0514dc4ba6a1016feb141946a2ded538a58d306bcf0fa68725d8a6"
DOCX_GENERATOR_VERSION = "0.30.0"
PROFILE_VERSION = "DOCX.PROFILE.v4"

# ProtocolDraft table_key → template table index (0-based)
TABLE_KEY_TO_INDEX: dict[str, int] = {
    "STUDY_METADATA": 0,  # T01
    "SYNOPSIS_N": 2,  # T03 synopsis (N rows merged conceptually)
    "SIGNATURES": 3,  # T04
    "TEST_PRODUCT": 4,  # T05
    "REFERENCE_PRODUCT": 5,  # T06
    "PK_PARAMETERS": 6,  # T07
    "SCHEDULE_OF_ASSESSMENTS": 7,  # T08 — fill_mode PRESERVE when STATIC
    # T09 LAB_PARAMETERS intentionally omitted — STATIC_VERIFIED, not overwritten
    "BLOOD_SAMPLING": 9,  # T10
    "MEAL_TIMING": 11,  # T12
    "CV_EVIDENCE": 16,  # T17
}

# Sections we actively overwrite from ProtocolDraft (heading section_code match)
# Phase 11B P0 — expand coverage; headings verified against template body.
ACTIVE_SECTION_CODES: tuple[str, ...] = (
    "1.1",
    "1.2",
    "1.3",
    "1.4",
    "1.5",
    "1.6",
    "1.7",
    "1.8",
    "1.9",
    "2.1.1",
    "2.1.2",
    "2.2",
    "2.3",
    "2.4",
    "2.5",
    "2.6",
    "2.7",
    "2.8",
    "2.9",
    "2.10",
    "2.11",
    "2.12",
    "3",
    "4.1",
    "4.2",
    "4.3",
    "4.4",
    "4.4.1",
    "4.4.2",
    "4.5",
    "4.6",
    "4.7",
    "4.7.1",
    "4.7.2",
    "4.7.3",
    "4.8",
    "4.8.1",
    "4.8.2",
    "4.8.3",
    "4.9",
    "5.1",
    "5.2",
    "5.3",
    "6.1",
    "6.1.1",
    "6.1.2",
    "6.1.3",
    "6.1.4",
    "6.1.5",
    "6.1.6",
    "6.1.7",
    "6.1.8",
    "6.1.9",
    "6.1.10",
    "6.2",
    "6.2.1",
    "6.2.2",
    "6.2.3",
    "6.3",
    "6.3.1",
    "7.1",
    "7.2",
    "7.3",
    "7.3.1",
    "7.3.2",
    "7.3.3",
    "7.3.4",
    "8.1",
    "8.2",
    "8.2.1",
    "8.2.2",
    "8.2.3",
    "8.3",
    "8.4",
    "8.5",
    "9.1",
    "9.2",
    "9.3",
    "9.4",
    "9.5",
    "9.6",
    "9.7",
    "9.7.1",
    "9.7.1.1",
    "9.7.1.2",
    "9.7.2",
    "9.7.3",
    "9.7.4",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
)

# Critical unresolved markers that block FINAL / REVIEW
CRITICAL_UNRESOLVED_PREFIXES: tuple[str, ...] = (
    "{{STUDY.PROTOCOL_NUMBER}}",
    "{{TEST_PRODUCT",
    "{{REFERENCE_PRODUCT",
    "{{SPONSOR",
    "{{SPONSOR_PERSONS",
    "{{MEDICAL_EXPERT",
    "{{INVESTIGATORS",
    "{{ANALYTICAL_LAB",
    "{{KEY_ORGS",
    "{{INVESTIGATOR_AGREEMENT",
    "{{INSURANCE",
    "{{FINANCING",
    "{{PUBLICATION",
    "{{CLINICAL_CENTERS",
    "{{SIGNATURES",
    "{{SIGNATURE",
    "{{SUBJECTS.EVALUABLE_N}}",
    "{{DESIGN.TYPE}}",
    "{{SAMPLING",
    "{{EVIDENCE.",
    "{{UNRESOLVED}}",
)


@dataclass(frozen=True)
class DocxTemplateProfile:
    template_id: str = TEMPLATE_ID
    template_version: str = TEMPLATE_VERSION
    file_checksum: str = TEMPLATE_CHECKSUM_SHA256
    profile_version: str = PROFILE_VERSION
    generator_version: str = DOCX_GENERATOR_VERSION
    styles: dict = field(
        default_factory=lambda: {
            "heading_1": "Heading 1",
            "heading_2": "Heading 2",
            "heading_3": "Heading 3",
            "normal": "Normal",
            "caption": "Caption",
        }
    )
    section_mappings: dict = field(default_factory=dict)
    table_mappings: dict = field(default_factory=lambda: dict(TABLE_KEY_TO_INDEX))
    bookmark_mappings: dict = field(
        default_factory=lambda: {
            "BLOOD_SAMPLING": "СХЕМАотбораКРОВИ",
            "BLOOD_VOLUME": "ОБЬЕМкрови",
            "BLOOD_VOLUME_SEROL": "ОБЪЕМкровиСЕРОЛ",
            "BLOOD_VOLUME_CATHETER": "ОБЪЕМкровиКАТЕТЕР",
            "BLOOD_VOLUME_TOTAL": "ОБЩИЙобъемКРОВИ",
        }
    )
    numbering_rules: dict = field(
        default_factory=lambda: {"table_caption_prefix": "Таблица", "dynamic": True}
    )
    header_footer_rules: dict = field(
        default_factory=lambda: {
            "variables": ["protocol_number", "test_product", "version", "date"],
            "strategy": "token_or_preserve",
        }
    )
    page_rules: dict = field(
        default_factory=lambda: {
            "preserve_sections": True,
            "preserve_page_fields": True,
            "update_toc_fields": "leave_word_fields",
        }
    )

    def template_path(self, repo_root: Path | None = None) -> Path:
        root = repo_root or Path(__file__).resolve().parents[3]
        return root / "templates" / "protocol" / TEMPLATE_FILENAME

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "template_version": self.template_version,
            "file_checksum": self.file_checksum,
            "profile_version": self.profile_version,
            "generator_version": self.generator_version,
            "styles": self.styles,
            "table_mappings": self.table_mappings,
            "bookmark_mappings": self.bookmark_mappings,
            "numbering_rules": self.numbering_rules,
            "header_footer_rules": self.header_footer_rules,
            "page_rules": self.page_rules,
            "active_sections": list(ACTIVE_SECTION_CODES),
        }


def get_template_profile() -> DocxTemplateProfile:
    return DocxTemplateProfile(
        section_mappings={code: {"strategy": "replace_section_body"} for code in ACTIVE_SECTION_CODES}
    )
