"""ReferenceRegistry — resolve cross-references without legacy Word field errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.table_registry import TableRegistry


@dataclass
class ReferenceEntry:
    reference_key: str
    reference_type: str  # section | table | appendix | figure
    target_id: str
    display_number: int | None
    display_text: str
    resolved: bool = True
    error: str | None = None


@dataclass
class ReferenceRegistry:
    entries: list[ReferenceEntry] = field(default_factory=list)

    def by_key(self) -> dict[str, ReferenceEntry]:
        return {e.reference_key: e for e in self.entries}

    def unresolved(self) -> list[ReferenceEntry]:
        return [e for e in self.entries if not e.resolved]

    def to_dict(self) -> dict[str, Any]:
        return {
            "references": [
                {
                    "reference_key": e.reference_key,
                    "reference_type": e.reference_type,
                    "target_id": e.target_id,
                    "display_number": e.display_number,
                    "display_text": e.display_text,
                    "resolved": e.resolved,
                    "error": e.error,
                }
                for e in self.entries
            ]
        }


def build_reference_registry(
    protocol_references: list[dict],
    *,
    table_registry: TableRegistry,
    section_codes: set[str] | None = None,
) -> ReferenceRegistry:
    section_codes = section_codes or set()
    entries: list[ReferenceEntry] = []
    for i, ref in enumerate(protocol_references):
        key = str(ref.get("id") or ref.get("reference_key") or f"ref-{i}")
        ttype = str(ref.get("target_type") or "section")
        tid = str(ref.get("target_id") or "")
        display_number: int | None = None
        display_text = str(ref.get("display_text") or "")
        resolved = True
        error = None

        if ttype == "table":
            num = table_registry.number_for(tid)
            if num is None:
                resolved = False
                error = f"table target not found: {tid}"
                display_text = display_text or f"{{{{TABLE.{tid}}}}}"
            else:
                display_number = num
                display_text = table_registry.display_text(tid) or display_text
        elif ttype == "section":
            if section_codes and tid and tid not in section_codes:
                resolved = False
                error = f"section target not found: {tid}"
            else:
                display_text = display_text or f"раздел {tid}"
        elif ttype in {"appendix", "figure"}:
            display_text = display_text or f"{ttype} {tid}"
        else:
            resolved = False
            error = f"unknown reference_type: {ttype}"

        entries.append(
            ReferenceEntry(
                reference_key=key,
                reference_type=ttype,
                target_id=tid,
                display_number=display_number,
                display_text=display_text,
                resolved=resolved,
                error=error,
            )
        )
    return ReferenceRegistry(entries=entries)


def detect_broken_reference_text(blob: str) -> list[str]:
    """Heuristic for leftover Word / unresolved reference errors in DOCX text."""
    hits: list[str] = []
    needles = (
        "Error! Reference source not found",
        "Error: Reference source not found",
        "Источник ссылки не найден",
        "Таблица {{",
        "см. Таблицу {{",
        "{{TABLE.",
    )
    for n in needles:
        if n.lower() in (blob or "").lower() or n in (blob or ""):
            hits.append(n)
    return hits
