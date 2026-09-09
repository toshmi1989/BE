# Phase 23 — Case Selection

**Version:** 0.28.0  
**Policy:** Select only from `fixtures/real_packages/`. No duplicates. No invented packages.

## Inventory reality

| Class | Count |
|-------|------:|
| Full REAL sanitized | 1 |
| REAL_PARTIAL | 1 |
| Empty intake slots | 8 |
| Target for Controlled Beta | ≥10 full |

**Limitation:** Controlled Beta entry gate cannot open on package population alone until writers deliver ≥9 additional distinct sanitized full packages.

## Selected cases (maximize diversity from what exists)

| case_id | study pattern | documents available | complexity | reason selected |
|---------|---------------|---------------------|------------|-----------------|
| REAL-UPDCB-02-BE-2026 | conflicting_documents, crossover, complete_smpc, legacy_golden_reference | CHECKLIST, SYNOPSIS, SMPC, GOLDEN_PROTOCOL | HIGH — CRITICAL dose conflict across sources | Only full REAL package; covers conflict + complete SmPC + crossover-like design |
| REAL-DESIGN-ONLY-UPDCB | incomplete_package, missing_smpc | DESIGN | MEDIUM — incomplete sources | Only REAL_PARTIAL; covers document incompleteness (counts as partial, not toward ≥10 full) |

## Not selected / unavailable patterns

Empty slots remain for: fed, fasting+fed, different API, missing CVintra, long half-life/parallel, replicate/high-var, legacy-as-input, incomplete SmPC diversity.

These **must not** be filled with synthetic or duplicated packages.

## Writer assignment (template — not fabricated)

When writers are available, assign:

| case_id | writer_id (pseudonym) | session_group |
|---------|----------------------|---------------|
| REAL-UPDCB-02-BE-2026 | *pending* | SG-UPDCB-01 |
| REAL-DESIGN-ONLY-UPDCB | *pending* | SG-DESIGN-01 |

No personal identifiers in analytics.

## Gate implication

`scripts/phase23_beta_gate.py` → **BLOCK** until package/session/Postgres criteria are met (or a documented package override with explicit reason file — still requires writers, pairs, Postgres ops).
