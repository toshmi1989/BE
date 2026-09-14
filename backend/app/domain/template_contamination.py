"""Phase 29.2 — Semantic template contamination registry (primary protection).

Token scrub remains secondary. Product-specific Bosutinib/Bosulif example content
must be cleared or block generation — never left under another product's name.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable

from app.domain.protocol_template_registry import study_is_bosutinib_sample


def _sha16(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ContaminationBlock:
    block_id: str
    category: str
    classification: str  # PRODUCT_SPECIFIC | UNKNOWN
    renderer_action: str  # CLEAR_OR_BLOCK | POPULATE_FROM_EVIDENCE | BLOCK
    source_field: str | None
    fingerprint: str | None
    markers: tuple[str, ...]
    notes: str = ""


# Semantic markers — absence of "Бозутиниб" is NOT proof of generic content.
CONTAMINATION_MARKER_GROUPS: dict[str, tuple[str, ...]] = {
    "PRODUCT_NAME": (
        "Бозутиниб",
        "бозутиниб",
        "Бозутиниба",
        "бозутиниба",
        "Бозулиф",
        "бозулиф",
        "Bosutinib",
        "bosutinib",
        "Bosulif",
        "bosulif",
        "BOSUTINIB",
        "BOSULIF",
    ),
    "DISEASE_CML": (
        "хронического миелоидного лейкоза",
        "хронический миелоидный лейкоз",
        "миелоидного лейкоза",
        "миелоидный лейкоз",
        "ХМЛ",
        "CML",
        "Ph-положительн",
        "Ph+",
        "филадельфийской хромосом",
        "Philadelphia",
    ),
    "MECHANISM_TKI": (
        "тирозинкиназ",
        "тирозин-киназ",
        "тирозиновой киназ",
        "ингибитор тирозин",
        "Bcr-Abl",
        "BCR-ABL",
        "Bcr–Abl",
        "киназы Src",
        "Src-киназ",
    ),
    "CHEMISTRY_BOSUTINIB": (
        "C26H29Cl2N5O3",
        "C₂₆H₂₉Cl₂N₅O₃",
        "530,45",
        "530.45",
        "дихлорфенил",
        "метилпиперазин-1-ил",
        "хиназолин",
        "4-[(2,4-дихлорфенил)",
    ),
    "ATC_BOSUTINIB": (
        "L01EA04",
        "L01XE14",
    ),
    "INDICATION_BOSULIF": (
        "Бозулиф",
        "Bosulif",
    ),
}

# Fingerprints of known PRODUCT_SPECIFIC template paragraphs/cells (Phase 29.2 audit).
# Primary clear targets — secondary to marker scan.
TEMPLATE_CONTAMINATION_FINGERPRINTS: frozenset[str] = frozenset(
    {
        # Loaded from docs/_phase29_2_fingerprints.txt at audit time; kept inline for runtime.
        "0a1f3c8e9b2d4e6f",  # placeholder — replaced below from real audit set
    }
)


def _load_audit_fingerprints() -> frozenset[str]:
    """Prefer inventory fingerprints when present; fall back to embedded set."""
    from pathlib import Path

    inv = Path(__file__).resolve().parents[3] / "docs" / "_phase29_template_inventory.json"
    if inv.is_file():
        try:
            import json

            data = json.loads(inv.read_text(encoding="utf-8"))
            fps = (
                (data.get("phase29_2_semantic_audit") or {}).get("contamination_fingerprints")
                or []
            )
            if fps:
                return frozenset(str(x) for x in fps)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    fp_file = Path(__file__).resolve().parents[3] / "docs" / "_phase29_2_fingerprints.txt"
    if fp_file.is_file():
        lines = [ln.strip() for ln in fp_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            return frozenset(lines)
    return frozenset()


CONTAMINATION_FINGERPRINTS: frozenset[str] = _load_audit_fingerprints()


CONTAMINATION_BLOCKS: tuple[ContaminationBlock, ...] = (
    ContaminationBlock(
        "pharm.2.1.mechanism_cml",
        "PHARMACOLOGY",
        "PRODUCT_SPECIFIC",
        "CLEAR_OR_BLOCK",
        "evidence.pharmacology",
        None,
        CONTAMINATION_MARKER_GROUPS["DISEASE_CML"]
        + CONTAMINATION_MARKER_GROUPS["MECHANISM_TKI"],
        "§2.1 Bosutinib/CML/TKI narrative",
    ),
    ContaminationBlock(
        "pharm.2.1.chemistry",
        "CHEMICAL_FORMULA",
        "PRODUCT_SPECIFIC",
        "CLEAR_OR_BLOCK",
        "product.chemistry",
        None,
        CONTAMINATION_MARKER_GROUPS["CHEMISTRY_BOSUTINIB"],
        "Chemical name / formula / MW of Bosutinib example",
    ),
    ContaminationBlock(
        "pharm.2.8.properties",
        "PHARMACOLOGY",
        "PRODUCT_SPECIFIC",
        "CLEAR_OR_BLOCK",
        "evidence.pharmacology",
        None,
        CONTAMINATION_MARKER_GROUPS["PRODUCT_NAME"]
        + CONTAMINATION_MARKER_GROUPS["MECHANISM_TKI"],
        "§2.8 pharmacological properties of bosutinib",
    ),
    ContaminationBlock(
        "product.names",
        "PRODUCT_NAME",
        "PRODUCT_SPECIFIC",
        "CLEAR_OR_BLOCK",
        "product.trade_name|inn",
        None,
        CONTAMINATION_MARKER_GROUPS["PRODUCT_NAME"],
        "Embedded Bosutinib/Bosulif names",
    ),
    ContaminationBlock(
        "atc.bosutinib",
        "ATC",
        "PRODUCT_SPECIFIC",
        "CLEAR_OR_BLOCK",
        "product.atc",
        None,
        CONTAMINATION_MARKER_GROUPS["ATC_BOSUTINIB"],
        "Bosutinib ATC codes",
    ),
)


CLEARED_PLACEHOLDER_RU = (
    "[СОДЕРЖАНИЕ УДАЛЕНО: в шаблоне был пример другого препарата. "
    "Требуются верифицированные данные по исследуемому препарату текущего исследования.]"
)


def iter_contamination_markers() -> Iterable[str]:
    for group in CONTAMINATION_MARKER_GROUPS.values():
        yield from group


def text_contamination_hits(text: str) -> list[dict[str, str]]:
    """Return marker hits (category + token) for a text blob."""
    if not text:
        return []
    hits: list[dict[str, str]] = []
    lower = text.lower()
    for cat, tokens in CONTAMINATION_MARKER_GROUPS.items():
        for tok in tokens:
            if tok.isascii():
                found = tok.lower() in lower
            else:
                found = tok in text or tok.lower() in lower
            if found:
                hits.append({"category": cat, "token": tok})
    return hits


def fingerprint_match(text: str) -> bool:
    if not text or not CONTAMINATION_FINGERPRINTS:
        return False
    return _sha16(text) in CONTAMINATION_FINGERPRINTS


def is_product_specific_text(text: str) -> bool:
    if fingerprint_match(text):
        return True
    hits = text_contamination_hits(text)
    if not hits:
        return False
    cats = {h["category"] for h in hits}
    # Strong semantic contamination
    if cats & {
        "PRODUCT_NAME",
        "DISEASE_CML",
        "MECHANISM_TKI",
        "CHEMISTRY_BOSUTINIB",
        "ATC_BOSUTINIB",
        "INDICATION_BOSULIF",
    }:
        return True
    return False


def has_verified_product_pharmacology(study_ctx: dict[str, Any]) -> bool:
    """True only when all Phase 30 required pharmacology fields are verified for this study.

    required_for_final_pharmacology catalog fields must each be source-backed and
    VERIFIED (via structured_facts + fact_sources, or live VERIFIED ResearchClaims).
    A single unrelated pharmacology snippet must not clear the FINAL gate.
    """
    from app.domain.product_knowledge import PRODUCT_KNOWLEDGE_FIELDS

    required = [
        f.field_path
        for f in PRODUCT_KNOWLEDGE_FIELDS
        if f.required_for_final_pharmacology
    ]
    if not required:
        return False

    facts = study_ctx.get("structured_facts") or {}
    sources = study_ctx.get("fact_sources") or {}
    ok_sources = {
        "VERIFIED",
        "EXPERT_INPUT",
        "VERIFIED_EVIDENCE",
        "APPROVED_DECISION",
        "CANONICAL",
        "RESEARCH_EVIDENCE",
    }

    verified_paths: set[str] = set()
    for key in required:
        if facts.get(key) not in (None, "", [], {}):
            src = sources.get(key)
            if str(src or "").upper() in ok_sources:
                verified_paths.add(key)

    study_id = study_ctx.get("study_id") or study_ctx.get("project_id")
    if study_id:
        try:
            from app.domain.research_evidence_store import list_claims

            for c in list_claims(study_id=str(study_id)):
                if c.verification_status != "VERIFIED":
                    continue
                if c.field_path not in required:
                    continue
                if c.applicability in {"LOW", "NOT_APPLICABLE", "UNKNOWN"}:
                    continue
                if c.value not in (None, "", []):
                    verified_paths.add(c.field_path)
        except Exception:  # noqa: BLE001
            pass

    return all(fp in verified_paths for fp in required)


def contamination_preflight(
    study_ctx: dict[str, Any],
    *,
    mode: str = "DRAFT",
) -> dict[str, Any]:
    """Assess whether template product-specific content is unmanaged for this study."""
    product = study_ctx.get("product") or {}
    if study_is_bosutinib_sample(product):
        return {
            "ok": True,
            "code": "CRITICAL_TEMPLATE_CONTAMINATION",
            "skipped": "study_is_bosutinib_sample",
            "unmanaged_blocks": [],
            "message": "Study matches Bosutinib sample identity — template example allowed",
        }

    verified = has_verified_product_pharmacology(study_ctx)
    unmanaged: list[dict[str, Any]] = []
    mode_u = str(mode).upper()
    for block in CONTAMINATION_BLOCKS:
        if block.classification != "PRODUCT_SPECIFIC":
            unmanaged.append(
                {
                    "block_id": block.block_id,
                    "reason": "UNKNOWN_MUST_NOT_REMAIN",
                    "action": block.renderer_action,
                }
            )
            continue
        if block.renderer_action == "POPULATE_FROM_EVIDENCE" and not verified:
            # DRAFT: renderer clears / leaves placeholder — do not block export.
            # FINAL: must have verified evidence for populate fields.
            if mode_u == "FINAL":
                unmanaged.append(
                    {
                        "block_id": block.block_id,
                        "reason": "MISSING_VERIFIED_EVIDENCE",
                        "action": block.renderer_action,
                        "source_field": block.source_field,
                    }
                )
        elif block.renderer_action == "BLOCK":
            unmanaged.append(
                {
                    "block_id": block.block_id,
                    "reason": "EXPLICIT_BLOCK",
                    "action": block.renderer_action,
                }
            )
        elif block.renderer_action == "CLEAR_OR_BLOCK":
            # DRAFT: clear allowed at render time. FINAL: need verified pharmacology.
            if mode_u == "FINAL" and not verified:
                unmanaged.append(
                    {
                        "block_id": block.block_id,
                        "reason": "FINAL_REQUIRES_VERIFIED_EVIDENCE",
                        "action": block.renderer_action,
                        "source_field": block.source_field,
                    }
                )

    # Fingerprints are secondary protection for the scrubber — never block DRAFT
    # solely because the audit inventory file was not shipped with the build.
    fingerprint_gap = not CONTAMINATION_FINGERPRINTS
    if fingerprint_gap and mode_u == "FINAL":
        unmanaged.append(
            {
                "block_id": "registry.fingerprints",
                "reason": "MISSING_FINGERPRINT_BASELINE",
                "action": "BLOCK",
            }
        )

    ok = len(unmanaged) == 0
    return {
        "ok": ok,
        "code": "CRITICAL_TEMPLATE_CONTAMINATION",
        "unmanaged_blocks": unmanaged,
        "clearable_blocks": [b.block_id for b in CONTAMINATION_BLOCKS if b.renderer_action == "CLEAR_OR_BLOCK"],
        "verified_pharmacology": verified,
        "mode": mode,
        "fingerprint_count": len(CONTAMINATION_FINGERPRINTS),
        "fingerprint_baseline_missing": fingerprint_gap,
        "message": (
            "Template product-specific content will be cleared or populated at render"
            if ok
            else "Template contains product-specific content that is not supported by the current study."
        ),
        "action": (
            "None"
            if ok
            else "Resolve template/content mapping before DOCX generation."
        ),
    }


def scan_text_blob_for_contamination(blob: str) -> dict[str, Any]:
    hits = text_contamination_hits(blob)
    by_cat: dict[str, int] = {}
    for h in hits:
        by_cat[h["category"]] = by_cat.get(h["category"], 0) + 1
    contaminated = bool(hits)
    return {
        "contaminated": contaminated,
        "hit_count": len(hits),
        "by_category": by_cat,
        "sample_hits": hits[:30],
    }
