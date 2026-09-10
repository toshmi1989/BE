"""Real web search provider — Phase 15.3.

Uses DuckDuckGo HTML results by default (no API key). Injectable transport for tests.
Domain logic depends only on ResearchProvider ABC.
"""

from __future__ import annotations

import re
from typing import Any, Callable
from urllib.parse import quote_plus, unquote

from app.domain.research_http import ResearchHttpError, http_get, research_http_settings
from app.domain.research_provider import ProviderHit, ResearchProvider
from app.domain.research_sanitize import sanitize_metadata, sanitize_snippet, sanitize_title, sanitize_url
from app.domain.research_search_result import (
    ResearchSearchResult,
    infer_priority_class,
)


SearchFn = Callable[[str], list[dict[str, Any]]]


_RESULT_RE = re.compile(
    r'class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.I | re.S,
)
# The snippet sits in its own tag after the title; a single combined pattern with an
# optional trailing group matches empty and silently loses every snippet.
_SNIPPET_RE = re.compile(
    r'class="result__snippet"[^>]*>(?P<snippet>.*?)</(?:a|td|div)>',
    re.I | re.S,
)
_UDDG_RE = re.compile(r"[?&]uddg=([^&]+)")


def _unwrap_ddg_url(href: str) -> str:
    m = _UDDG_RE.search(href)
    if m:
        return unquote(m.group(1))
    return href


def parse_duckduckgo_html(html_text: str) -> list[dict[str, Any]]:
    text = html_text or ""
    titles = list(_RESULT_RE.finditer(text))
    snippets = list(_SNIPPET_RE.finditer(text))
    results: list[dict[str, Any]] = []
    for idx, m in enumerate(titles):
        block_end = titles[idx + 1].start() if idx + 1 < len(titles) else len(text)
        raw_snippet = next(
            (s.group("snippet") for s in snippets if m.end() <= s.start() < block_end),
            "",
        )
        href = _unwrap_ddg_url(m.group("href"))
        title = sanitize_title(m.group("title"))
        snippet = sanitize_snippet(raw_snippet)
        try:
            url = sanitize_url(href)
        except ValueError:
            continue
        if not url:
            continue
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def default_duckduckgo_search(query: str, *, client=None) -> list[dict[str, Any]]:
    cfg = research_http_settings()
    if not cfg["enabled"]:
        raise ResearchHttpError("Real web research disabled", kind="DISABLED")
    q = quote_plus(query.strip())
    url = f"https://html.duckduckgo.com/html/?q={q}"
    r = http_get(url, client=client)
    return parse_duckduckgo_html(r.text)[: cfg["max_results"]]


def classify_source_type(url: str, title: str, snippet: str) -> str:
    blob = f"{url} {title} {snippet}".lower()
    if any(x in blob for x in ("smpc", "spc", "prescribing information", "инструкц", "листок-вкладыш")):
        return "SMPC"
    if any(x in blob for x in ("ema.europa", "fda.gov", "guideline", "guidance")):
        return "GUIDELINE"
    if "pubmed" in blob or "doi.org" in blob or "journal" in blob:
        return "PUBLICATION"
    if "clinicaltrials" in blob or "bioequivalence" in blob:
        return "CLINICAL_STUDY"
    if "review" in blob:
        return "REVIEW"
    return "UNKNOWN"


class RealWebResearchProvider(ResearchProvider):
    """REAL_WEB_PROVIDER — external search. Never auto-verifies."""

    kind = "WEB"

    def __init__(
        self,
        *,
        search_fn: SearchFn | None = None,
        client=None,
    ) -> None:
        self._search_fn = search_fn
        self._client = client
        self.last_error: str | None = None
        self.last_status: str = "OK"
        self.last_results: list[ResearchSearchResult] = []

    def search(self, query: str, *, query_type: str | None = None) -> list[ProviderHit]:
        self.last_error = None
        self.last_status = "OK"
        self.last_results = []
        try:
            if self._search_fn:
                raw = self._search_fn(query)
            else:
                raw = default_duckduckgo_search(query, client=self._client)
        except ResearchHttpError as exc:
            self.last_error = f"{exc.kind}: {exc}"
            self.last_status = "RESEARCH_FAILED"
            raise
        except Exception as exc:  # noqa: BLE001 — surface as research failure
            self.last_error = str(exc)
            self.last_status = "RESEARCH_FAILED"
            raise ResearchHttpError(str(exc), kind="HTTP_ERROR") from exc

        hits: list[ProviderHit] = []
        for item in raw:
            title = sanitize_title(item.get("title"))
            try:
                url = sanitize_url(item.get("url"))
            except ValueError:
                continue
            if not url:
                continue
            snippet = sanitize_snippet(item.get("snippet"))
            stype = item.get("source_type") or classify_source_type(url, title, snippet)
            if stype not in {
                "REGULATORY", "SMPC", "PRODUCT_LABEL", "PUBLICATION", "CLINICAL_STUDY",
                "PROTOCOL", "DATABASE", "GUIDELINE", "REVIEW", "OTHER", "UNKNOWN",
            }:
                stype = "UNKNOWN"
            # Map to ProviderHit source_type vocabulary (slightly smaller set)
            ph_type = {
                "SMPC": "SMPC",
                "GUIDELINE": "REGULATORY",
                "REGULATORY": "REGULATORY",
                "PRODUCT_LABEL": "SMPC",
                "PUBLICATION": "PUBLICATION",
                "CLINICAL_STUDY": "CLINICAL_STUDY",
                "REVIEW": "REVIEW",
                "DATABASE": "DATABASE",
                "PROTOCOL": "PROTOCOL",
            }.get(stype, "OTHER")
            meta = sanitize_metadata(item.get("metadata") or {})
            meta["priority_class"] = infer_priority_class(source_type=stype, url=url, title=title)
            meta["query_type"] = query_type
            meta["real_source_type"] = stype
            rsr = ResearchSearchResult(
                title=title,
                url=url,
                provider=self.kind,
                snippet=snippet,
                source_type=stype,
                publication_date=item.get("publication_date"),
                authors=item.get("authors"),
                identifier=item.get("identifier"),
                raw_metadata=meta,
                priority_class=meta["priority_class"],
            )
            self.last_results.append(rsr)
            hits.append(
                ProviderHit(
                    title=title,
                    locator=url,
                    source_type=ph_type,
                    text=snippet or "",
                    author=item.get("authors"),
                    publication_date=item.get("publication_date"),
                    identifier=item.get("identifier"),
                    metadata=meta,
                )
            )
        if not hits:
            self.last_status = "NO_USABLE_EVIDENCE"
        return hits

    def fetch(self, hit: ProviderHit) -> ProviderHit:
        """Fetch is handled by research_fetch module; keep hit as-is here."""
        return hit

    def to_search_results(self) -> list[ResearchSearchResult]:
        return list(self.last_results)
