"""PlaceholderRegistry — classify unresolved markers in protocol/DOCX."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_.]+)\}\}")

ALLOWED_DRAFT = "ALLOWED_DRAFT_PLACEHOLDER"
REQUIRED_FIELD = "REQUIRED_FIELD"
UNRESOLVED_CRITICAL = "UNRESOLVED_CRITICAL"
LEGACY_TEMPLATE = "LEGACY_TEMPLATE_PLACEHOLDER"

# Critical for REVIEW/FINAL
CRITICAL_CODES: frozenset[str] = frozenset(
    {
        "STUDY.PROTOCOL_NUMBER",
        "STUDY.COUNTRY",
        "TEST_PRODUCT.TRADE_NAME",
        "TEST_PRODUCT.INN",
        "TEST_PRODUCT.NAME",
        "REFERENCE_PRODUCT.TRADE_NAME",
        "REFERENCE_PRODUCT.INN",
        "REFERENCE_PRODUCT.NAME",
        "SPONSOR.NAME",
        "SPONSOR_PERSONS.DETAILS",
        "SIGNATURE.SPONSOR",
        "SIGNATURE.INVESTIGATOR",
        "SUBJECTS.EVALUABLE_N",
        "SUBJECTS.RANDOMIZED_N",
        "DESIGN.TYPE",
        "SAMPLING.N_POINTS",
        "SAMPLING.POINT",
        "SAMPLING.TIME_H",
        "UNRESOLVED",
    }
)

# Allowed in DRAFT only (org/eligibility often incomplete mid-wizard)
DRAFT_ALLOWED_PREFIXES: tuple[str, ...] = (
    "SPONSOR",
    "SPONSOR_PERSONS",
    "MEDICAL_EXPERT",
    "INVESTIGATORS",
    "ANALYTICAL_LAB",
    "KEY_ORGS",
    "INVESTIGATOR_AGREEMENT",
    "SIGNATURE",
    "FINANCING",
    "INSURANCE",
    "PUBLICATION",
    "CLINICAL_CENTERS",
    "STATISTICS.DROPOUT_PCT",
    "SOURCES",
)

# Legacy tokens that must never ship even in DRAFT without build-report note
LEGACY_TOKENS: frozenset[str] = frozenset(
    {
        "XXX",
        "ХХ",
        "TBD",
        "N/A",
    }
)


@dataclass(frozen=True)
class ClassifiedPlaceholder:
    marker: str  # full {{CODE}}
    code: str
    classification: str
    blocks_review: bool
    blocks_final: bool


def classify_placeholder(marker: str) -> ClassifiedPlaceholder:
    raw = marker.strip()
    m = PLACEHOLDER_RE.fullmatch(raw) or PLACEHOLDER_RE.search(raw)
    code = m.group(1) if m else raw.replace("{{", "").replace("}}", "")
    if code in LEGACY_TOKENS or any(tok in code for tok in ("XXX",)):
        return ClassifiedPlaceholder(raw if raw.startswith("{{") else f"{{{{{code}}}}}", code, LEGACY_TEMPLATE, True, True)
    if code in CRITICAL_CODES or code.split(".")[0] in {
        "SPONSOR",
        "TEST_PRODUCT",
        "REFERENCE_PRODUCT",
        "DESIGN",
        "SAMPLING",
        "SUBJECTS",
    }:
        # Critical unresolved
        draft_ok = any(code.startswith(p) or code == p for p in DRAFT_ALLOWED_PREFIXES)
        return ClassifiedPlaceholder(
            f"{{{{{code}}}}}",
            code,
            UNRESOLVED_CRITICAL if not draft_ok else ALLOWED_DRAFT,
            blocks_review=True,
            blocks_final=True,
        )
    if any(code.startswith(p) or code == p for p in DRAFT_ALLOWED_PREFIXES):
        return ClassifiedPlaceholder(f"{{{{{code}}}}}", code, ALLOWED_DRAFT, True, True)
    return ClassifiedPlaceholder(f"{{{{{code}}}}}", code, REQUIRED_FIELD, True, True)


def classify_placeholders(markers: Iterable[str]) -> list[ClassifiedPlaceholder]:
    return [classify_placeholder(m) for m in sorted(set(markers))]


def extract_placeholders(obj: Any) -> list[str]:
    found: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, str):
            found.extend(f"{{{{{m.group(1)}}}}}" for m in PLACEHOLDER_RE.finditer(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)
    return sorted(set(found))


def review_blocking_placeholders(markers: Iterable[str]) -> list[ClassifiedPlaceholder]:
    return [c for c in classify_placeholders(markers) if c.blocks_review]


def final_blocking_placeholders(markers: Iterable[str]) -> list[ClassifiedPlaceholder]:
    return [c for c in classify_placeholders(markers) if c.blocks_final]
