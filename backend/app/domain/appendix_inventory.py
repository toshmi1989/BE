"""Appendix inventory — Phase 12B.4.

Classifies existing appendix/static blocks. Does not invent appendix letters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.domain.static_blocks import STATIC_BLOCKS, STATIC_VERIFIED


@dataclass
class AppendixInventoryItem:
    section_code: str
    title: str
    type: str  # STATIC_VERIFIED|DYNAMIC_CANONICAL|CONDITIONAL|REFERENCE|FORM|PLACEHOLDER
    source: str
    required: bool
    conditional: bool
    render_target: str | None
    status: str
    block_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _item_type_for_static(verified_status: str, block_id: str, source: str) -> str:
    src_l = (source or "").lower()
    if "form" in src_l or block_id.startswith("APP."):
        return "FORM" if verified_status == STATIC_VERIFIED else verified_status
    if verified_status == STATIC_VERIFIED:
        return "STATIC_VERIFIED"
    return verified_status


def build_appendix_inventory(*, ctx: dict | None = None) -> list[AppendixInventoryItem]:
    """Build appendix inventory from static registry + known dynamic slots."""
    items: list[AppendixInventoryItem] = []
    seen_ids: set[str] = set()

    for b in STATIC_BLOCKS:
        if not (str(b.section_code).startswith("16") or str(b.block_id).startswith("APP.")):
            continue
        itype = _item_type_for_static(b.verified_status, b.block_id, b.source)
        items.append(
            AppendixInventoryItem(
                section_code=str(b.section_code),
                title=b.source,
                type=itype,
                source=b.source,
                required=True,
                conditional=False,
                render_target="preserve_static" if b.verified_status == STATIC_VERIFIED else None,
                status=b.verified_status,
                block_id=b.block_id,
            )
        )
        seen_ids.add(b.block_id)

    # Dynamic: signatures from StudyAdministration / persons
    if "SIGNATURES" not in seen_ids:
        items.append(
            AppendixInventoryItem(
                section_code="16",
                title="Signatures",
                type="DYNAMIC_CANONICAL",
                source="StudyAdministration/persons",
                required=True,
                conditional=False,
                render_target="SIGNATURES",
                status="DYNAMIC",
                block_id="SIGNATURES",
            )
        )

    # STUDY_METADATA if applicable (study identity present)
    ctx = ctx or {}
    study = ctx.get("study") or {}
    has_meta = any(
        study.get(k)
        for k in ("title", "protocol_number", "protocol_code", "version", "study_code")
    )
    if has_meta and "STUDY_METADATA" not in seen_ids:
        items.append(
            AppendixInventoryItem(
                section_code="16",
                title="Study metadata",
                type="DYNAMIC_CANONICAL",
                source="study",
                required=False,
                conditional=True,
                render_target="STUDY_METADATA",
                status="DYNAMIC",
                block_id="STUDY_METADATA",
            )
        )

    # Deterministic order: static forms first, then dynamic by block_id
    items.sort(key=lambda x: (0 if str(x.type) in {"STATIC_VERIFIED", "FORM"} else 1, str(x.block_id or ""), str(x.title)))
    return items


def appendix_inventory_to_dict(items: list[AppendixInventoryItem]) -> list[dict[str, Any]]:
    return [i.to_dict() for i in items]
