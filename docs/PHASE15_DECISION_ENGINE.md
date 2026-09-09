# Phase 15.0 — Evidence-Based Protocol Decision Engine

> **Phase 16 (0.21.0):** Decision Center is composed into the Study Workspace via
> `run_protocol_workflow` / `/api/studies/{id}/workspace`. See
> [PHASE16_END_TO_END_WORKFLOW.md](./PHASE16_END_TO_END_WORKFLOW.md).
> Recommendation ≠ approval; conflicts are never auto-resolved.

**Version:** 0.20.0  
**Automatic medical decisions:** ZERO  
**Study mutation from recommendations:** NONE

> Phase 15.1 hardening: see `docs/PHASE15_1_DECISION_DEPENDENCY_APPLICABILITY.md`  
> Phase 15.2 research workflow: see `docs/PHASE15_2_RESEARCH_EVIDENCE_ENGINE.md`  
> Phase 15.3 real search: see `docs/PHASE15_3_REAL_RESEARCH_PROVIDER.md`  
> Phase 15.4 sample size: see `docs/PHASE15_4_SAMPLE_SIZE_ENGINE.md`  
> Phase 15.5 statistics: see `docs/PHASE15_5_STATISTICS_ENGINE.md`

## 1. Architecture

```
Study Input Package / verified facts / interview / rules / analogues
        ↓
DecisionContext (no Study mutation)
        ↓
Domain engines (DESIGN / FOOD / WASHOUT / SAMPLING / ANALYTE_PK)
        ↓
ProtocolDecision + DecisionEvidence + Evidence matrix
        ↓
DecisionRecommendation (SUPPORTED / PARTIAL / INSUFFICIENT / CONTRADICTED / BLOCKED)
        ↓
Expert APPROVE / REJECT / MODIFY (auditable)
        ↓
Canonical Study only via existing controlled ExpertDecision projection (not silent)
```

Deterministic. Not an LLM.

## 2. Decision domains

| Domain | Purpose |
|--------|---------|
| DESIGN | Crossover / replicate / adaptive / parallel vocabulary |
| FOOD | Fasting / fed / both |
| WASHOUT | Fixed vs half-life-derived (no invent) |
| SAMPLING | Profile assessment (no invented timepoints) |
| ANALYTE_PK | Parent / metabolite vocabulary |
| STATISTICS | Statistical method plan (15.5) — recommendation ≠ approval |

SAMPLE_SIZE and full STATISTICS engines are **out of scope**.

## 3. Evidence types

`REGULATORY_CLAIM`, `REGULATORY_RULE`, `PRODUCT_FACT`, `SMPC_FACT`, `LITERATURE_CLAIM`, `ANALOGUE_STUDY`, `PREVIOUS_PROTOCOL`, `EXPERT_INTERVIEW`, `EXPERT_RULE`, `EXPERT_DECISION`, `STRUCTURED_STUDY_FACT`

Support levels: `SUPPORTS` / `CONTRADICTS` / `NEUTRAL` / `CONTEXT_ONLY`

PROPOSED ≠ VERIFIED. Interview ≠ regulation.

## 4. Recommendation states

`SUPPORTED` · `PARTIALLY_SUPPORTED` · `INSUFFICIENT_EVIDENCE` · `CONTRADICTED` · `BLOCKED`

Confidence = evidence **sufficiency**, not medical correctness probability.

**Recommended ≠ Approved.** UI must keep them distinct.

## 5. Expert approval

`APPROVE` / `REJECT` / `MODIFY` require reviewer, timestamp, rationale.

- Historical recommendations preserved
- `study_mutated=false` in this layer
- Projection to Study only through existing ExpertDecision guards

## 6. Conflict blocking

Open critical conflicts (`reference_product.dose/name`, `test_product.dose`) → dependent domains **BLOCKED**.

Golden fixture UPDCB-02-BE-2026: dose 30 vs 15 → all five domains BLOCKED; design **context** still shown.

## 7. Missing evidence

Examples:

- `MISSING_CVINTRA` → research literature
- `MISSING_HALF_LIFE_FOR_WASHOUT` → **do not calculate** washout
- `MISSING_TMAX_FOR_SAMPLING` → **do not invent** timepoints
- `MISSING_MEAL_COMPOSITION` → do not invent calorie/fat targets

## 8. Analogue studies

Stored with explicit relevance. `identical_to_current=false` always. Never auto-copy design.

## 9. Previous protocols

`CONTEXT_ONLY` evidence. Cannot overwrite current Study.

## 10. AI-off

Full Decision Center works with `AI_ENABLED=false`.

## 11. Provenance

Every DecisionEvidence needs identity/excerpt. Recommendations with SUPPORTED/PARTIAL require evidence.

## 12. Change impact

Uses existing `validation_graph` + `content_change_impact`. Upstream change → decisions `SUPERSEDED` → recompute.

## 13. Limitations

- No SAMPLE_SIZE engine
- No invented CV/t½/Tmax thresholds
- No automatic ACTIVE rule creation
- SmPC/product facts remain signal-oriented unless verified
- In-memory decision store (API contract)

## API

`/api/decision-center/studies/{id}/decisions[...]`  
`/api/decision-center/fixtures/updcb-real/recompute`

## Tests

`backend/tests/test_phase15_decision_engine.py` (≥120 meaningful tests)
