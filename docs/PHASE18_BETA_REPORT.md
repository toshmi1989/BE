# Phase 18 — Real-World Beta Validation Report

**Version:** 0.23.0  
**Status:** Framework COMPLETE with documented population limitations  
**Date:** 2026-09-08

## 1. Test population

| Origin | Count |
|--------|------:|
| REAL (full UPDCB package) | 1 |
| REAL_PARTIAL (design-only) | 1 |
| SYNTHETIC (labelled) | 10 |
| **Total registry cases** | **12** |

**Limitation:** Acceptance asked for ≥10 protocol cases — met via registry, but **only 2 have real/partial writer documents**. Remaining cases are **clearly labelled SYNTHETIC** until real packages are supplied. Do not treat synthetic scores as clinical validation.

## 2. Cases

Categories A–L registered in `fixtures/beta/registry.json`:

- A/B: 2×2 fasting / fed (synthetic)
- C: fasting+fed (synthetic)
- D: high-var replicate (synthetic)
- E: long half-life / parallel (synthetic)
- F/G/H: missing CVintra / half-life / Tmax (synthetic)
- **I: conflicting docs — UPDCB REAL (mandatory)**
- **J: partial package — design-only REAL_PARTIAL**
- K: document quality (synthetic)
- L: stale legacy protocol values (synthetic)

## 3. Extraction accuracy

Harness: `score_extraction` (AUTO-EXTRACTED vs EXPERT-VERIFIED vs UNRESOLVED).

- Golden CASE-I: run via `/api/beta/cases/CASE-I-CONFLICTING-DOCS/evaluate`
- Synthetic cases: expected facts seeded as PROPOSED (not claimed as verified medical truth)

**Recorded in automated tests** — see Phase 18 pytest output for numeric rates. Unverified extraction is **not** scored correct merely because an expert later fixes it.

## 4. Canonical accuracy

Key fields scored Correct / Missing / Conflicting / Incorrect (`score_canonical`).

## 5. Conflict detection

CASE-I expects `reference_product.dose` 15 vs 30 mg:

- True Positive required
- Auto-resolve forbidden
- Metrics: TP / FP / FN in evaluate payload

## 6. Evidence quality

Rates: source / location / excerpt / confidence / verification status attached.

## 7. Research quality

Synthetic cases list expected research questions. Full source-relevance scoring requires live Research Center runs per case — **not claimed complete** without real corpora.

## 8. Decision workload

Expected decisions listed per case. Counts of approved/rejected require live writer sessions — placeholders in evaluate payload.

## 9–10. Sample size / Statistics

Deterministic engines reused. Recommendation ≠ approval. Missing CVintra → sample size blocked/review.

## 11. Protocol consistency

Canonical Snapshot → Protocol Draft path from Phase 16–17. Cross-field consistency via workspace preflight.

## 12. DOCX quality

Existing DOCX validators reused (Phase 9/12). Generation remains gated by CRITICAL preflight.

## 13. Writer time savings

**Not claimed.** `writer_time` fields are null until observed:

- T_manual
- T_system_assisted
- T_review

## 14–15. Critical / repeated failures

See `docs/BETA_ISSUE_LOG.md` (B-001…B-006).

## 16. Production blockers

1. Insufficient real writer packages (population bias toward UPDCB)
2. AUTH_REQUIRED + strong AUTH_SECRET required for beta (`docker-compose.beta.yml`)
3. Writer time study not executed
4. Research usefulness not fully benchmarked on synthetic cases

## 17. Recommended next phase

**Phase 19 — Real Package Expansion & Writer Field Study**

- Ingest ≥10 distinct real BE packages across design patterns
- Run observed time study with medical writers
- Close P1 population / ROI blockers
- Harden Postgres beta backups in ops runbooks

## How to run

```bash
# Evaluate all registry cases (AI off)
pytest backend/tests/test_phase18_beta_validation.py -q

# API
GET /api/beta/cases
POST /api/beta/cases/CASE-I-CONFLICTING-DOCS/evaluate
GET /api/beta/studies/{id}/writer-review

# Beta Postgres stack
docker compose -f docker-compose.beta.yml up --build

# Backup/restore smoke
python scripts/beta_backup_restore_check.py
```
