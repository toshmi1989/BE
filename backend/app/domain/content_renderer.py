"""ContentRenderer interfaces — Phase 12A.2 (no full NL generator)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.content_resolver import ResolvedContent
from app.domain.display_value_registry import resolve_display


class ContentRenderer(ABC):
    @abstractmethod
    def render(self, resolved: ResolvedContent) -> dict[str, Any]:
        raise NotImplementedError


class CanonicalValueRenderer(ContentRenderer):
    def render(self, resolved: ResolvedContent) -> dict[str, Any]:
        val = resolved.content
        if isinstance(val, str) and val.isupper() and "_" in val:
            val = resolve_display(val, context="general", fallback=val)
        return {
            "type": "CANONICAL_VALUE",
            "text": None if val is None else str(val),
            "source_type": resolved.source_type,
            "canonical_source": resolved.canonical_source,
            "final": resolved.display_as_final,
        }


class ProcedureRenderer(ContentRenderer):
    def render(self, resolved: ResolvedContent) -> dict[str, Any]:
        return {
            "type": "PROCEDURE",
            "payload": resolved.content,
            "source_type": resolved.source_type,
            "final": False if not resolved.display_as_final else True,
        }


class ConditionRenderer(ContentRenderer):
    def render(self, resolved: ResolvedContent) -> dict[str, Any]:
        return {"type": "CONDITION", "payload": resolved.content, "source_type": resolved.source_type}


class TableRenderer(ContentRenderer):
    def render(self, resolved: ResolvedContent) -> dict[str, Any]:
        return {"type": "TABLE", "payload": resolved.content, "source_type": resolved.source_type}


class ReferenceRenderer(ContentRenderer):
    def render(self, resolved: ResolvedContent) -> dict[str, Any]:
        return {"type": "REFERENCE", "payload": resolved.content, "source_type": resolved.source_type}


def render_resolved(resolved: ResolvedContent) -> dict[str, Any]:
    bt = (resolved.block or {}).get("block_type") or "CANONICAL_VALUE"
    mapping: dict[str, ContentRenderer] = {
        "CANONICAL_VALUE": CanonicalValueRenderer(),
        "PROCEDURE": ProcedureRenderer(),
        "CONDITION": ConditionRenderer(),
        "CONDITIONAL": ConditionRenderer(),
        "TABLE": TableRenderer(),
        "REFERENCE": ReferenceRenderer(),
    }
    renderer = mapping.get(bt, CanonicalValueRenderer())
    out = renderer.render(resolved)
    out["section_code"] = resolved.section_code
    out["status"] = resolved.status
    out["knowledge_gaps"] = resolved.knowledge_gaps
    return out
