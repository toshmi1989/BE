"""Phase 30.2 — section-level DOCX ↔ claim reverse traceability.

Smallest safe version: map protocol sections / canonical fields to evidence
claims and decisions. Does NOT invent paragraph-level provenance.
"""

from __future__ import annotations

from typing import Any

from app.domain.decision_store import list_decisions
from app.domain.display_value_registry import scrub_technical_tokens_in_text
from app.domain.research_evidence_store import get_source, list_claims


# Section-level mapping for product-specific / dynamic protocol content.
SECTION_FIELD_MAP: dict[str, list[str]] = {
    "GENERAL": ["sponsor.name", "test_product.name", "product.name", "product.inn"],
    "BACKGROUND": [
        "product.pharmacology.mechanism",
        "product.pharmacology.indication",
        "product.chemistry.formula",
        "product.chemistry.mw",
        "product.identity.inn",
    ],
    "DESIGN": ["design.type", "design.crossover"],
    "SUBJECTS": ["subjects.planned_n", "subjects.randomized_n"],
    "PRODUCTS": ["test_product.name", "reference_product.name", "product.inn"],
    "DOSING": ["reference_product.dose", "test_product.dose"],
    "FOOD": ["food.condition"],
    "SAMPLING": ["sampling.schedule", "pk.expected_tmax", "pk.expected_t_half"],
    "PK": ["pk.parameters", "pk.expected_tmax", "pk.expected_t_half", "pk.cmax"],
    "STATISTICS": ["statistics.primary_endpoint", "statistics.model"],
    "SAFETY": ["product.safety.warnings"],
}

SECTION_CLAIM_PREFIXES: dict[str, tuple[str, ...]] = {
    "BACKGROUND": ("product.pharmacology.", "product.chemistry.", "product.identity."),
    "PRODUCTS": ("product.", "test_product.", "reference_product."),
    "DOSING": ("reference_product.dose", "test_product.dose", "product.dose"),
    "PK": ("pk.", "product.pharmacology."),
    "SAMPLING": ("pk.", "sampling."),
    "SAFETY": ("product.safety.", "safety."),
    "FOOD": ("food.",),
    "DESIGN": ("design.",),
    "SUBJECTS": ("subjects.", "sample_size."),
}


def _claim_matches_section(field_path: str, section_id: str) -> bool:
    prefixes = SECTION_CLAIM_PREFIXES.get(section_id) or ()
    fp = field_path or ""
    return any(fp.startswith(p) or fp == p.rstrip(".") for p in prefixes)


def _provenance_flags(claim: Any | None, decision: Any | None) -> dict[str, Any]:
    """Writer-facing provenance: AI proposal ≠ expert verified ≠ approved."""
    ver = (getattr(claim, "verification_status", None) or "").upper() if claim else ""
    method = (getattr(claim, "extraction_method", None) or "").upper() if claim else ""
    dec_status = str(getattr(decision, "status", None) or "").upper() if decision else ""
    ai_proposal = bool(claim) and ver == "PROPOSED"
    expert_verified = ver == "VERIFIED"
    approved = dec_status in {"APPROVED", "ACCEPTED", "RESOLVED"} or expert_verified
    return {
        "ai_proposal": ai_proposal,
        "expert_verified": expert_verified,
        "approved_for_protocol": approved,
        "extraction_method": method or None,
        "ai_confidence": getattr(claim, "confidence", None) if claim else None,
        "labels": {
            "ai_proposal": "🤖 AI proposal" if ai_proposal else None,
            "expert_verified": "✓ Verified by expert" if expert_verified else None,
            "approved": "✓ Approved for protocol" if approved else None,
        },
    }


def build_section_traceability(
    study_key: str,
    *,
    facts: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Emit section-level reverse map for writer preview / artifact metadata."""
    facts = facts or {}
    claims = list_claims(study_id=study_key)
    decisions = list_decisions(study_key)

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for section_id, field_paths in SECTION_FIELD_MAP.items():
        section_claims = [c for c in claims if _claim_matches_section(c.field_path or "", section_id)]
        # Prefer exact field paths first, then any section-matched claim once per field
        for field_path in field_paths:
            key = (section_id, field_path)
            if key in seen:
                continue
            value = facts.get(field_path)
            field_claims = [c for c in section_claims if (c.field_path or "") == field_path]
            ordered = sorted(
                field_claims,
                key=lambda c: (
                    0 if (c.verification_status or "").upper() == "VERIFIED" else 1,
                    c.claim_id or c.id or "",
                ),
            )
            claim = ordered[0] if ordered else None
            if claim is None and value is None:
                continue
            decision = next(
                (
                    d
                    for d in decisions
                    if field_path in str(getattr(d, "subject", None) or "")
                    or field_path.split(".")[-1] in str(getattr(d, "subject", None) or "").lower()
                    or field_path in str((getattr(d, "current_context", None) or {}))
                ),
                None,
            )
            src = get_source(claim.source_id) if claim and claim.source_id else None
            location: Any = None
            if claim and claim.location:
                location = claim.location
            elif claim and claim.excerpt:
                location = {"excerpt": (claim.excerpt or "")[:240]}

            entry: dict[str, Any] = {
                "protocol_section_id": section_id,
                "canonical_field": field_path,
                "value": value if value is not None else (claim.value if claim else None),
                "claim_id": (claim.claim_id or claim.id) if claim else None,
                "decision_id": getattr(decision, "id", None) if decision else None,
                "source_id": claim.source_id if claim else None,
                "source_label": (
                    (src.title if src else None)
                    or (src.source_type if src else None)
                    or (src.locator if src else None)
                    or None
                ),
                "source_type": (src.source_type if src else None),
                "location": location,
                "claim_status": claim.verification_status if claim else None,
                "provenance": _provenance_flags(claim, decision),
            }
            if entry["value"] is not None or entry["claim_id"] or entry["decision_id"]:
                seen.add(key)
                out.append(entry)

        # Also attach orphan section claims whose field is not in the map
        for claim in section_claims:
            fp = claim.field_path or "unknown"
            key = (section_id, fp)
            if key in seen:
                continue
            if any(fp == p or fp.startswith(p.rstrip(".") + ".") for p in field_paths):
                # already considered via exact match path
                if any(fp == p for p in field_paths):
                    continue
            decision = next(
                (
                    d
                    for d in decisions
                    if fp in str(getattr(d, "subject", None) or "")
                    or fp in str((getattr(d, "current_context", None) or {}))
                ),
                None,
            )
            src = get_source(claim.source_id) if claim.source_id else None
            location = claim.location or (
                {"excerpt": (claim.excerpt or "")[:240]} if claim.excerpt else None
            )
            out.append(
                {
                    "protocol_section_id": section_id,
                    "canonical_field": fp,
                    "value": claim.value,
                    "claim_id": claim.claim_id or claim.id,
                    "decision_id": getattr(decision, "id", None) if decision else None,
                    "source_id": claim.source_id,
                    "source_label": (src.title if src else None)
                    or (src.source_type if src else None),
                    "source_type": src.source_type if src else None,
                    "location": location,
                    "claim_status": claim.verification_status,
                    "provenance": _provenance_flags(claim, decision),
                }
            )
            seen.add(key)

    return out


def enrich_field_bindings_with_sources(
    field_bindings: dict[str, dict[str, Any]],
    traceability: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Attach Источник / provenance to preview field bindings."""
    by_field = {t["canonical_field"]: t for t in traceability if t.get("canonical_field")}
    out: dict[str, dict[str, Any]] = {}
    for field, meta in field_bindings.items():
        row = dict(meta)
        t = by_field.get(field)
        if t:
            row["source"] = {
                "label": t.get("source_label") or t.get("source_type") or "—",
                "source_type": t.get("source_type"),
                "claim_id": t.get("claim_id"),
                "status": t.get("claim_status"),
                "location": t.get("location"),
                "provenance": t.get("provenance"),
            }
        out[field] = row
    return out


def scrub_docx_technical_enums(doc: Any) -> dict[str, Any]:
    """Replace raw internal enums in paragraph/table text of an open Document."""
    replaced_all: list[str] = []
    for p in doc.paragraphs:
        if not p.text:
            continue
        new_text, replaced = scrub_technical_tokens_in_text(p.text)
        if replaced and new_text != p.text:
            _replace_paragraph_text(p, new_text)
            replaced_all.extend(replaced)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if not p.text:
                        continue
                    new_text, replaced = scrub_technical_tokens_in_text(p.text)
                    if replaced and new_text != p.text:
                        _replace_paragraph_text(p, new_text)
                        replaced_all.extend(replaced)
    return {"replaced": sorted(set(replaced_all)), "count": len(set(replaced_all))}


def _replace_paragraph_text(paragraph: Any, new_text: str) -> None:
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(new_text)
        return
    runs[0].text = new_text
    for r in runs[1:]:
        r.text = ""
