# Phase 12A.1 — Expert Knowledge Foundation — Final Report

**Status:** COMPLETE — stop here (do not start 12A.2).

**Version:** 0.12.1

## 1. What was created

Formal expert-knowledge layer: rules, decisions, gaps, regulatory citations, design/food/sampling/washout/sample-size/PK/criteria/source proposals, previous-protocol diff, Protocol QA — without inventing medical thresholds or expanding DOCX.

## 2. Models / tables

| Table / model | Purpose |
|---------------|---------|
| `regulatory_bases` / `RegulatoryBasisRecord` | Regulatory citation infrastructure |
| `knowledge_rules` / `KnowledgeRuleRecord` | Versioned knowledge rules |
| `expert_decisions` / `ExpertDecisionRecord` | Formal expert decisions + audit |
| `knowledge_gaps` / `KnowledgeGapRecord` | Unresolved knowledge questions |
| `previous_protocol_comparisons` / `PreviousProtocolComparisonRecord` | Diff runs |
| `protocol_diff_items` / `ProtocolDiffItemRecord` | Diff line items (incl. LEGACY_SUSPECTED) |
| `protocol_qa_runs` / `ProtocolQARunRecord` | QA run summary |
| `protocol_qa_findings` / `ProtocolQAFindingRecord` | QA findings |

Phase 12A `ExpertRule` catalog left intact (separate empty catalog).

## 3. Services / domain

- `knowledge_service` — seed, CRUD, approve/reject (no Study mutation), proposals, QA, diff
- `design_decision_engine` — structured DesignDecisionProposal
- `sampling_rules` — SamplingRuleSet eval + SamplingPointGenerator interface
- `decision_proposals` — Food / Washout / SampleSize proposal layer
- `pk_semantic` — AUCMetricType, PKParameterDefinition/Profile, analyte proposal, compat aliases
- `criteria_rules` — CriteriaRuleSet + SourcePriorityProfile + safety foundation note
- `protocol_qa` — PreviousProtocolDiff helpers + ProtocolQA
- `knowledge_seed` — PROPOSED rule catalog + foundation gaps
- Validation: open CRITICAL KnowledgeGaps → `VAL.KNOWLEDGE.GAP_OPEN.v1` (blocking)

## 4. API endpoints

- `GET/POST/PATCH /api/knowledge-rules`, `POST /api/knowledge-rules/seed`
- `GET/POST /api/expert-decisions`, `POST …/approve`, `POST …/reject`
- `GET/POST /api/knowledge-gaps`, `POST …/resolve`
- `GET/POST /api/regulatory-bases`
- `POST /api/projects/{id}/design/propose`
- `POST /api/projects/{id}/sampling/evaluate`, `…/sampling/propose`
- `POST /api/projects/{id}/pk/analytes/propose`, `…/pk/parameters/propose`
- `POST /api/projects/{id}/criteria/evaluate`
- `POST/GET /api/projects/{id}/qa`
- `POST /api/projects/{id}/protocol-diff`

## 5. Seeded rules

**36** KnowledgeRules (INPUT/REF/DESIGN/FOOD/SAMPLE/WASH/SAMPLING/ANALYTE/CRIT/SAFETY/SOURCE) — see `docs/EXPERT_RULE_STATUS.md`.

## 6. Rules remaining PROPOSED

**All 36** seeded rules remain PROPOSED with `requires_expert_confirmation=true` (no verified regulatory evidence attached as VERIFIED).

## 7. KnowledgeGaps created (foundation)

8 foundation gaps including Potvin B/C, final randomized N (CRITICAL/blocking), long HL threshold, expanded BE limits, PK exceptions, safety protocol post-2026-06, source conflict algorithm, 72h truncation.

## 8. Medical rules NOT implemented (insufficient verified data)

- Numeric high-variability CV threshold
- Numeric long half-life threshold
- Expanded BE limit auto-selection
- Potvin B/C numerical algorithms
- Universal meal kcal/fat/water/timing constants
- Universal 10/20-minute sampling intervals
- ±25% Tmax as regulatory PASS
- Full standard safety checklist
- Full critical QA medical error list
- Verified source conflict ranking algorithm
- Auto-final ReferenceProduct selection

## 9–11. Tests

| | Count |
|--|------|
| Before Phase 12A.1 | **230** |
| After | **255** passed |
| New (this phase) | **25** (`test_phase12a1_knowledge.py`) |
| Full suite result | **255 passed** in ~14:42 |

(Transient env miss of `pypdf` for an older Phase 6 test was restored; not a 12A.1 regression.)

## 12. Compatibility

- Existing Sampling Engine wrapped, not rewritten
- Sample-size calculator unchanged; proposal/provenance layer added
- AUC string aliases → `AUCMetricType` without breaking old fields
- DisplayValueRegistry: AUC displays + `design_long` for 2×2 / 2×2×4
- ExpertDecision approve does **not** silently write Design/Study
- Phase 12A ExpertRule catalog preserved

## 13. Migrations

- `0013_phase12a1_knowledge.py` (revises `0012`) — additive tables only

## 14. Documentation

- `docs/KNOWLEDGE_BASE_V1.md`
- `docs/EXPERT_RULE_STATUS.md`
- `docs/PHASE12A1_REPORT.md` (this file)

## UI

Minimal Dashboard panels: Expert decisions (propose/approve/reject), Knowledge gaps (resolve). Validation / Evidence panels already present.

## STOP

Phase 12A.1 complete. Do not proceed to Phase 12A.2 automatically.
