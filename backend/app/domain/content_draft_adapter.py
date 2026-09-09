"""Thin adapter: ContentResolver → ProtocolDraft block hints (Phase 12A.2).

Does NOT rewrite DOCX renderer or expand section coverage.
"""

from __future__ import annotations

from typing import Any

from app.domain.content_resolver import ResolvedContent, resolve_section
from app.domain.content_renderer import render_resolved


def resolved_to_draft_blocks(resolved: ResolvedContent) -> list[dict[str, Any]]:
    """Map ResolvedContent to assembly-compatible content_blocks (structural only)."""
    rendered = render_resolved(resolved)
    if resolved.source_type == "MISSING" or resolved.content is None:
        return [
            {
                "type": "TEXT",
                "text": f"{{{{CONTENT.SECTION_{resolved.section_code.replace('.', '_')}}}}}",
                "status": "UNRESOLVED",
                "origin": "PLACEHOLDER",
                "source_type": resolved.source_type,
                "knowledge_gaps": resolved.knowledge_gaps,
            }
        ]
    if not resolved.display_as_final:
        return [
            {
                "type": "TEXT",
                "text": f"[PROPOSED — not final] {rendered.get('text') or rendered.get('payload')}",
                "status": "PROPOSED",
                "origin": resolved.source_type,
                "display_as_final": False,
            }
        ]
    return [
        {
            "type": "TEXT",
            "text": str(rendered.get("text") if rendered.get("text") is not None else rendered.get("payload")),
            "status": "RESOLVED",
            "origin": resolved.source_type,
            "canonical_source": resolved.canonical_source,
            "display_as_final": True,
        }
    ]


def preview_section_blocks(
    *,
    section_code: str,
    canonical_snapshot: dict[str, Any],
    expert_decisions: list[dict] | None = None,
) -> list[dict[str, Any]]:
    resolved = resolve_section(
        section_code=section_code,
        canonical_snapshot=canonical_snapshot,
        expert_decisions=expert_decisions,
    )
    return resolved_to_draft_blocks(resolved)
