"""Register search results as Source/SourceVersion — Phase 15.3.

SearchResult → (select) → Source → SourceVersion → Claims (PROPOSED).
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from app.domain.research_evidence_models import RegisteredSource, ResearchClaim, SourceResult
from app.domain.research_evidence_store import (
    find_source_by_locator_or_id,
    list_claims,
    put_claim,
    put_result,
    put_source,
)
from app.domain.research_extract import extract_claims_from_hit
from app.domain.research_fetch import fetch_and_snapshot
from app.domain.research_provider import ProviderHit
from app.domain.research_sanitize import sanitize_title, sanitize_url
from app.domain.research_search_result import ResearchSearchResult, infer_priority_class
from app.domain.research_usability import apply_usability


def register_search_result_as_source(
    result: ResearchSearchResult,
    *,
    research_task_id: str,
    study_id: str | None = None,
    fetch_content: bool = False,
    client=None,
    mock_text: str | None = None,
    context: dict[str, Any] | None = None,
    auto_extract: bool = True,
) -> dict[str, Any]:
    """Register a selected search result. Claims remain PROPOSED.

    Official priority does NOT auto-verify.
    """
    url = sanitize_url(result.url) or result.url
    existing = find_source_by_locator_or_id(url, result.identifier)
    if existing:
        src = existing
    else:
        src = RegisteredSource(
            locator=url,
            source_type=result.source_type if result.source_type != "UNKNOWN" else "OTHER",
            title=sanitize_title(result.title),
            content_hash=None,
            classification=result.priority_class,
            study_id=study_id or result.study_id,
        )
        put_source(src)

    sr = SourceResult(
        research_task_id=research_task_id,
        provider=result.provider,
        title=sanitize_title(result.title),
        url_or_source_locator=url,
        source_type={
            "SMPC": "SMPC",
            "REGULATORY": "REGULATORY",
            "GUIDELINE": "REGULATORY",
            "PUBLICATION": "PUBLICATION",
            "CLINICAL_STUDY": "CLINICAL_STUDY",
            "REVIEW": "REVIEW",
            "DATABASE": "DATABASE",
            "PROTOCOL": "PROTOCOL",
        }.get(result.source_type, "OTHER"),
        publication_date=result.publication_date,
        author=result.authors,
        identifier=result.identifier,
        raw_metadata={
            **(result.raw_metadata or {}),
            "priority_class": result.priority_class,
            "priority_is_not_verification": True,
        },
        text_excerpt=result.snippet,
        registered_source_id=src.id,
        registered_source_version_id=src.version_id,
        study_id=study_id or result.study_id,
    )
    put_result(sr)
    result.registered = True
    result.registered_source_id = src.id

    snapshot = None
    claims: list[ResearchClaim] = []
    extracted_text = result.snippet or ""

    if fetch_content:
        if mock_text is not None:
            snapshot, extracted_text = fetch_and_snapshot(
                f"mock://registered/{src.id}",
                client=client,
                allow_local_mock_text=mock_text,
            )
            snapshot.locator = url  # preserve real locator in snapshot metadata
            snapshot.document_metadata = {
                **(snapshot.document_metadata or {}),
                "original_locator": url,
                "fetched_via": "mock_text_override",
            }
        else:
            snapshot, extracted_text = fetch_and_snapshot(url, client=client)
        if snapshot.content_hash:
            src.content_hash = snapshot.content_hash
            put_source(src)
        sr.text_excerpt = snapshot.text_excerpt
        sr.content_hash = snapshot.content_hash
        if snapshot.source_version_id:
            sr.registered_source_version_id = snapshot.source_version_id
            src.version_id = snapshot.source_version_id
            put_source(src)
        put_result(sr)

    if auto_extract and extracted_text:
        hit = ProviderHit(
            title=sr.title,
            locator=url,
            source_type=sr.source_type,
            text=extracted_text,
            author=sr.author,
            publication_date=sr.publication_date,
            identifier=sr.identifier,
            metadata=dict(sr.raw_metadata or {}),
        )
        for c in extract_claims_from_hit(
            hit,
            research_task_id=research_task_id,
            source_result=sr,
            study_id=study_id,
            context=context or {},
        ):
            c.verification_status = "PROPOSED"
            apply_usability(c)
            # Dedup
            if any(
                x.source_result_id == c.source_result_id
                and x.field_path == c.field_path
                and x.value == c.value
                for x in list_claims(research_task_id)
            ):
                continue
            put_claim(c)
            claims.append(c)

    return {
        "source": src.to_dict(),
        "source_result": sr.to_dict(),
        "snapshot": snapshot.to_dict() if snapshot else None,
        "claims": [c.to_dict() for c in claims],
        "priority_class": result.priority_class,
        "verification_status": "PROPOSED",
        "study_mutated": False,
        "automatic_verifications": 0,
    }


def maybe_auto_register_official(
    results: list[ResearchSearchResult],
    *,
    research_task_id: str,
    study_id: str | None = None,
) -> list[dict[str, Any]]:
    """High-confidence official sources may auto-register as Source candidates.

    Claims remain PROPOSED. Priority ≠ verification.
    """
    out = []
    for r in results:
        if r.priority_class in {"OFFICIAL_REGULATORY", "OFFICIAL_PRODUCT"}:
            out.append(
                register_search_result_as_source(
                    r,
                    research_task_id=research_task_id,
                    study_id=study_id,
                    fetch_content=False,
                    auto_extract=False,
                )
            )
    return out
