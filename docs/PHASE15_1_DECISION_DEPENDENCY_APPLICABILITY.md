# Phase 15.1 — Decision Dependency & Evidence Applicability

**Version:** 0.18.0  
**Hardening of:** Phase 15.0 Decision Center  
**Does not start:** Phase 16, Sample Size engine, Statistics engine

## 1. Dependency graph

Single registry: `decision_dependency_registry` in
`backend/app/domain/decision_dependency.py`.

Model:

```
Study field / gap / conflict
    → Decision domain (DESIGN|FOOD|WASHOUT|SAMPLING|ANALYTE_PK)
    → Decision evaluation
```

Examples:

| Field / gap | Domains |
|-------------|---------|
| `reference_product.dose` | DESIGN |
| `reference_product.name` | DESIGN, ANALYTE_PK |
| `t_half` / `pk.t_half` | WASHOUT, SAMPLING |
| `tmax` / `pk.Tmax` | SAMPLING |
| `cv_intra` (gap) | DESIGN (non-blocking) |
| `food.condition` | FOOD |
| `bioanalysis.analyte` | ANALYTE_PK |

Unregistered dependencies are **not** assumed.

## 2. Blocker evaluation

`is_decision_blocked(domain, study_state)` inspects **only** that domain’s
registered dependencies.

Structured blockers:

- `blocking_reason_code`
- `field_path`
- `severity`
- `kind` (CONFLICT | GAP | MISSING_FIELD | EVIDENCE)
- `reference_id` (conflict / gap / evidence)

Global “study has issues → all domains BLOCKED” is removed.

## 3. Current fact vs recommendation

| Type | Meaning |
|------|---------|
| `CURRENT_STUDY_FACT` | Already present in protocol inputs (e.g. Synopsis washout = 7 days) |
| `SYSTEM_RECOMMENDATION` | Engine output |
| `EXPERT_DECISION` | Explicit human decision |
| `EVIDENCE` / `RULE` | Supporting materials |

Synopsis washout is **not** auto-labeled SYSTEM_RECOMMENDATION,
EXPERT_DECISION, or REGULATORY_REQUIREMENT.

## 4. Evidence applicability

Independent of verification:

- `verification_status`: PROPOSED | VERIFIED | REJECTED
- `applicability`: DIRECT | HIGH | MODERATE | LOW | UNKNOWN | NOT_APPLICABLE

`VERIFIED + UNKNOWN` is valid.

## 5. Analogue study applicability

Same substance / form / different dose → typically MODERATE/HIGH, **never
automatic DIRECT**. Different substance → LOW/UNKNOWN.

## 6. Regulatory applicability

Source existence ≠ claim applies. Unreviewed contextual fit → UNKNOWN with
explicit `applicability_reason`.

## 7. Stale evidence

Source version change → applicability review becomes `STALE` /
`REQUIRES_REVIEW`. Do not silently reuse.

## 8. Change impact

`domains_affected_by_field` + `invalidate_on_upstream_change` recompute only
registered dependents (e.g. `t_half` → WASHOUT + SAMPLING, not FOOD).

## 9. Expert interaction

`KEEP_CURRENT_VALUE` confirms a CURRENT_STUDY_FACT without rewriting source
evidence and without creating a SYSTEM_RECOMMENDATION.

## 10. AI-off behavior

Dependency / blocking / applicability classification works with AI OFF.
AI may propose applicability (remains PROPOSED) but cannot:

- finalize applicability as VERIFIED
- unblock decisions
- approve / keep-current
- mutate Study
- activate rules

## API

- `GET .../decisions/{id}/dependencies`
- `GET .../decisions/{id}/blockers`
- `GET .../decisions/{id}/evidence`
- `GET .../decisions/{id}/applicability`
- `POST .../decisions/{id}/keep-current`

## Golden fixture (UPDCB-02-BE-2026-REAL-01)

Dependency-aware (illustrative; graph is SoT):

| Domain | Typical status | Why |
|--------|----------------|-----|
| DESIGN | BLOCKED | reference dose conflict (+ CVintra non-blocking) |
| FOOD | REVIEW_REQUIRED | meal composition incomplete; **not** dose |
| WASHOUT | BLOCKED | missing t½; **not** dose |
| SAMPLING | BLOCKED | missing Tmax/t½; **not** dose |
| ANALYTE_PK | REVIEW_REQUIRED | analyte known; dose conflict non-blocking |

## Production stance

READY-WITH-BLOCKERS until dependency blockers and gaps are resolved by experts.
