"""Document / source content search — Postgres FTS when available, LIKE fallback."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class SearchHit:
    source_id: str | None
    document_id: str
    page: int
    chunk_id: str
    score: float
    snippet: str

    def to_dict(self) -> dict:
        return asdict(self)


def _snippet(text: str, query: str, radius: int = 80) -> str:
    low = text.lower()
    q = query.lower().strip().strip('"')
    idx = low.find(q)
    if idx < 0:
        # try first token
        token = q.split()[0] if q.split() else q
        idx = low.find(token)
    if idx < 0:
        return text[: radius * 2]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(q) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix


def score_match(text: str, query: str, *, phrase: bool) -> float:
    if not text or not query:
        return 0.0
    low = text.lower()
    q = query.strip()
    if phrase or (q.startswith('"') and q.endswith('"')):
        phrase_q = q.strip('"').lower()
        return 1.0 if phrase_q in low else 0.0
    tokens = [t for t in q.lower().split() if t]
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in low)
    return hits / len(tokens)


def search_chunks(
    rows: list[dict],
    query: str,
    *,
    phrase: bool = False,
    source_type: str | None = None,
    limit: int = 50,
) -> list[SearchHit]:
    """In-memory / portable search used for SQLite tests and as Postgres fallback."""
    hits: list[SearchHit] = []
    for row in rows:
        if source_type and row.get("source_type") and row["source_type"] != source_type:
            continue
        text = row.get("text") or ""
        sc = score_match(text, query, phrase=phrase)
        if sc <= 0:
            continue
        hits.append(
            SearchHit(
                source_id=row.get("source_id"),
                document_id=str(row["document_id"]),
                page=int(row["page_number"]),
                chunk_id=str(row["chunk_id"]),
                score=round(sc, 4),
                snippet=_snippet(text, query),
            )
        )
    hits.sort(key=lambda h: (-h.score, h.page, h.chunk_id))
    return hits[:limit]
