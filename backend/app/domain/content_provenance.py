"""Content block provenance — Phase 12A technical foundation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContentProvenance:
    """Attached to generated protocol content blocks."""

    origin: str = "SOURCE_DERIVED"
    status: str = "DRAFT"
    source_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source_ids"] = list(self.source_ids)
        d["rule_ids"] = list(self.rule_ids)
        return d


def merge_provenance_into_block(block: dict[str, Any], prov: ContentProvenance) -> dict[str, Any]:
    """Return a copy of block with provenance fields set (does not invent medical text)."""
    out = dict(block)
    out["origin"] = prov.origin
    out["status"] = prov.status
    existing_src = list(out.get("source_ids") or [])
    for sid in prov.source_ids:
        if sid not in existing_src:
            existing_src.append(sid)
    out["source_ids"] = existing_src
    existing_rules = list(out.get("rule_ids") or [])
    rid = out.get("rule_id")
    if rid and rid not in existing_rules:
        existing_rules.append(str(rid))
    for r in prov.rule_ids:
        if r not in existing_rules:
            existing_rules.append(r)
    out["rule_ids"] = existing_rules
    if prov.notes and not out.get("notes"):
        out["notes"] = prov.notes
    return out


def expert_required_provenance(*, notes: str | None = None) -> ContentProvenance:
    return ContentProvenance(
        origin="EXPERT_REQUIRED",
        status="NEEDS_REVIEW",
        notes=notes or "Awaiting medical writer / expert verification",
    )


def unresolved_provenance(placeholder: str) -> ContentProvenance:
    return ContentProvenance(
        origin="UNRESOLVED",
        status="UNRESOLVED",
        notes=f"Missing: {placeholder}",
    )
