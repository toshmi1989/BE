"""Deterministic MockResearchProvider — Phase 15.2.

Never fabricates golden real-world results unless fixtures are explicitly loaded.
"""

from __future__ import annotations

from app.domain.research_provider import ProviderHit, ResearchProvider


# Deterministic fixtures for UPDCB-style research (mock only)
MOCK_HALF_LIFE_HITS: list[ProviderHit] = [
    ProviderHit(
        title="Mock PK Review — upadacitinib half-life A",
        locator="mock://pk/upadacitinib/half-life-a",
        source_type="PUBLICATION",
        text=(
            "In healthy volunteers after a single 15 mg oral dose of upadacitinib, "
            "the mean terminal half-life (t1/2) was 8.7 hours."
        ),
        author="Mock Author A",
        journal="Mock J Clin Pharmacol",
        publication_date="2020",
        identifier="DOI:10.MOCK/hl-a",
        metadata={"parameter": "t_half", "value": 8.7, "unit": "hours", "statistic": "MEAN"},
    ),
    ProviderHit(
        title="Mock PK Review — upadacitinib half-life B",
        locator="mock://pk/upadacitinib/half-life-b",
        source_type="PUBLICATION",
        text=(
            "Terminal half-life of upadacitinib was reported as 12.1 h "
            "(healthy volunteers, single dose 15 mg)."
        ),
        author="Mock Author B",
        journal="Mock Eur J Pharm",
        publication_date="2021",
        identifier="DOI:10.MOCK/hl-b",
        metadata={"parameter": "t_half", "value": 12.1, "unit": "hours", "statistic": "MEAN"},
    ),
    ProviderHit(
        title="Mock SmPC-like excerpt — half-life range",
        locator="mock://smpc/upadacitinib/half-life-range",
        source_type="SMPC",
        text="The terminal half-life ranges from 7 to 11 hours in healthy subjects.",
        identifier="MOCK-SMPC-HL",
        metadata={
            "parameter": "t_half",
            "statistic": "RANGE",
            "range_low": 7,
            "range_high": 11,
            "unit": "hours",
        },
    ),
]

MOCK_TMAX_HITS: list[ProviderHit] = [
    ProviderHit(
        title="Mock Tmax median",
        locator="mock://pk/upadacitinib/tmax-median",
        source_type="PUBLICATION",
        text="Median Tmax was 2.0 hours (range 1–4 h) after 15 mg extended-release tablet.",
        identifier="DOI:10.MOCK/tmax-1",
        metadata={
            "parameter": "Tmax",
            "value": 2.0,
            "unit": "hours",
            "statistic": "MEDIAN",
            "range_low": 1,
            "range_high": 4,
        },
    ),
]

MOCK_CV_HITS: list[ProviderHit] = [
    ProviderHit(
        title="Mock BE study CVintra Cmax",
        locator="mock://be/upadacitinib/cvintra-cmax",
        source_type="CLINICAL_STUDY",
        text=(
            "Within-subject CV for Cmax was 28% in a 2x2 crossover BE study "
            "in healthy volunteers (15 mg)."
        ),
        identifier="DOI:10.MOCK/cv-cmax",
        metadata={
            "parameter": "CVintra",
            "CV_value": 28,
            "CV_unit": "%",
            "PK_parameter": "Cmax",
            "variability_type": "WITHIN_SUBJECT",
        },
    ),
    ProviderHit(
        title="Mock between-subject CV (must not be CVintra)",
        locator="mock://be/upadacitinib/cv-between",
        source_type="PUBLICATION",
        text="Between-subject CV for AUC was 45%.",
        identifier="DOI:10.MOCK/cv-between",
        metadata={
            "parameter": "CV",
            "CV_value": 45,
            "CV_unit": "%",
            "PK_parameter": "AUC",
            "variability_type": "BETWEEN_SUBJECT",
        },
    ),
]

MOCK_MEAL_HITS: list[ProviderHit] = [
    ProviderHit(
        title="Mock food effect — qualitative only",
        locator="mock://food/high-calorie",
        source_type="REGULATORY",
        text="Administration with a high-calorie breakfast is recommended for the fed arm.",
        identifier="MOCK-FOOD-1",
        metadata={"meal_description": "high-calorie breakfast"},
    ),
]

MOCK_ANALOGUE_HITS: list[ProviderHit] = [
    ProviderHit(
        title="Mock analogue BE study",
        locator="mock://analogue/be-study-1",
        source_type="CLINICAL_STUDY",
        text=(
            "Bioequivalence study of upadacitinib 30 mg tablets vs reference in "
            "healthy volunteers, 2x2 crossover, fasting."
        ),
        identifier="DOI:10.MOCK/analogue-1",
        metadata={
            "active_substance": "upadacitinib",
            "dose": "30 mg",
            "dosage_form": "tablet",
            "population": "healthy volunteers",
            "design": "2x2 crossover",
            "condition": "fasting",
        },
    ),
]


class MockResearchProvider(ResearchProvider):
    kind = "MOCK"

    def __init__(self, fixtures: dict[str, list[ProviderHit]] | None = None) -> None:
        self.fixtures = fixtures or {
            "half-life": MOCK_HALF_LIFE_HITS,
            "t1/2": MOCK_HALF_LIFE_HITS,
            "tmax": MOCK_TMAX_HITS,
            "within-subject": MOCK_CV_HITS,
            "cvintra": MOCK_CV_HITS,
            "variability": MOCK_CV_HITS,
            "calorie": MOCK_MEAL_HITS,
            "breakfast": MOCK_MEAL_HITS,
            "meal": MOCK_MEAL_HITS,
            "analogue": MOCK_ANALOGUE_HITS,
            "bioequivalence": MOCK_ANALOGUE_HITS,
        }

    def search(self, query: str, *, query_type: str | None = None) -> list[ProviderHit]:
        q = (query or "").lower()
        hits: list[ProviderHit] = []
        seen: set[str] = set()
        for key, group in self.fixtures.items():
            if key in q or (query_type == "PK" and key in {"half-life", "tmax", "t1/2"}):
                for h in group:
                    if h.locator not in seen:
                        hits.append(h)
                        seen.add(h.locator)
        if query_type == "CV":
            for h in MOCK_CV_HITS:
                if h.locator not in seen:
                    hits.append(h)
                    seen.add(h.locator)
        if query_type == "FOOD":
            for h in MOCK_MEAL_HITS:
                if h.locator not in seen:
                    hits.append(h)
                    seen.add(h.locator)
        if query_type == "ANALOGUE":
            for h in MOCK_ANALOGUE_HITS:
                if h.locator not in seen:
                    hits.append(h)
                    seen.add(h.locator)
        return hits

    def fetch(self, hit: ProviderHit) -> ProviderHit:
        return hit
