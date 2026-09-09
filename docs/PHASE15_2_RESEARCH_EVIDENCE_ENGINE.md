# Phase 15.2 — Research & Analogue Evidence Engine

**Version:** 0.18.0  
**Extends:** Phase 15.0 / 15.1 Decision Center  
**Does not start:** Phase 16, Sample Size engine, Statistics engine

> Phase 15.3 adds real web search: see `docs/PHASE15_3_REAL_RESEARCH_PROVIDER.md`

## 1. ResearchTask architecture

```
KnowledgeGap
  → ResearchTask (study-scoped)
  → ResearchQuery (auditable)
  → ResearchProvider.search
  → SourceResult
  → Source / SourceVersion registration
  → ResearchClaim (PROPOSED)
  → Applicability + Usability
  → Expert VERIFY / REJECT / REQUEST_MORE_INFORMATION
  → Decision bridge (context only)
  → Dependency-aware decision recompute
```

Domain models live in `research_evidence_models.py` (Decision Center research lane).  
Existing ORM `ResearchTask` (Phase 5) remains for project research cases — not duplicated conceptually; Phase 15.2 bridges **gap codes** from Decision Center.

## 2. ResearchQuery

Exact `query_text` stored. Types: IDENTITY / PK / CV / DESIGN / FOOD / ANALOGUE / REGULATORY / SAFETY / OTHER.  
Deterministic templates in `research_query_gen.py`. AI may propose alternatives (`ai_proposed=True`) only.

## 3. Providers

`ResearchProvider` ABC: `search` / `fetch` / `extract`.  
Kinds: WEB, LOCAL_DOCUMENTS, INTERNAL_LIBRARY, REGULATORY_SOURCE, PUBLICATION, MOCK.  
`MockResearchProvider` for fixtures; `NullResearchProvider` for empty offline results.

## 4–5. Sources

`SourceResult` → `RegisteredSource` (locator, hash, version_id). Deduplicate by locator / DOI / hash.  
Version bump → claims linked to old version get `REQUIRES_REVIEW` / STALE reason.

## 6–11. Claims & numeric evidence

Always **PROPOSED** on extract. Methods: DETERMINISTIC / AI / MANUAL.  
`EvidenceMeasurement` preserves parameter, value, unit, population, dose, condition, **statistic_type** (MEAN/MEDIAN/RANGE/…).  
Ranges are **not** collapsed to a single number.  
`CVintraEvidence` requires PK_parameter + variability_type (WITHIN vs BETWEEN).  
Meal: qualitative text allowed; kcal/fat **not invented**.

## 12–13. Analogues & applicability

Match dimensions: MATCH / PARTIAL / MISMATCH / UNKNOWN.  
Applicability never DIRECT from substance similarity alone.  
Verification ⊥ applicability ⊥ usability.

## 14. Usability

`USABLE_FOR_DECISION` / `NOT_USABLE_FOR_DECISION` / `REQUIRES_REVIEW`.  
LOW / NOT_APPLICABLE cannot unblock critical decisions.

## 15. Conflicts

Material numeric differences → OPEN conflict. **No averaging.** No auto-authority pick.

## 16. AI-off

Full workflow works with Mock/Null providers and deterministic extraction. AI cannot verify, finalize applicability, resolve conflicts, approve decisions, or mutate Study.

## 17. MockResearchProvider

Deterministic half-life (8.7 / 12.1 / range 7–11), Tmax median+range, CVintra Cmax, between-subject CV, qualitative meal, analogue BE study.

## 18. Decision integration

`apply_verified_research_to_context` sets `half_life` / `tmax` / `cvintra` only when VERIFIED + usable + applicable.  
`recompute_affected_decisions` uses Phase 15.1 dependency registry (e.g. t½ → WASHOUT+SAMPLING, not FOOD).  
Does **not** approve decisions.

## 19. Limitations

- No live web search in default path  
- Golden fixture uses **mocked** research results only  
- Open conflicts block task COMPLETE  
- Research does not write Study ORM  

## API (`/api/research-center`)

- `GET/POST /studies/{id}/research-tasks`  
- `GET /research-tasks/{id}`  
- `POST /research-tasks/{id}/run`  
- `GET .../results|evidence|conflicts`  
- `POST /evidence/{id}/verify|reject|request-review`  
- `GET/POST .../applicability`  
- `GET /studies/{id}/coverage`  
- `POST /studies/{id}/apply-to-decisions`  
- `POST /fixtures/updcb-real/bootstrap`
