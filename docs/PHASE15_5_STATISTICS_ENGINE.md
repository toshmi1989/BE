# Phase 15.5 — Deterministic Statistics Engine

**Version:** 0.20.0  
**Does not start:** Phase 16 / post-study statistical programming / fabricated GMR/CI

## 1. Architecture

```
CANONICAL STUDY FACTS
+ VERIFIED REGULATORY EVIDENCE / RULES / EXPERT DECISIONS
        ↓
STATISTICS INPUTS (provenanced)
        ↓
DETERMINISTIC STATISTICS PLAN (STATISTICAL_METHOD_PLAN)
        ↓
ANALYSIS SCENARIOS
        ↓
EXPERT REVIEW
        ↓
OPTIONAL CANONICAL PROJECTION (not in this phase by default)
```

Distinguishes: `CURRENT_STUDY_FACT` ≠ `STATISTICAL_RECOMMENDATION` ≠ `STATISTICAL_PLAN` ≠  
`EXPERT_DECISION` ≠ `REGULATORY_REQUIREMENT`.

Canonical ANOVA vocabulary aligns with existing `stats_rules.ANOVA_TOST_90CI` —  
**no duplicate math module**. Model id: `ANOVA_LOG_2X2` with terms  
`treatment`, `sequence`, `period`, `subject_within_sequence`.

## 2. Parameter roles

`PRIMARY_BE` | `SECONDARY_PK` | `DESCRIPTIVE` | `SAFETY` | `NOT_ANALYZED_FOR_BE`  

PRIMARY_BE only via verified rule or expert decision — never silent from synopsis.

## 3. Transformations

`NONE` | `LOG` — parameter-level; not auto-applied to every parameter.  
Tmax stays `NONE` / descriptive.

## 4. Statistical models

Supported: `ANOVA_LOG_2X2` for `STANDARD_2X2_CROSSOVER` only.  
Replicate / adaptive / parallel → `METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW`.

## 5–6. Confidence intervals & estimands

Planned estimate: Test/Reference geometric mean ratio.  
Confidence level stored explicitly (e.g. 0.90) with provenance.  
**No fabricated observed GMR/CI** without participant-level data.

## 7. Acceptance intervals

Explicit `lower_bound` / `upper_bound` + source + verification_status.  
Missing when required → `MISSING_ACCEPTANCE_INTERVAL`.

## 8. Descriptive statistics

Explicit list per parameter (N, Mean, SD, CV%, Min, Median, Max, Geometric Mean).  
Tmax default: Median, Range, Min, Max.

## 9. Tmax

Role `DESCRIPTIVE`; never `ANOVA_LOG_2X2` / LOG.

## 10. Safety

Descriptive safety summaries only; no hypothesis testing unless a verified rule exists.

## 11. Evidence gates

PROPOSED evidence is not authoritative methodology.  
Current study facts labeled as such — not regulatory requirements.

## 12. Current study facts

Golden UPDCB synopsis facts (ANOVA, log, 90% CI, 80–125%, PK list) recovered as  
`CURRENT_STUDY_FACT` inputs requiring expert handling.

## 13. Expert decisions

APPROVE / REJECT / MODIFY / REQUEST_MORE_INFORMATION — versioned; AI cannot approve.

## 14. Versioning

New plan version on parameter/role/transform/model/CI/acceptance/population change.  
Prior versions remain auditable (`SUPERSEDED`).

## 15. Dependencies

`STATISTICS` registered in Phase 15.1 dependency registry.  
Design / PK endpoint / evidence_version changes supersede affected plans.  
Sample size (`randomized_n`) does **not** define statistical methodology.

## 16. Limitations

- Method planning only (no post-study dataset processing)  
- Single supported inferential model: 2×2 log-ANOVA  
- Study projection from approval not auto-enabled  

## 17. Future post-study interface

Reserved: PK dataset → model → GMR → 90% CI → BE conclusion.  
Not implemented in 15.5; `observed_data_present` / fabricated results hard-blocked.

See also: `docs/PHASE15_4_SAMPLE_SIZE_ENGINE.md`, `docs/PHASE15_DECISION_ENGINE.md`
