"""Deterministic ResearchProfile / SearchProfile — no LLM."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class ClientResearchInput:
    requested_product_name: str | None = None
    inn: str | None = None
    dosage: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    requested_subject_count: int | None = None
    country: str | None = None
    regulatory_jurisdiction: str | None = None


@dataclass
class SearchProfile:
    inn: str | None = None
    dosage: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    product_name: str | None = None
    reference_search_terms: list[str] = field(default_factory=list)
    pk_search_terms: list[str] = field(default_factory=list)
    bioequivalence_search_terms: list[str] = field(default_factory=list)
    analyte_search_terms: list[str] = field(default_factory=list)
    cv_search_terms: list[str] = field(default_factory=list)
    food_search_terms: list[str] = field(default_factory=list)
    guideline_search_terms: list[str] = field(default_factory=list)
    version: str = "SEARCH.PROFILE.v1"

    def to_dict(self) -> dict:
        return asdict(self)


def _terms(*parts: str | None, extras: list[str] | None = None) -> list[str]:
    out: list[str] = []
    base = [p.strip() for p in parts if p and str(p).strip()]
    if base:
        joined = " ".join(base)
        out.append(joined)
        out.extend(base)
    for e in extras or []:
        if e and e not in out:
            out.append(e)
    # stable unique
    seen: set[str] = set()
    uniq: list[str] = []
    for t in out:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(t)
    return uniq


def build_search_profile(inp: ClientResearchInput) -> SearchProfile:
    inn = (inp.inn or "").strip() or None
    dosage = (inp.dosage or "").strip() or None
    form = (inp.dosage_form or "").strip() or None
    route = (inp.route or "").strip() or None
    product = (inp.requested_product_name or "").strip() or None
    jurisdiction = (inp.regulatory_jurisdiction or inp.country or "").strip() or None

    return SearchProfile(
        inn=inn,
        dosage=dosage,
        dosage_form=form,
        route=route,
        product_name=product,
        reference_search_terms=_terms(
            inn, dosage, form, extras=["reference product", "оригинальный препарат", "SmPC", "label"]
        ),
        pk_search_terms=_terms(
            inn, dosage, extras=["pharmacokinetics", "Tmax", "half-life", "AUC", "Cmax", "фармакокинетика"]
        ),
        bioequivalence_search_terms=_terms(
            inn,
            dosage,
            form,
            extras=["bioequivalence", "BE study", "биоэквивалентность", "crossover"],
        ),
        analyte_search_terms=_terms(inn, extras=["analyte", "metabolite", "plasma", "аналит"]),
        cv_search_terms=_terms(
            inn, dosage, extras=["CVintra", "within-subject CV", "intra-subject variability", "вариабельность"]
        ),
        food_search_terms=_terms(
            inn, extras=["fed", "fasting", "food effect", "после еды", "натощак", "high-fat meal"]
        ),
        guideline_search_terms=_terms(
            inn,
            form,
            jurisdiction,
            extras=["BE guideline", "EAEU", "EMA", "product-specific guidance"],
        ),
    )
