# Phase 13.3 — Decision 85 Regulatory Claim Verification

**Version:** 0.14.3  
**Package status:** `PARTIAL` (Decision 85 ingested; FDA / EMA / SmPC still missing)  
**Medical rules added:** **ZERO**  
**Auto-verify:** **NO** (first batch only with explicit `reviewer`)  
**Study / Design / Sampling / PK / Food / ReferenceProduct mutation:** **NO**

---

## Purpose

First real regulatory verification cycle against user-supplied Decision 85:

```text
REAL SOURCE → EXACT CLAUSE → EVIDENCE CLAIM → REGULATORY BASIS
  → REVIEW → VERIFIED CLAIM → KNOWLEDGE RULE CANDIDATE (PROPOSED)
```

Claim verification ≠ rule verification ≠ Study mutation.

## Source

| Field | Value |
|-------|--------|
| File | `fixtures/regulatory/eec/16sr0085.doc` |
| Format | MHTML / MIME web-archive (not a native Word binary) |
| Source ID | `SRC-DECISION85` |
| Class | `EEC_REGULATORY` |
| Document identifier | `85` |
| Authority | Евразийская экономическая комиссия |
| Title | Решение Совета ЕЭК от 03.11.2016 №85 … |
| Page provenance | `UNAVAILABLE_WEB_ARCHIVE` — use section + point + chunk |

Domains: `app.domain.decision85_mhtml`, `decision85_claims`, `decision85_pipeline`.

## Amendments (SOURCE_EMBEDDED)

Extracted only when present in the source header (не выдуманы):

| Date | Number | Status |
|------|--------|--------|
| 2020-09-04 | 67 | `SOURCE_EMBEDDED` |
| 2023-02-15 | 22 | `SOURCE_EMBEDDED` |
| 2024-04-12 | 30 | `SOURCE_EMBEDDED` |

`amendment_metadata_certainty = SOURCE_EMBEDDED` when all three are found.

## Claim table

`PAGE` is always unavailable for this web-archive (do not invent). Excerpt summaries are short; full text is stored on the claim.

| CLAIM | SOURCE | POINT | PAGE | EXCERPT summary | STATUS (default / first batch) | RULE |
|-------|--------|------:|------|-----------------|--------------------------------|------|
| REF-01 | SRC-DECISION85 | 18 | UNAVAILABLE | Reference selection sequence | REVIEW_REQUIRED → **VERIFIED** | REF-01 candidate |
| DESIGN-01 | SRC-DECISION85 | 15 | UNAVAILABLE | Randomized 2×2 crossover | REVIEW_REQUIRED | DESIGN-01 |
| DESIGN-02 | SRC-DECISION85 | 16 | UNAVAILABLE | Replicate for high variability | REVIEW_REQUIRED | DESIGN-02 |
| DESIGN-04 | SRC-DECISION85 | 16 | UNAVAILABLE | Parallel for long t½ | REVIEW_REQUIRED | DESIGN-04/05 |
| WASHOUT-15 | SRC-DECISION85 | 15 | UNAVAILABLE | Washout ~5 half-lives («обычно достаточно») | REVIEW_REQUIRED | WASH-01 soft gap |
| FOOD-01 | SRC-DECISION85 | 44 | UNAVAILABLE | Fasting default / SmPC | REVIEW_REQUIRED → **VERIFIED** | FOOD-01 |
| FOOD-02 | SRC-DECISION85 | 46 | UNAVAILABLE | 800–1000 kcal, ~50% fat | REVIEW_REQUIRED → **VERIFIED** | FOOD-02 |
| PK-01 | SRC-DECISION85 | 47 | UNAVAILABLE | AUC(0-t), Cmax, AUC(0-∞) | REVIEW_REQUIRED → **VERIFIED** | PK-01 |
| PK-02 | SRC-DECISION85 | 47 | UNAVAILABLE | AUC(0-72h), kel, t½ | REVIEW_REQUIRED → **VERIFIED** | PK-02 |
| SAMPLING-01 | SRC-DECISION85 | 38 | UNAVAILABLE | Dense around tmax; Cmax not first | REVIEW_REQUIRED | — |
| SAMPLING-AUC | SRC-DECISION85 | 38 | UNAVAILABLE | ≥80% AUC coverage | REVIEW_REQUIRED → **VERIFIED** | — |
| SAMPLING-TERMINAL | SRC-DECISION85 | 38 | UNAVAILABLE | 3–4 terminal samples | REVIEW_REQUIRED → **VERIFIED** | — |
| SAMPLING-02 | SRC-DECISION85 | 38 | UNAVAILABLE | AUC(0-72h) alternative | REVIEW_REQUIRED | — |
| SAMPLING-03 | SRC-DECISION85 | 41 | UNAVAILABLE | Endogenous background | REVIEW_REQUIRED | — |
| ANALYTE-01 | SRC-DECISION85 | 50 | UNAVAILABLE | Parent compound general | REVIEW_REQUIRED → **VERIFIED** | ANALYTE-01 |
| ANALYTE-02 | SRC-DECISION85 | 51 | UNAVAILABLE | Inactive prodrug | REVIEW_REQUIRED | — |
| ANALYTE-03 | SRC-DECISION85 | 52 | UNAVAILABLE | Metabolite substitution not recommended | REVIEW_REQUIRED | — |
| STAT-03 | SRC-DECISION85 | 85 | UNAVAILABLE | NTI / high variability | REVIEW_REQUIRED | — |
| STAT-04 | SRC-DECISION85 | 86 | UNAVAILABLE | Stats predefined in protocol | REVIEW_REQUIRED | — |
| STAT-01 | SRC-DECISION85 | 87 | UNAVAILABLE | 90% CI | REVIEW_REQUIRED | STAT-01 |
| STAT-02 | SRC-DECISION85 | 88 | UNAVAILABLE | ANOVA log-transform | REVIEW_REQUIRED | — |

**Expert decision:** none applied to Study. Verified claims may spawn **PROPOSED** rule candidates only.

## First verification batch

Controlled batch (8 claims) when `verify_first_batch=True` **and** `reviewer` is set:

`REF-01`, `FOOD-01`, `FOOD-02`, `PK-01`, `PK-02`, `SAMPLING-AUC`, `SAMPLING-TERMINAL`, `ANALYTE-01`

Typical pipeline result:

| Metric | Value |
|--------|------:|
| Claims | 21 |
| Verified (first batch) | 8 |
| Proposed / remaining | 13 |
| Rule candidates | PROPOSED only |
| Conflicts (interview vs D85) | ≥ 1 (OPEN, not auto-resolved) |
| Amendments | 3 × SOURCE_EMBEDDED |
| `study_mutated` | `False` |

## Verify guard

For Decision 85 `REGULATORY_CLAIM`: page may be missing if **section + paragraph_or_chunk + excerpt** are present. Interview claims cannot become regulatory VERIFIED.

## API

Prefix: `/api/regulatory-evidence`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/decision85/import` | Import MHTML → SourceVersion + claims |
| POST | `/decision85/pipeline` | Optional `verify_first_batch` + `reviewer` |
| GET | `/decision85/claims` | D85 claim list |

## Limitations

- Page numbers are **not** recoverable from this web-archive — provenance is point/section/chunk only
- Package remains **PARTIAL** (FDA / EMA / SmPC / safety protocol still missing)
- Potvin B/C **not** in Decision 85 (`REG.POTVIN.NO_D85_SOURCE`)
- WASH soft wording («обычно достаточно») ≠ hard WASH-01 (`REG.WASH.HARD_THRESHOLD_UNCERTAIN`)
- Interview «3 points before/after Tmax» **not** exact D85 text (`REG.SAMPLING.TMAX_3PLUS3.NOT_IN_D85`)
- Source-derived numbers (800–1000, 50%, 80%, 3–4) are facts on claims — not approved medical defaults
- KnowledgeRule seeds remain **PROPOSED**; medical rules added = **ZERO**

## Tests

`backend/tests/test_phase13_3_decision85_verification.py` — ≥60 tests including exact §22 no-mutation names.

```text
python -m pytest tests/test_phase13_3_decision85_verification.py -q --tb=line
```

See also: `docs/PHASE13_1_REGULATORY_EVIDENCE.md`, `docs/PHASE13_2_REGULATORY_IMPORT.md`, `docs/REGULATORY_EVIDENCE_COVERAGE.md`.
