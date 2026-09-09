"""Bibliographic ReferenceBuilder — Phase 12B.4.

Distinct from cross-ref ReferenceRegistry (section/table/appendix links).
Builds literature entries from Sources / EvidenceClaims / RegulatoryBases.
No invented citations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BibliographyEntry:
    reference_id: str
    source_id: str | None
    citation: str
    title: str | None
    authors: Any
    year: Any
    url: str | None
    document_identifier: str | None
    usage_locations: list[str] = field(default_factory=list)
    evidence_claim_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm_cite(text: str | None) -> str:
    return (text or "").strip().lower()


def _authors_display(authors: Any) -> str | None:
    if authors is None:
        return None
    if isinstance(authors, list):
        parts = [str(a).strip() for a in authors if str(a).strip()]
        return ", ".join(parts) if parts else None
    s = str(authors).strip()
    return s or None


def _citation_from_source(src: dict) -> str:
    parts: list[str] = []
    auth = _authors_display(src.get("authors"))
    if auth:
        parts.append(auth)
    title = src.get("title") or src.get("citation")
    if title:
        parts.append(str(title))
    if src.get("year") is not None:
        parts.append(str(src["year"]))
    if src.get("document_identifier"):
        parts.append(str(src["document_identifier"]))
    if src.get("url"):
        parts.append(str(src["url"]))
    if src.get("section"):
        parts.append(f"§{src['section']}")
    if src.get("page") is not None:
        parts.append(f"p.{src['page']}")
    if parts:
        return ". ".join(parts)
    return str(src.get("citation") or src.get("id") or "")


def _citation_from_regulatory(rb: dict) -> str:
    parts: list[str] = []
    if rb.get("title"):
        parts.append(str(rb["title"]))
    if rb.get("document_identifier"):
        parts.append(str(rb["document_identifier"]))
    if rb.get("section_reference"):
        parts.append(str(rb["section_reference"]))
    if rb.get("jurisdiction"):
        parts.append(str(rb["jurisdiction"]))
    if rb.get("effective_date"):
        parts.append(str(rb["effective_date"]))
    return ". ".join(parts) if parts else str(rb.get("id") or "")


def _merge_entry(existing: BibliographyEntry, *, locations: list[str], claim_ids: list[str]) -> None:
    for loc in locations:
        if loc and loc not in existing.usage_locations:
            existing.usage_locations.append(loc)
    for cid in claim_ids:
        if cid and cid not in existing.evidence_claim_ids:
            existing.evidence_claim_ids.append(cid)


def build_bibliography(ctx: dict) -> list[BibliographyEntry]:
    """Collect and deduplicate bibliographic entries from project context."""
    sources = list(ctx.get("sources") or [])
    claims = list(ctx.get("evidence_claims") or [])
    regulatory = list(ctx.get("regulatory_bases") or [])

    # source_id → claim ids + usage
    claims_by_source: dict[str, list[str]] = {}
    locations_by_source: dict[str, list[str]] = {}
    for c in claims:
        cid = str(c.get("id") or "")
        sids = list(c.get("source_ids") or [])
        if not sids and c.get("source_id"):
            sids = [c.get("source_id")]
        field_name = str(c.get("field_name") or c.get("evidence_type") or "evidence")
        for sid in sids:
            key = str(sid)
            claims_by_source.setdefault(key, [])
            if cid and cid not in claims_by_source[key]:
                claims_by_source[key].append(cid)
            locations_by_source.setdefault(key, [])
            loc = f"evidence:{field_name}"
            if loc not in locations_by_source[key]:
                locations_by_source[key].append(loc)

    candidates: list[dict[str, Any]] = []

    for s in sources:
        sid = str(s.get("id")) if s.get("id") is not None else None
        title = s.get("title")
        if not sid and not title:
            continue
        cite = s.get("citation") or _citation_from_source(s)
        if not cite and not title:
            continue
        candidates.append(
            {
                "source_id": sid,
                "citation": str(cite),
                "title": str(title) if title else None,
                "authors": s.get("authors"),
                "year": s.get("year"),
                "url": s.get("url"),
                "document_identifier": s.get("document_identifier") or s.get("file_id"),
                "usage_locations": list(locations_by_source.get(sid or "", [])),
                "evidence_claim_ids": list(claims_by_source.get(sid or "", [])),
            }
        )

    for rb in regulatory:
        sid = str(rb["source_id"]) if rb.get("source_id") is not None else None
        title = rb.get("title")
        doc_id = rb.get("document_identifier")
        if not sid and not title and not doc_id:
            continue
        cite = _citation_from_regulatory(rb)
        candidates.append(
            {
                "source_id": sid,
                "citation": cite,
                "title": str(title) if title else None,
                "authors": rb.get("authors"),
                "year": (str(rb["effective_date"])[:4] if rb.get("effective_date") else None),
                "url": rb.get("url"),
                "document_identifier": doc_id,
                "usage_locations": ["regulatory_basis"],
                "evidence_claim_ids": [],
            }
        )

    # Deduplicate: source_id → document_identifier → normalized citation
    by_source: dict[str, BibliographyEntry] = {}
    by_doc: dict[str, BibliographyEntry] = {}
    by_cite: dict[str, BibliographyEntry] = {}
    ordered: list[BibliographyEntry] = []

    for c in candidates:
        sid = c.get("source_id")
        doc = c.get("document_identifier")
        ncite = _norm_cite(c.get("citation"))
        locs = list(c.get("usage_locations") or [])
        claims_ids = list(c.get("evidence_claim_ids") or [])

        existing: BibliographyEntry | None = None
        if sid and sid in by_source:
            existing = by_source[sid]
        elif doc and str(doc) in by_doc:
            existing = by_doc[str(doc)]
        elif ncite and ncite in by_cite:
            existing = by_cite[ncite]

        if existing is not None:
            _merge_entry(existing, locations=locs, claim_ids=claims_ids)
            if sid and sid not in by_source:
                by_source[sid] = existing
            if doc and str(doc) not in by_doc:
                by_doc[str(doc)] = existing
            if ncite and ncite not in by_cite:
                by_cite[ncite] = existing
            continue

        entry = BibliographyEntry(
            reference_id="",  # assigned after sort
            source_id=sid,
            citation=str(c.get("citation") or ""),
            title=c.get("title"),
            authors=c.get("authors"),
            year=c.get("year"),
            url=c.get("url"),
            document_identifier=str(doc) if doc else None,
            usage_locations=locs,
            evidence_claim_ids=claims_ids,
        )
        ordered.append(entry)
        if sid:
            by_source[sid] = entry
        if doc:
            by_doc[str(doc)] = entry
        if ncite:
            by_cite[ncite] = entry

    # Deterministic order: stable sort by (year, title, source_id)
    ordered.sort(
        key=lambda e: (
            str(e.year) if e.year is not None else "",
            str(e.title or ""),
            str(e.source_id or ""),
        )
    )
    for i, e in enumerate(ordered, start=1):
        e.reference_id = f"REF-{i:03d}"
    return ordered


def bibliography_to_protocol_references(entries: list[BibliographyEntry]) -> list[dict]:
    """Serialize bibliography for ProtocolDraft literature-type references."""
    out: list[dict] = []
    for e in entries:
        out.append(
            {
                "type": "literature",
                "reference_id": e.reference_id,
                "source_id": e.source_id,
                "citation": e.citation,
                "title": e.title,
                "authors": e.authors,
                "year": e.year,
                "url": e.url,
                "document_identifier": e.document_identifier,
                "usage_locations": list(e.usage_locations),
                "evidence_claim_ids": list(e.evidence_claim_ids),
            }
        )
    return out


def find_orphan_source_ids(used_source_ids: list | set, bibliography: list[BibliographyEntry]) -> list:
    """Source IDs referenced in content but absent from bibliography."""
    present = {e.source_id for e in bibliography if e.source_id}
    orphans: list[str] = []
    for sid in used_source_ids:
        key = str(sid)
        if key and key not in present and key not in orphans:
            orphans.append(key)
    return orphans


def find_duplicate_reference_ids(entries: list[BibliographyEntry]) -> list:
    """Return reference_ids that appear more than once."""
    seen: dict[str, int] = {}
    for e in entries:
        rid = e.reference_id
        if not rid:
            continue
        seen[rid] = seen.get(rid, 0) + 1
    return sorted(rid for rid, n in seen.items() if n > 1)
