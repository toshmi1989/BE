# Phase 15.4 — Deterministic Sample Size Engine

**Version:** 0.19.0  
**Does not start:** Phase 16 / full Statistics engine / adaptive sample-size methods / autonomous medical decisions

## 1. Purpose

Transparent, reproducible sample-size calculation with full provenance.

```
VERIFIED EVIDENCE → ELIGIBLE NUMERIC INPUT → SAMPLE SIZE CALCULATION
  → CALCULATION RESULT → EXPERT REVIEW → OPTIONAL CANONICAL PROJECTION
```

`CURRENT_STUDY_FACT` (e.g. Synopsis `randomized_n=56`) is **never** treated as
`calculated_required_n`. Differences surface as `SAMPLE_SIZE_DISCREPANCY`.

## 2. Supported designs

| Design | Status |
|--------|--------|
| `STANDARD_2X2_CROSSOVER` | Fully supported |
| `REPLICATE_CROSSOVER` | `METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW` |
| `ADAPTIVE_DESIGN` | `METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW` |
| `PARALLEL_DESIGN` | `METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW` |

The 2×2 formula is **never** applied silently to another design.

## 3. Supported parameters

`Cmax`, `AUC`, `AUC0-t`, `AUC0-inf`.  
AUC CV is never converted into Cmax CV.

## 4. Mathematical method

**Canonical calculator (single SoT):**  
`app.domain.sample_size.Crossover2x2SampleSizeCalculator`  
Method: `CROSSOVER_2X2_TOST_NCT` / algorithm `BE_TOST_2X2_NCT.v1`

- Log-transformed ratio; σ² = ln(1+CV²); SE = σ√(2/n); df = n−2  
- TOST power via non-central t (iterate even n until power ≥ target)  
- Phase 15.4 wraps this calculator with gating, provenance, fingerprinting, and
  explicit inflation — it does **not** invent a second formula.

## 5. Input provenance

Every non-derived input must cite:

- `EVIDENCE_MEASUREMENT` / claim id, or  
- `VERIFIED_STUDY_FACT` / `SYNOPSIS`, or  
- `EXPERT_INPUT` / `EXPLICIT_CONFIGURATION` / `PROJECT_DEFAULT`

No anonymous inputs. Defaults (if any) are stored explicitly with source kind.

## 6. CVintra eligibility

Eligible only if:

- `verification_status = VERIFIED`  
- `applicability ∉ {LOW, NOT_APPLICABLE}`  
- usability allows sample-size use (`USABLE_FOR_DECISION`)  
- `variability_type = WITHIN_SUBJECT`  
- PK parameter explicit  

Reject: PROPOSED, REJECTED, between-subject, total/unknown type, missing PK.

Multiple eligible / conflicting values →  
`MULTIPLE_ELIGIBLE_INPUTS_REQUIRES_EXPERT_SELECTION` / `MULTIPLE_CONFLICTING_CVINTRA`  
(no average, no auto-pick, no “latest”).

## 7. Applicability

LOW / NOT_APPLICABLE evidence cannot enter authoritative calculation.  
MODERATE/HIGH/DIRECT allowed when verified and usable (policy gate in eligibility module).

## 8–11. GMR, alpha, power, dropout

All explicit; no silent injection.

- Expected ratio (GMR): e.g. 0.95 / 1.00 / 1.05 with source  
- Alpha: e.g. 0.05 with `EXPLICIT_CONFIGURATION` or `EXPERT_INPUT`  
- Power: 80% / 90% explicitly stored as `target_power`  
- Dropout: `required_n` (evaluable) vs `randomized_n`;  
  `inflation_method = DIVIDE_BY_RETAINMENT_RATE` →  
  `randomized = ceil_even(evaluable / (1 − dropout/100))`  
  Missing dropout when inflation required → `MISSING_DROPOUT_ASSUMPTION`

## 12. Rounding

Never round downward. 2×2 uses even-ceil policy (`STAT.ROUND.2X2_EVEN.v1`).  
Store `raw_n` and integer `required_n`.

## 13. Achieved power

After choosing rounded evaluable N, store `achieved_power` separately from `target_power`.

## 14. Multiple scenarios

`SampleSizeScenario` per PK parameter. Controlling parameter only after expert/config.  
Otherwise `REQUIRES_EXPERT_SELECTION`.

## 15. Discrepancy handling

If calculated randomized N ≠ current protocol N → `SAMPLE_SIZE_DISCREPANCY`  
(requires expert interpretation; not an automatic error).

## 16. Versioning & fingerprint

Calculations are immutable. Input change → new calculation version.  
Fingerprint = SHA-256 of normalized  
`(design, parameter, CV, GMR, alpha, power, dropout, method, calculation_version, …)`.

## 17. Expert review

`ACCEPT_CALCULATION` | `REJECT_CALCULATION` | `ACCEPT_CURRENT_N` | `REQUEST_RECALCULATION`  

Approval does **not** mutate Study in Phase 15.4 (`project_to_study` refused).

Recommendation layer always starts at `REQUIRES_EXPERT_DECISION` (never auto-selected).

## 18. AI-off

Authoritative arithmetic is deterministic and works with AI disabled.  
AI cannot calculate authoritative N, select controlling CV/parameter, approve, or mutate Study.

## 19. Limitations

- Only standard 2×2 TOST fully implemented  
- BE limits must be supplied explicitly (no hidden clinical defaulting in 15.4 path)  
- Study projection from approval deferred to future canonical-projection rules  
- Existing project `/statistics/sample-size` API retained for regression (Phase 4);  
  Phase 15.4 study-scoped engine is the authoritative Decision Center path

## API

- `POST /studies/{id}/sample-size/calculate`  
- `GET /studies/{id}/sample-size/calculations`  
- `GET /studies/{id}/sample-size/panel`  
- `GET /sample-size/calculations/{id}`  
- `GET /sample-size/calculations/{id}/inputs`  
- `GET /sample-size/calculations/{id}/provenance`  
- `POST /sample-size/calculations/{id}/request-review`  
- `POST /sample-size/calculations/{id}/approve`  
- `POST /sample-size/calculations/{id}/reject`

## Golden fixture

`UPDCB-02-BE-2026-REAL-01`: current `randomized_n=56` (Synopsis).  
Without verified CVintra → `BLOCKED` / `MISSING_VERIFIED_CVINTRA`.  
CI uses synthetic verified measurements only (no fabricated literature as verified).
