# Phase 19 — Real Case Results

**Version:** 0.24.0  
**Postgres beta:** `docker-compose.beta.yml` (AUTH_REQUIRED=true) — ops documented; unit tests may still use SQLite memory.

## 1. Real package population

| case_id | origin | sanitized | patterns |
|---------|--------|-----------|----------|
| REAL-UPDCB-02-BE-2026 | REAL | yes | conflict dose, crossover, SmPC, golden ref |
| REAL-DESIGN-ONLY-UPDCB | REAL_PARTIAL | yes | incomplete package |

**Distinct full REAL packages:** 1 (target ≥10)  
**Synthetic counted as real:** no  
**Limitation:** Explicit — ≥10 requires writer intake into REAL-INTAKE-03…10 after sanitization checklist.

## 2. Timing methodology

Observed-only. No reconstructed times. Aggregate uses **median / P25 / P75**, not mean alone.

Until writers complete paired manual vs assisted sessions:

| Metric | Value |
|--------|-------|
| Median manual time | *not observed* |
| Median assisted time | *not observed* |
| Median time saving | *not published* |

Infrastructure validates that savings stay `null` unless `observed_directly` and both timings present (`POST /api/field-study/sessions/{id}/timings`).

## 3. Extraction (UPDCB)

Writer field classification uses:

`CORRECT_AUTO | CORRECT_AFTER_REVIEW | MISSING | INCORRECT | CONFLICTING | NOT_APPLICABLE`

`CORRECT_AFTER_REVIEW` ≠ successful automatic extraction.

API: `GET /api/field-study/metrics/extraction`

Critical fields to classify in live study: Sponsor, Product, Test/Reference, Dose, Design, Sequence, Period, Washout, Food, Population, Subjects, Sampling, Analytes, PK, Statistics, Safety.

## 4. Population gap (B-002)

`GET /api/field-study/population-gap`:

- Subjects fields already in controlled vocabulary (`subjects.*`)
- UPDCB full package typically extracts age/sex/N/allocation when present in synopsis
- Incomplete package leaves subjects.* missing → writer enters manually
- **No new medical rule proposed** (`proposed_model_change.required=false`)
- True B-002 blocker remains **insufficient REAL package count**, not missing schema

## 5. Conflicts (UPDCB) — reliable labels n=1

`GET /api/field-study/conflict-benchmark`

| Metric | Value |
|--------|-------|
| Expected | dose (`reference_product.dose` OPEN) |
| Detected | yes |
| Missed | none |
| Precision / Recall / F1 | 1.0 / 1.0 / 1.0 (n=1) |
| Auto-resolve | forbidden |

B-001: **monitor** — OPEN conflict is correct; not a failure; blocks FINAL until expert.

## 6. Evidence / research / decisions

- Provenance rates via beta scoring on REAL cases
- Research usefulness: not claimed beyond real Research Center runs
- Decisions: recommendation ≠ approval (regression guarded)

## 7. Sample size / statistics

Deterministic engines; statuses ACCEPTED/MODIFIED/REJECTED/BLOCKED recorded in field sessions when writers review. No new formulas in Phase 19.

## 8. Protocol / DOCX

Preflight CRITICAL gating unchanged. DOCX integrity checks from Phase 17.5 remain.

## 9. UX feedback template

Fields: saved_most_time, unnecessary_clicks, unclear, did_not_trust, wanted_evidence_on, useful_recommendations, hardest_to_verify, never_automate.

## 10. Production blockers

1. <10 distinct full REAL packages  
2. No observed paired timing dataset yet (B-003 data)  
3. Diversity gaps (fed, replicate, etc.) empty intake slots  
4. Ops: Postgres beta must be used for field study (not SQLite memory)

## Issue revisit

| ID | Status after Phase 19 |
|----|------------------------|
| B-001 | Monitor — dose conflict correctly stays OPEN; frequency=known golden; impact=blocks FINAL until expert |
| B-002 | Open P1 — package population; schema gap not confirmed |
| B-003 | Addressed as **infrastructure**; data collection pending writers |
| B-005 | Documented ops checklist below |

### B-005 Postgres ops checklist

- [ ] `docker compose -f docker-compose.beta.yml up` with `POSTGRES_PASSWORD` + `AUTH_SECRET`
- [ ] `AUTH_REQUIRED=true`
- [ ] `alembic upgrade head` on startup (compose command)
- [ ] Persistent volumes: DB + documents + artifacts
- [ ] Backup: `pg_dump` + copy artifact volume
- [ ] Restore: restore DB + volumes; reopen study; verify workspace/snapshots/artifacts
- [ ] Script smoke: `python scripts/beta_backup_restore_check.py` (file DB / configured URL)

**Do not claim full production ops** until checklist executed in target environment.

---

## PHASE 19 COMPLETE — Final Report

```
PHASE 19 COMPLETE

Version: 0.24.0
Real packages: 1 full REAL + 1 REAL_PARTIAL (explicit limitation; intake slots 8 empty)
Writers: infrastructure ready; live paired sessions not yet recorded
Study patterns: conflicting docs + incomplete package covered; fed/replicate/etc. pending intake
Postgres: docker-compose.beta.yml AUTH_REQUIRED=true; ops checklist documented (not claimed fully tested in prod)
Extraction accuracy: field-study classification API ready; live multi-case rates pending writers
Wrong value rate: pending observed writer classifications
Missing rate: pending observed writer classifications
Conflict precision: 1.0 (n=1 UPDCB labeled)
Conflict recall: 1.0 (n=1 UPDCB labeled)
Evidence provenance: evaluated via Phase 18 beta harness on REAL cases; expand with package growth
Research usefulness: not claimed from synthetic; collect via field-study research events
Median manual time: not observed
Median assisted time: not observed
Median time saving: not published (requires direct observation both sides)
P25/P75 time saving: not published
Manual edits: pending sessions
Expert decisions: pending sessions
Top repeated errors: dose conflict OPEN (expected); incomplete package MISSING subjects.*; insufficient REAL diversity
B-001: Monitor (not blocker failure)
B-002: Open P1 — <10 REAL packages; no invented population medical rule
B-003: Infra complete; observed timing data open
B-005: Documented; execute checklist before claiming ops-ready
P0: none new (dose conflict remains correctly gated)
P1: B-002 package population; B-003 timing data; B-005 ops execution
P2: B-004 incomplete package labeling; B-006 research corpus
P3: cosmetic / diversity documentation only
Regression: Phase 15–18 subset + Phase 19 tests PASS
Golden: PASS (AI-off golden)
AI-off: PASS
Production readiness: READY-WITH-BLOCKERS
Recommendation for Phase 20: Intake ≥9 additional sanitized distinct REAL packages; run paired writer time study; close B-003 with published median/P25/P75; execute Postgres backup/restore in beta; then re-gate production.
```
