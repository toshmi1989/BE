# Phase 12B.1 — Protocol Content Generation: Core Sections

**Version:** 0.13.1  
**Extends:** Phase 12A.2 Content Foundation  
**Medical rules added:** ZERO  
**Invented medical defaults:** ZERO

## 1. Scope

Controlled generation for **core sections only** (identity, admin, product/reference, objectives, design, treatment/periods/washout, sampling summary).

Not in scope: full protocol rewrite, sections 5–18 mass generation, AI-required narrative, automatic reference/design/N decisions, template-as-truth.

## 2. Sections generated

Section codes come from existing `SECTION_TREE` / `CORE_12B1_SECTION_CODES`, including:

- **1.x** — identity / administrative core  
- **2.1–2.6, 2.9–2.12** — product, reference, subjects, washout rationale (as mapped)  
- **3** — objectives  
- **4.1–4.6, 4.8–4.9, 4.4.x** — design, treatment, sampling summary  

Exact titles/numbers are not invented; missing codes are skipped.

## 3. Canonical dependencies

| Content area | Canonical / approved sources |
|--------------|------------------------------|
| Identity | Study (protocol number, title, version), sponsor, orgs |
| Product | Product fields (semantic: trade name, INN, manufacturer, form, dose, …) |
| Reference | Approved ReferenceProduct / ExpertDecision only — no auto-select |
| Design | Approved design; DisplayValueRegistry for human-readable text |
| Objectives | Canonical objective fields + deterministic templates when complete |
| Treatment / washout / food | Design, washout, food — no invented kcal/water/meal details |
| Sampling | Canonical SamplingPlan; ordered points; same list everywhere |
| Subject N | SubjectPlan / sample_size consistency snapshot only |

## 4. Content resolver flow

```
Canonical Field
    → Content Matrix entry
    → ContentResolver
    → ResolvedContent (RESOLVED | PROPOSED | UNRESOLVED | BLOCKED)
    → ContentRenderer / section generators
    → ProtocolDraft block
    → Protocol QA (CONTENT.*)
    → targeted DOCX (optional)
```

API: `POST /api/projects/{id}/content/generate-core`

## 5. Text templates

Deterministic templates in `content_core_templates.py` (e.g. BE objective).  
Templates require all required fields; otherwise KnowledgeGap / unresolved — never partial invention.  
Enums go through `DisplayValueRegistry` (no raw `CROSSOVER_2X2` / bare `FASTING` in final text).

## 6. Provenance

Each generated block carries section/block codes, content type, canonical source, evidence/decision refs, status, gaps, validation issues.  
Evidence-derived content must keep source/claim/confidence/verification status; PROPOSED evidence is not VERIFIED.

## 7. ExpertDecision behavior

| Status | Render |
|--------|--------|
| APPROVED | Eligible for final |
| PROPOSED | Draft/preview only |
| REJECTED / SUPERSEDED | Not rendered as final |
| Ambiguous multiples | KnowledgeGap |

## 8. KnowledgeGap behavior

Missing sponsor, reference decision, design, washout, sampling approval → structured gaps/blockers.  
Never silent `N/A`, empty invent, or copy from previous protocol / template text.

## 9. DOCX rendering

```
ProtocolDraft → selected sections → existing DOCX renderer → output
```

- `DocxBuildRequest.only_sections` limits section-body replace  
- Tables filled only if referenced by selected section blocks  
- Synopsis/cover fills skipped on narrow targeted runs  
- No global find/replace; no positional cell invent mapping for product fields  
- Static verified blocks outside selection remain unchanged  

## 10. QA

`content_generation_qa` checks include:

- `CONTENT.CANONICAL_MISSING`  
- `CONTENT.UNRESOLVED_RENDER`  
- `CONTENT.PROPOSED_RENDERED_AS_FINAL`  
- `CONTENT.REJECTED_DECISION_USED` / `CONTENT.SUPERSEDED_DECISION_USED`  
- `CONTENT.LEGACY_VALUE` / `CONTENT.CANONICAL_MISMATCH`  
- `CONTENT.RAW_ENUM_LEAK` / `CONTENT.PLACEHOLDER_UNRESOLVED`  

Cross-section consistency: sponsor, product, reference, dose, form, design, food, N, washout, sampling vs canonical.

## 11. Limitations

- Core sections only; 5–18 not regenerated here  
- NarrativeRenderer interface may exist; implementation is deterministic (LLM optional, not required)  
- Previous Protocol import not fully implemented; QA detects legacy N when hinted  
- FINAL readiness still depends on full project completeness outside 12B.1  

## 12. Future sections

Phase 12B.2+ should extend the same pipeline to remaining sections without template-as-truth or medical invention.
