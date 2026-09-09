"""RegulatorySourceSlot — Phase 13.2.

Maps expected official sources to presence / gaps. Does not fabricate files.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.regulatory_evidence_manifest import load_regulatory_manifest
from app.domain.regulatory_source_version import list_source_versions


SLOT_STATUSES: tuple[str, ...] = (
    "MISSING",
    "PRESENT",
    "INGESTED",
    "REVIEW_REQUIRED",
    "VERIFIED",
)


@dataclass
class RegulatorySourceSlot:
    slot_code: str
    expected_class: str
    title: str
    required: bool = True
    status: str = "MISSING"
    source_id: str | None = None
    source_version_id: str | None = None
    knowledge_gap_code: str | None = None
    technical_fixture: bool = False
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Declared official slots — files must be supplied by user; never invented
OFFICIAL_SLOTS: tuple[RegulatorySourceSlot, ...] = (
    RegulatorySourceSlot(
        "DECISION_85",
        "EEC_REGULATORY",
        "Decision No. 85 (EEC)",
        True,
        "MISSING",
        "SRC-DECISION85",
        knowledge_gap_code="REG.DECISION85.MISSING",
    ),
    RegulatorySourceSlot(
        "FDA_BE_CORE",
        "FDA_GUIDANCE",
        "FDA BE core guidance",
        False,
        "MISSING",
        "SRC-FDA-BE",
        knowledge_gap_code="REG.FDA.MISSING",
    ),
    RegulatorySourceSlot(
        "EMA_BE_CORE",
        "EMA_GUIDANCE",
        "EMA BE guideline",
        False,
        "MISSING",
        "SRC-EMA-BE",
        knowledge_gap_code="REG.EMA.MISSING",
    ),
    RegulatorySourceSlot(
        "REFERENCE_SMPC",
        "SMPC_OHLP",
        "Reference product SmPC/ОХЛП",
        True,
        "MISSING",
        "SRC-SMPC-REF",
        knowledge_gap_code="REG.SMPC.MISSING",
    ),
    RegulatorySourceSlot(
        "SAFETY_REFERENCE_PROTOCOL",
        "REGULATORY_REPORT",
        "Post-June-2026 BE safety reference protocol",
        True,
        "MISSING",
        None,
        knowledge_gap_code="REG.SAFETY.POST_2026_PROTOCOL.MISSING",
    ),
    RegulatorySourceSlot(
        "TECHNICAL_FIXTURE",
        "OTHER",
        "Technical import fixture (not regulatory)",
        False,
        "MISSING",
        "SRC-TECH-FIXTURE",
        technical_fixture=True,
        notes="TECHNICAL_FIXTURE_ONLY — must not be treated as verified regulation",
    ),
)


def refresh_slots(*, base=None, project_id: str | None = None) -> list[RegulatorySourceSlot]:
    """Update slot status from manifest + imported versions + on-disk Decision 85."""
    from app.domain.decision85_claims import decision85_doc_path

    manifest = load_regulatory_manifest(base)
    versions = list_source_versions(base, project_id=project_id)
    by_source = {}
    for v in versions:
        if v.is_current:
            by_source[v.source_id] = v

    d85_present = decision85_doc_path(base).is_file()

    out: list[RegulatorySourceSlot] = []
    for slot in OFFICIAL_SLOTS:
        s = RegulatorySourceSlot(**asdict(slot))
        if s.slot_code == "DECISION_85" and d85_present:
            s.status = "PRESENT"
        if s.source_id:
            for src in manifest.sources:
                if src.source_id == s.source_id and src.ingestion_status == "OK":
                    s.status = "PRESENT"
            if s.source_id in by_source:
                v = by_source[s.source_id]
                s.source_version_id = v.version_id
                if v.ingestion_status == "OK":
                    s.status = "INGESTED"
                if v.verification_status == "REVIEW_REQUIRED":
                    s.status = "REVIEW_REQUIRED"
                if v.verification_status == "VERIFIED" and getattr(v, "explicitly_verified", False):
                    s.status = "VERIFIED"
        if s.status == "MISSING" and s.required:
            s.knowledge_gap_code = s.knowledge_gap_code or f"REG.SLOT.{s.slot_code}.MISSING"
        out.append(s)
    return out


def gaps_for_missing_required_slots(slots: list[RegulatorySourceSlot] | None = None) -> list[dict[str, Any]]:
    slots = slots or refresh_slots()
    gaps: list[dict[str, Any]] = []
    for s in slots:
        if s.required and s.status == "MISSING":
            gaps.append(
                {
                    "code": s.knowledge_gap_code or f"REG.SLOT.{s.slot_code}.MISSING",
                    "domain": s.expected_class,
                    "question": f"Required regulatory source slot missing: {s.title}",
                    "slot_code": s.slot_code,
                    "importance": "HIGH",
                    "blocking": True,
                    "status": "OPEN",
                }
            )
    return gaps
