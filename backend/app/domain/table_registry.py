"""TableRegistry — dynamic table numbers and reference display text."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TableRegistryEntry:
    table_key: str
    section_code: str
    title: str
    order: int
    actual_number: int
    rendering_status: str  # GENERATED | SKIPPED | STATIC | CONDITIONAL_OMITTED


@dataclass
class TableRegistry:
    entries: list[TableRegistryEntry] = field(default_factory=list)

    def by_key(self) -> dict[str, TableRegistryEntry]:
        return {e.table_key: e for e in self.entries}

    def number_for(self, table_key: str) -> int | None:
        e = self.by_key().get(table_key)
        return e.actual_number if e else None

    def display_text(self, table_key: str, *, language: str = "ru") -> str | None:
        num = self.number_for(table_key)
        if num is None:
            return None
        if language == "ru":
            return f"Таблица {num}"
        return f"Table {num}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tables": [
                {
                    "table_key": e.table_key,
                    "section_code": e.section_code,
                    "title": e.title,
                    "order": e.order,
                    "actual_number": e.actual_number,
                    "rendering_status": e.rendering_status,
                }
                for e in self.entries
            ]
        }


def build_table_registry(protocol_tables: list[dict]) -> TableRegistry:
    """Assign actual_number from ordered ProtocolDraft tables (never hardcode in text)."""
    ordered = sorted(protocol_tables, key=lambda t: int(t.get("order") or 0))
    entries: list[TableRegistryEntry] = []
    num = 0
    for t in ordered:
        status = str(t.get("status") or "GENERATED")
        if status in {"SKIPPED", "CONDITIONAL_OMITTED"}:
            entries.append(
                TableRegistryEntry(
                    table_key=str(t["table_key"]),
                    section_code=str(t.get("section_code") or ""),
                    title=str(t.get("title") or ""),
                    order=int(t.get("order") or 0),
                    actual_number=0,
                    rendering_status=status,
                )
            )
            continue
        num += 1
        entries.append(
            TableRegistryEntry(
                table_key=str(t["table_key"]),
                section_code=str(t.get("section_code") or ""),
                title=str(t.get("title") or ""),
                order=int(t.get("order") or 0),
                actual_number=num,
                rendering_status=status,
            )
        )
    return TableRegistry(entries=entries)


def apply_table_numbers_to_tables(protocol_tables: list[dict], registry: TableRegistry) -> list[dict]:
    """Return copies with display_number from registry."""
    by_key = registry.by_key()
    out: list[dict] = []
    for t in protocol_tables:
        copy = dict(t)
        entry = by_key.get(t.get("table_key"))
        if entry and entry.actual_number:
            copy["display_number"] = entry.actual_number
        out.append(copy)
    return out
