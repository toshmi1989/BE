"""Deep read — Phase 29.1.

A search snippet almost never states a PK number; the number sits inside the
document (FDA review, SmPC, journal article). This module opens the sources
found by a search, cuts out the passages that actually state a value, and runs
the same deterministic extraction over them.

Never mutates Study. Never verifies anything: every claim stays PROPOSED.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from app.domain.research_evidence_models import ResearchClaim, SourceResult
from app.domain.research_evidence_store import (
    get_task,
    list_claims,
    list_results,
    put_claim,
    put_result,
    put_task,
)
from app.domain.research_evidence_engine import register_source_from_result
from app.domain import research_fetch
from app.domain.research_extract import extract_claims_from_hit
from app.domain.research_http import ResearchHttpError
from app.domain.research_provider import ProviderHit
from app.domain.research_real_search import list_stored_search_results
from app.domain.research_sanitize import sanitize_snippet
from app.domain.research_tables import cv_table_findings
from app.domain.research_usability import apply_usability

# What to look for in the full text, per field the caller still needs
FIELD_PATTERNS: dict[str, str] = {
    "pk.Tmax": r"t\s*max|время\s+достижения\s+максимальной",
    "pk.t_half": r"half[-\s]?li(?:fe|ves)|t\s*1\s*/\s*2|t½|период\s+полувыведения",
    "cv_intra": (
        r"within[-\s]?subject|intra[-\s]?subject|intra[-\s]?individual|"
        r"between[-\s]?subject|inter[-\s]?subject|inter[-\s]?individual|"
        r"coefficient\s+of\s+variation|вариабельност"
    ),
    "food.calorie_target": r"kcal|calorie|breakfast|ккал|высококалорийн",
}

# Sources the reader opens first: official ones before commentary
_PRIORITY_ORDER: dict[str, int] = {
    "OFFICIAL_REGULATORY": 0,
    "OFFICIAL_PRODUCT": 1,
    "PEER_REVIEWED": 2,
    "CLINICAL_DATABASE": 3,
    "PUBLICATION": 4,
    "INTERNAL_PROTOCOL": 5,
    "OTHER": 6,
}

_HIT_SOURCE_TYPE: dict[str, str] = {
    "SMPC": "SMPC",
    "PRODUCT_LABEL": "SMPC",
    "REGULATORY": "REGULATORY",
    "GUIDELINE": "REGULATORY",
    "PUBLICATION": "PUBLICATION",
    "CLINICAL_STUDY": "CLINICAL_STUDY",
    "PROTOCOL": "PROTOCOL",
    "REVIEW": "REVIEW",
    "DATABASE": "DATABASE",
}

_HAS_NUMBER = re.compile(r"\d")


def relevant_passages(
    text: str,
    pattern: str,
    *,
    window: int = 260,
    limit: int = 6,
) -> list[str]:
    """Passages that name the parameter and state a number next to it.

    A mention without a number carries nothing to propose, so it is skipped —
    that is what keeps the reader from inventing values.
    """
    if not text:
        return []
    # PDF text arrives wrapped every ~60 characters; a label and its value are
    # routinely split across lines, so the passage is read as running text.
    flat = re.sub(r"\s+", " ", text)
    found: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(pattern, flat, re.I):
        start = max(0, m.start() - window)
        end = min(len(flat), m.end() + window)
        passage = flat[start:end].strip()
        if not _HAS_NUMBER.search(passage):
            continue
        key = passage[:120].lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(passage)
        if len(found) >= limit:
            break
    return found


def _claim_key(claim: ResearchClaim) -> tuple:
    """Identity of a proposal. One table states a CV per PK parameter, and two
    parameters can share the same number — the parameter is part of the identity.
    """
    cv = claim.cvintra or {}
    return (
        claim.source_result_id,
        claim.field_path,
        claim.value,
        cv.get("PK_parameter"),
        cv.get("CV_range_low"),
        cv.get("CV_range_high"),
    )


def _source_result_for(task_id: str, study_id: str | None, result: Any, text: str) -> SourceResult:
    """Reuse the SourceResult of the snippet pass so evidence stays on one source."""
    for existing in list_results(task_id):
        if existing.url_or_source_locator == result.url:
            return existing
    stype = str(result.source_type or "OTHER")
    sr = SourceResult(
        research_task_id=task_id,
        provider=str(result.provider or "WEB"),
        title=result.title,
        url_or_source_locator=result.url,
        source_type=_HIT_SOURCE_TYPE.get(stype, "OTHER"),
        publication_date=result.publication_date,
        author=result.authors,
        identifier=result.identifier,
        raw_metadata=dict(result.raw_metadata or {}),
        text_excerpt=sanitize_snippet(text[:2000]),
        study_id=study_id,
    )
    put_result(sr)
    return sr


def deep_read_task_sources(
    task_id: str,
    *,
    field_paths: list[str] | None = None,
    context: dict[str, Any] | None = None,
    max_sources: int = 5,
    client: Any = None,
    fetcher: Callable[..., tuple[Any, str]] | None = None,
) -> dict[str, Any]:
    """Open the sources of a finished search and extract from their full text."""
    task = get_task(task_id)
    if task is None:
        raise KeyError("task not found")

    wanted = [f for f in (field_paths or list(FIELD_PATTERNS)) if f in FIELD_PATTERNS]
    if not wanted:
        wanted = list(FIELD_PATTERNS)
    pattern = "|".join(FIELD_PATTERNS[f] for f in wanted)

    results = sorted(
        list_stored_search_results(task_id),
        key=lambda r: _PRIORITY_ORDER.get(str(r.priority_class), 9),
    )

    ctx = context or {}
    substance = str(ctx.get("active_substance") or "").strip()

    read: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    new_claims: list[ResearchClaim] = []
    passages_total = 0
    table_values_total = 0

    # Resolved per call so a test can substitute the reader without the network
    read_source = fetcher or research_fetch.fetch_and_snapshot

    for result in results[:max_sources]:
        try:
            _snapshot, text = read_source(result.url, client=client)
        except ResearchHttpError as exc:
            failed.append({"url": result.url, "title": result.title, "error": exc.kind})
            continue
        except Exception as exc:  # noqa: BLE001 — one bad source must not stop the read
            failed.append({"url": result.url, "title": result.title, "error": str(exc)[:120]})
            continue

        passages = relevant_passages(text, pattern)
        passages_total += len(passages)
        # Variability is usually tabulated, so the tables are read as well
        findings = cv_table_findings(text) if "cv_intra" in wanted else []
        table_values_total += len(findings)
        # A document that never names the substance may be describing another drug
        names_substance = bool(substance) and substance.lower() in (text or "").lower()
        read.append(
            {
                "url": result.url,
                "title": result.title,
                "characters": len(text or ""),
                "passages": len(passages),
                "table_values": len(findings),
                "names_substance": names_substance if substance else None,
            }
        )
        if not passages and not findings:
            continue

        sr = _source_result_for(task_id, task.study_id, result, text)
        register_source_from_result(sr, study_id=task.study_id)
        meta = dict(result.raw_metadata or {})
        meta["read_mode"] = "FULL_TEXT"

        reads: list[tuple[str, dict[str, Any]]] = [(p, meta) for p in passages]
        # A table cell needs no re-parsing: its row and column already say what it is
        reads += [(f.excerpt, f.as_metadata()) for f in findings]

        for passage, passage_meta in reads:
            hit = ProviderHit(
                title=result.title,
                locator=result.url,
                source_type=_HIT_SOURCE_TYPE.get(str(result.source_type or "OTHER"), "OTHER"),
                text=passage,
                author=result.authors,
                publication_date=result.publication_date,
                identifier=result.identifier,
                metadata=passage_meta,
            )
            for claim in extract_claims_from_hit(
                hit,
                research_task_id=task_id,
                source_result=sr,
                study_id=task.study_id,
                context=ctx,
            ):
                if substance and not names_substance:
                    claim.applicability = "LOW"
                    claim.applicability_reason = (
                        f"Документ не упоминает «{substance}» — значение может относиться "
                        "к другому препарату"
                    )
                if any(_claim_key(x) == _claim_key(claim) for x in list_claims(task_id)):
                    continue
                claim.verification_status = "PROPOSED"
                apply_usability(claim)
                put_claim(claim)
                new_claims.append(claim)

    if new_claims:
        task.status = "REVIEW_REQUIRED"
        put_task(task)

    return {
        "task_id": task_id,
        "sources_read": read,
        "sources_failed": failed,
        "passages": passages_total,
        "table_values": table_values_total,
        "claims": [c.to_dict() for c in new_claims],
        "new_claim_count": len(new_claims),
        "study_mutated": False,
        "automatic_verifications": 0,
    }
