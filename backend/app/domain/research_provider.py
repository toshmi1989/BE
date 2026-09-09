"""Research provider abstraction — Phase 15.2. Provider-independent."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderHit:
    title: str
    locator: str
    source_type: str = "OTHER"
    text: str = ""
    author: str | None = None
    journal: str | None = None
    publication_date: str | None = None
    identifier: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchProvider(ABC):
    kind: str = "OTHER"

    @abstractmethod
    def search(self, query: str, *, query_type: str | None = None) -> list[ProviderHit]:
        ...

    def fetch(self, hit: ProviderHit) -> ProviderHit:
        """Fetch full content if needed. Default: return hit unchanged."""
        return hit

    def extract(self, hit: ProviderHit) -> list[dict[str, Any]]:
        """Optional provider-side extract hints. Default: empty (engine extracts)."""
        return []


class NullResearchProvider(ResearchProvider):
    """No external results — AI-off / offline safe."""

    kind = "LOCAL_DOCUMENTS"

    def search(self, query: str, *, query_type: str | None = None) -> list[ProviderHit]:
        return []
