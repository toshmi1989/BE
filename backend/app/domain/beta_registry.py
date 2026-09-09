"""Phase 18 — Beta fixture registry (real + clearly-labelled synthetic)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
BETA_ROOT = REPO_ROOT / "fixtures" / "beta"
REGISTRY_PATH = BETA_ROOT / "registry.json"

ERROR_TYPES: tuple[str, ...] = (
    "EXTRACTION_ERROR",
    "SOURCE_ATTRIBUTION_ERROR",
    "NORMALIZATION_ERROR",
    "CONFLICT_MISSED",
    "FALSE_CONFLICT",
    "RESEARCH_GAP_MISSED",
    "BAD_RECOMMENDATION",
    "DECISION_UX_ERROR",
    "SAMPLE_SIZE_ERROR",
    "STATISTICS_ERROR",
    "PROTOCOL_RENDER_ERROR",
    "DOCX_ERROR",
    "PERMISSION_ERROR",
    "PERSISTENCE_ERROR",
)


def load_registry() -> dict[str, Any]:
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return raw


def list_cases(*, origin: str | None = None) -> list[dict[str, Any]]:
    cases = list(load_registry().get("cases") or [])
    if origin:
        cases = [c for c in cases if str(c.get("origin") or "").upper().startswith(origin.upper())]
    return cases


def get_case(case_id: str) -> dict[str, Any]:
    for c in list_cases():
        if c.get("case_id") == case_id:
            return c
    raise KeyError(case_id)


def case_summary() -> dict[str, Any]:
    cases = list_cases()
    by_origin: dict[str, int] = {}
    by_cat: dict[str, int] = {}
    for c in cases:
        o = str(c.get("origin") or "UNKNOWN")
        by_origin[o] = by_origin.get(o, 0) + 1
        cat = str(c.get("category") or "?")
        by_cat[cat] = by_cat.get(cat, 0) + 1
    return {
        "total": len(cases),
        "by_origin": by_origin,
        "by_category": by_cat,
        "real_available": by_origin.get("REAL", 0) + by_origin.get("REAL_PARTIAL", 0),
        "synthetic": by_origin.get("SYNTHETIC", 0),
        "limitation": (
            "Only UPDCB (CASE-I) and design-only (CASE-J) have real/partial writer packages; "
            "remaining categories are SYNTHETIC placeholders until real packages are provided."
        ),
    }
