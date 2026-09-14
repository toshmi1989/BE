"""Phase 30 — Extract product-specific EvidenceClaims for Writer Workspace.

Reuses AIProvider + ResearchClaim store. Claims always start PROPOSED.
Never mutates Canonical Snapshot / Approved Decision / Stats / Sample Size / Draft.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.domain.ai_provider import get_ai_provider
from app.domain.ai_prompts import get_prompt
from app.domain.ai_runtime_settings import get_runtime
from app.domain.ai_schemas import ChunkContext
from app.domain.product_knowledge import FIELD_NAME_TO_PATH, SOURCE_PRIORITY
from app.domain.research_conflicts import detect_numeric_conflicts
from app.domain.research_evidence_models import ResearchClaim
from app.domain.research_evidence_store import list_claims, put_claim, put_conflict
from app.domain.research_usability import apply_usability
from app.domain.study_workspace import find_study_package


def _chunk_text(text: str, *, max_len: int = 1400) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + max_len])
        start += max_len - 150
    return parts


def _package_document_chunks(study_id: str, package_id: str | None = None) -> list[ChunkContext]:
    pkg = find_study_package(study_id, package_id)
    if pkg is None:
        return []
    ingest_cache = getattr(pkg, "_ingest_cache", None) or {}
    chunks: list[ChunkContext] = []
    for i, doc in enumerate(pkg.documents or []):
        d = doc.to_dict() if hasattr(doc, "to_dict") else dict(doc)
        # Never treat Golden / REFERENCE_OUTPUT as product-evidence content source
        role = str(d.get("role") or "").upper()
        dtype = str(d.get("document_type") or "").upper()
        if role == "REFERENCE_OUTPUT" or dtype == "GOLDEN_PROTOCOL":
            continue
        doc_id = str(d.get("document_id") or d.get("id") or f"DOC-{i}")
        text = str(d.get("extracted_text") or d.get("text") or d.get("preview_text") or "")
        if not text:
            cached = ingest_cache.get(doc_id) or {}
            text = str(cached.get("text") or "")
        if not text:
            # Filename alone is not evidence — skip
            continue
        source_id = str(d.get("source_id") or f"SRC-{doc_id}")
        for j, part in enumerate(_chunk_text(text)):
            chunks.append(
                ChunkContext(
                    chunk_id=f"{doc_id}-c{j}",
                    document_id=doc_id,
                    source_id=source_id,
                    page=int(d.get("page") or 0),
                    text=part,
                )
            )
    # Also use candidate excerpts as weak chunks (still PROPOSED only)
    for c in pkg.candidates or []:
        d = c.to_dict() if hasattr(c, "to_dict") else dict(c)
        if str(d.get("document_type") or "").upper() == "GOLDEN_PROTOCOL":
            continue
        excerpt = str(d.get("excerpt") or d.get("evidence_text") or "")
        value = d.get("value")
        if not excerpt and value is None:
            continue
        blob = excerpt or f"{d.get('field_path')}: {value}"
        doc_id = str(d.get("document_id") or "CANDIDATE")
        source_id = str(d.get("source_id") or f"SRC-{doc_id}")
        chunks.append(
            ChunkContext(
                chunk_id=f"cand-{uuid4().hex[:8]}",
                document_id=doc_id,
                source_id=source_id,
                page=int(d.get("page") or 0),
                text=blob[:1400],
            )
        )
    return chunks


def _deterministic_product_claims(chunks: list[ChunkContext], *, study_id: str) -> list[ResearchClaim]:
    """AI-off / grounding fallback — regex only, never invent."""
    out: list[ResearchClaim] = []
    for ch in chunks:
        text = ch.text or ""
        # Mechanism / class cues (must appear in text)
        for pat, field, conf in (
            (
                r"(Механизм действия\s+([^\n]{10,220}))",
                "product.mechanism",
                "HIGH",
            ),
            (
                r"([^\n.]{0,40}ингибитор(?:ы)?\s+(?:Янус|JAK|тирозин)[^\n.]{0,100})",
                "product.mechanism",
                "MEDIUM",
            ),
            (
                r"((?:Фармакотерапевтическая|Фармакологическ(?:ая|ой))\s+групп[аы]\s*[:\-]?\s*([^\n]{5,160}))",
                "product.pharmacological_class",
                "HIGH",
            ),
            (
                r"(Фармакодинамические свойства\s+(.{40,280}))",
                "product.pharmacology",
                "MEDIUM",
            ),
            (
                r"((?:МНН|INN|действующ(?:ее|его)\s+веществ[оа])\s*[:\-]?\s*([A-Za-zА-Яа-яёЁ\-]{3,80}))",
                "product.inn",
                "HIGH",
            ),
            (
                r"((?:брутто[- ]?формула|molecular formula)\s*[:\-]?\s*([A-Za-z0-9]+))",
                "product.chemical_formula",
                "MEDIUM",
            ),
        ):
            m = re.search(pat, text, re.I | re.S)
            if not m:
                continue
            excerpt = m.group(1).strip()[:240]
            value = (m.group(2) if m.lastindex and m.lastindex >= 2 else excerpt).strip()
            value = re.sub(r"\s+", " ", value).strip()[:240]
            out.append(
                _make_claim(
                    study_id=study_id,
                    field_path=field,
                    value=value,
                    excerpt=excerpt,
                    location=f"doc:{ch.document_id}/p{ch.page}",
                    source_id=ch.source_id,
                    confidence=conf,
                    extraction_method="DETERMINISTIC",
                    chunk=ch,
                )
            )
        # Expected Tmax / half-life (planning). SmPC tables often put unit
        # before the number: "(Tmax) (ч) 2–4".
        for m in re.finditer(
            r"(T\s*max[^\d\n]{0,40}(\d+(?:[.,]\d+)?(?:\s*[–\-—to]+\s*\d+(?:[.,]\d+)?))"
            r"(?:\s*(?:h|hours?|ч(?:ас[аов]*)?))?)",
            text,
            re.I,
        ):
            val = m.group(2).strip()
            out.append(
                _make_claim(
                    study_id=study_id,
                    field_path="pk.expected_tmax",
                    value=val,
                    unit="ч",
                    excerpt=m.group(1).strip()[:240],
                    location=f"doc:{ch.document_id}/p{ch.page}",
                    source_id=ch.source_id,
                    confidence="HIGH",
                    extraction_method="DETERMINISTIC",
                    chunk=ch,
                    measurement={
                        "parameter": "Tmax",
                        "unit": "h",
                        "parameter_context": "expected/planning Tmax (pre-study)",
                        "statistic_type": "RANGE"
                        if re.search(r"[–\-—to]", val)
                        else "POINT",
                        "applicability": "UNKNOWN",
                        "verification_status": "PROPOSED",
                        "usability": "REQUIRES_REVIEW",
                    },
                )
            )
        for m2 in re.finditer(
            r"((?:half[- ]?life|период полувыведения|t\s*1\s*/\s*2|t½)"
            r"[^\d\n]{0,40}(\d+(?:[.,]\d+)?(?:\s*[–\-—to]+\s*\d+(?:[.,]\d+)?))"
            r"(?:\s*(?:h|hours?|ч(?:ас[аов]*)?))?)",
            text,
            re.I,
        ):
            if re.search(r"\bAUC\b", m2.group(1), re.I):
                continue
            val = m2.group(2).strip()
            if re.fullmatch(r"0\s*[–\-—]\s*72", val):
                # AUC0-72 window false positive — not half-life
                continue
            out.append(
                _make_claim(
                    study_id=study_id,
                    field_path="pk.expected_t_half",
                    value=val,
                    unit="ч",
                    excerpt=m2.group(1).strip()[:240],
                    location=f"doc:{ch.document_id}/p{ch.page}",
                    source_id=ch.source_id,
                    confidence="HIGH",
                    extraction_method="DETERMINISTIC",
                    chunk=ch,
                    measurement={
                        "parameter": "t1/2",
                        "unit": "h",
                        "parameter_context": "expected/planning half-life (pre-study)",
                        "statistic_type": "RANGE"
                        if re.search(r"[–\-—to]", val)
                        else "POINT",
                        "applicability": "UNKNOWN",
                        "verification_status": "PROPOSED",
                        "usability": "REQUIRES_REVIEW",
                    },
                )
            )
    return out


def _make_claim(
    *,
    study_id: str,
    field_path: str,
    value: Any,
    excerpt: str,
    location: str,
    source_id: str,
    confidence: str,
    extraction_method: str,
    chunk: ChunkContext | None = None,
    unit: str | None = None,
    measurement: dict[str, Any] | None = None,
) -> ResearchClaim:
    claim = ResearchClaim(
        claim_text=f"{field_path}: {value}",
        research_task_id=f"PRODUCT-EXTRACT-{study_id}",
        field_path=field_path,
        value=value,
        unit=unit,
        source_id=source_id,
        source_result_id=None,
        excerpt=excerpt,
        location=location,
        extraction_method=extraction_method,
        confidence=confidence if confidence in {"LOW", "MEDIUM", "HIGH"} else "MEDIUM",
        verification_status="PROPOSED",
        applicability="UNKNOWN",
        usability="REQUIRES_REVIEW",
        study_id=study_id,
        measurement=measurement,
    )
    apply_usability(claim)
    # Force PROPOSED — AI confidence ≠ verification
    claim.verification_status = "PROPOSED"
    return claim


def _ai_claims_to_research(
    study_id: str,
    ai_claims: list[Any],
    chunks: list[ChunkContext],
) -> list[ResearchClaim]:
    by_chunk = {c.chunk_id: c for c in chunks}
    out: list[ResearchClaim] = []
    for ac in ai_claims:
        field = str(getattr(ac, "field_name", None) or "")
        path = FIELD_NAME_TO_PATH.get(field, field if field.startswith("product.") or field.startswith("pk.") else "")
        if not path:
            continue
        ch = by_chunk.get(getattr(ac, "chunk_id", None))
        excerpt = str(getattr(ac, "evidence_text", None) or "")
        if not excerpt:
            continue
        conf_f = float(getattr(ac, "confidence", 0.5) or 0.5)
        conf = "HIGH" if conf_f >= 0.85 else ("MEDIUM" if conf_f >= 0.6 else "LOW")
        out.append(
            _make_claim(
                study_id=study_id,
                field_path=path,
                value=getattr(ac, "value", None),
                unit=getattr(ac, "unit", None),
                excerpt=excerpt[:240],
                location=f"doc:{getattr(ac, 'document_id', '')}/p{getattr(ac, 'page', 0)}",
                source_id=str(getattr(ac, "source_id", None) or (ch.source_id if ch else "UNKNOWN")),
                confidence=conf,
                extraction_method="AI",
                chunk=ch,
            )
        )
    return out


def extract_product_evidence_for_study(
    study_id: str,
    *,
    package_id: str | None = None,
    force_mock: bool = False,
    actor: str = "system",
) -> dict[str, Any]:
    """Run product-specific extraction → ResearchClaim(PROPOSED) only."""
    chunks = _package_document_chunks(study_id, package_id)
    created: list[ResearchClaim] = []
    notes: list[str] = []

    # Deterministic always (AI-off safe)
    for c in _deterministic_product_claims(chunks, study_id=study_id):
        put_claim(c)
        created.append(c)

    settings = get_settings()
    runtime = get_runtime()
    ai_on = bool(runtime.enabled if runtime.enabled is not None else settings.ai_enabled)
    provider_name = "disabled"
    if ai_on or force_mock:
        try:
            provider = get_ai_provider(
                enabled=True if force_mock else ai_on,
                provider="mock" if force_mock else (runtime.provider or settings.ai_provider),
                force_mock=force_mock,
                base_url=runtime.base_url or settings.ai_base_url,
                model=runtime.model or settings.ai_model,
                api_key=runtime.api_key or settings.openai_api_key,
                timeout=settings.ai_timeout,
            )
            provider_name = provider.name
            if chunks and provider.name != "disabled":
                # PK + product prompts via existing provider surface
                pk = provider.extract_pk_data(chunks)
                prod = provider.extract_product_data(chunks)
                # Optional pharmacology prompt if registered
                try:
                    pharm_prompt = get_prompt("EXTRACT_PHARMACOLOGY")
                    pharm = provider.extract_evidence(
                        task_type="EXTRACT_PHARMACOLOGY",
                        chunks=chunks,
                        prompt=pharm_prompt,
                    )
                except Exception:  # noqa: BLE001
                    pharm = None
                ai_list = list(pk.claims) + list(prod.claims)
                if pharm:
                    ai_list.extend(pharm.claims)
                for c in _ai_claims_to_research(study_id, ai_list, chunks):
                    put_claim(c)
                    created.append(c)
            else:
                notes.append("AI unavailable or no chunks — deterministic only")
        except Exception as e:  # noqa: BLE001
            notes.append(f"AI skipped: {e}")
            provider_name = "disabled"
    else:
        notes.append("AI_ENABLED=false — deterministic extraction only")

    # Detect numeric conflicts (Tmax / t½) — never auto-resolve
    conflicts_out = []
    all_claims = list_claims(study_id=study_id)
    for fp in ("pk.expected_tmax", "pk.expected_t_half", "pk.Tmax", "pk.t_half"):
        for conf in detect_numeric_conflicts(all_claims, field_path=fp, study_id=study_id):
            put_conflict(conf)
            conflicts_out.append(conf.to_dict() if hasattr(conf, "to_dict") else conf.__dict__)

    return {
        "study_id": study_id,
        "provider": provider_name,
        "chunks": len(chunks),
        "claims_created": len(created),
        "claims": [c.to_dict() for c in created],
        "conflicts": conflicts_out,
        "source_priority": list(SOURCE_PRIORITY),
        "auto_verified": False,
        "study_mutated": False,
        "canonical_mutated": False,
        "notes": notes,
        "actor": actor,
    }


def list_product_evidence_panel(study_id: str) -> dict[str, Any]:
    """Writer UI contract: AI proposals for product-specific fields."""
    from app.domain.product_knowledge import PRODUCT_KNOWLEDGE_FIELDS

    paths = {f.field_path for f in PRODUCT_KNOWLEDGE_FIELDS}
    # Also include legacy pk.Tmax / pk.t_half
    paths |= {"pk.Tmax", "pk.t_half"}
    claims = [c for c in list_claims(study_id=study_id) if c.field_path in paths]
    proposals = []
    for c in claims:
        proposals.append(
            {
                "claim_id": c.id,
                "field": c.field_path,
                "value": c.value,
                "unit": c.unit,
                "source_id": c.source_id,
                "location": c.location,
                "excerpt": c.excerpt,
                "confidence": c.confidence,
                "ai_confidence_note": "AI confidence is NOT expert verification",
                "applicability": c.applicability,
                "applicability_reason": c.applicability_reason,
                "status": c.verification_status,
                "extraction_method": c.extraction_method,
                "usable": c.usability == "USABLE_FOR_DECISION",
                "badge": "🤖 AI proposal" if c.extraction_method == "AI" else "📄 Source extract",
            }
        )
    proposed = [p for p in proposals if p["status"] == "PROPOSED"]
    verified = [p for p in proposals if p["status"] == "VERIFIED"]
    rejected = [p for p in proposals if p["status"] == "REJECTED"]
    return {
        "study_id": study_id,
        "proposals": proposals,
        "counts": {
            "total": len(proposals),
            "proposed": len(proposed),
            "verified": len(verified),
            "rejected": len(rejected),
        },
        "actions": ["Verify", "Reject", "Request another source"],
        "study_mutated": False,
    }
