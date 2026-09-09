"""Local document + internal source research providers — Phase 15.3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.domain.research_provider import ProviderHit, ResearchProvider
from app.domain.research_sanitize import sanitize_snippet, sanitize_title


class LocalDocumentProvider(ResearchProvider):
    """Search filenames/text under document_storage_root. No network."""

    kind = "LOCAL_DOCUMENTS"

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or get_settings().document_storage_root)

    def search(self, query: str, *, query_type: str | None = None) -> list[ProviderHit]:
        if not self.root.exists():
            return []
        terms = [t.lower() for t in query.split() if len(t) > 2][:8]
        hits: list[ProviderHit] = []
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".exe", ".bat", ".cmd", ".ps1", ".js", ".dll"}:
                continue
            name = path.name.lower()
            if terms and not any(t in name for t in terms):
                # optionally peek small text files
                if path.suffix.lower() not in {".txt", ".md"}:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")[:4000].lower()
                except OSError:
                    continue
                if not any(t in text for t in terms):
                    continue
            else:
                text = ""
            hits.append(
                ProviderHit(
                    title=sanitize_title(path.name),
                    locator=f"local://{path.as_posix()}",
                    source_type="OTHER",
                    text=sanitize_snippet(text[:500]),
                    metadata={"provider": "LOCAL_DOCUMENTS", "path_name": path.name},
                )
            )
            if len(hits) >= 10:
                break
        return hits


class InternalSourceProvider(ResearchProvider):
    """Search already-registered research sources / fixtures in memory."""

    kind = "INTERNAL_LIBRARY"

    def __init__(self, catalog: list[dict[str, Any]] | None = None) -> None:
        self.catalog = list(catalog or [])

    def add(self, item: dict[str, Any]) -> None:
        self.catalog.append(item)

    def search(self, query: str, *, query_type: str | None = None) -> list[ProviderHit]:
        q = query.lower()
        hits: list[ProviderHit] = []
        for item in self.catalog:
            blob = " ".join(
                str(item.get(k) or "")
                for k in ("title", "text", "active_substance", "locator", "tags")
            ).lower()
            if not any(tok in blob for tok in q.split() if len(tok) > 2):
                continue
            hits.append(
                ProviderHit(
                    title=sanitize_title(item.get("title") or "Internal source"),
                    locator=str(item.get("locator") or item.get("id") or "internal://unknown"),
                    source_type=item.get("source_type") or "OTHER",
                    text=sanitize_snippet(item.get("text") or ""),
                    identifier=item.get("identifier"),
                    metadata={"provider": "INTERNAL_LIBRARY", **(item.get("metadata") or {})},
                )
            )
        return hits
