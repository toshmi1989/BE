# Knowledge Base v1 — Expert Knowledge Foundation (Phase 12A.1)

## Architecture

```
Evidence / Sources
        ↓
KnowledgeRule  (evaluate / propose / gap / recommend — never mutates Study)
        ↓
Proposal (Design / Food / Sampling / Washout / SampleSize / Analyte / PK / Criteria)
        ↓
ExpertDecision  (PROPOSED → APPROVED | REJECTED | SUPERSEDED)
        ↓
Canonical Study Snapshot  (via approved workflow — not silent field writes)
        ↓
ProtocolDraft → DOCX
```

Forbidden shortcuts:

- Evidence → DOCX directly
- AI → Study field directly
- Interview statements treated as VERIFIED regulatory norms

## Statuses

### KnowledgeRule / RegulatoryBasis

| Status | Meaning |
|--------|---------|
| PROPOSED | System/interview proposed; needs expert confirmation |
| VERIFIED | Confirmed by official source and/or competent expert |
| UNVERIFIED | Insufficient data for safe use |
| REJECTED | Rejected by expert |

### ExpertDecision

| Status | Meaning |
|--------|---------|
| PROPOSED | Awaiting review |
| APPROVED | Formal expert decision (audit retained) |
| REJECTED | Rejected |
| SUPERSEDED | Replaced by a newer APPROVED decision of same type/target |

### KnowledgeGap

| Status | Meaning |
|--------|---------|
| OPEN | Unresolved |
| RESOLVED | Answered with recorded resolution |
| DISMISSED | Closed without applying a value |

Importance: LOW | MEDIUM | HIGH | CRITICAL. Open CRITICAL / blocking gaps contribute CRITICAL validation issues and block REVIEW/FINAL readiness.

## KnowledgeRule

Persisted rule with `rule_code`, domain, condition/action, provenance (`source_ids`, `evidence_claim_ids`, optional `regulatory_basis_id`), status, and `requires_expert_confirmation`.

Domains: INPUT, REFERENCE_SELECTION, DESIGN, FOOD, SAMPLE_SIZE, SAMPLING, WASHOUT, ANALYTE, PK, ELIGIBILITY, SAFETY, STATISTICS, SOURCE, PREVIOUS_PROTOCOL, QA.

Seed catalog: `app/domain/knowledge_seed.py` — all seeds are PROPOSED + `requires_expert_confirmation=true`.

## ExpertDecision

Formal recorded decision (not a silent `manual_override`). Approve/reject creates audit trail; prior APPROVED of same type+target becomes SUPERSEDED. **Approve does not mutate Study/Design ORM** in this phase — decision state is the record of truth until a later apply workflow.

## KnowledgeGap

Created when data is insufficient. System must not invent values. Foundation gaps are seeded per project via `/knowledge-rules/seed?project_id=…`.

## RegulatoryBasis

Citation infrastructure (title, document identifier, section/page/paragraph, jurisdiction, status). Linked from KnowledgeRule / ExpertDecision / EvidenceClaim via IDs. Not auto-filled with a complete norm corpus.

## DesignDecisionEngine

Returns `DesignDecisionProposal` (design, reasons, inputs, rules, evidence, regulatory basis, confidence, gaps, expert flag).

- No hardcoded high-CV threshold
- No hardcoded long half-life threshold
- Expanded BE limits → KnowledgeGap / ExpertDecision only
- Final design → ExpertDecision(DESIGN)

## SamplingRuleSet

Regulatory adequacy (`evaluate_sampling_plan`) is separate from heuristics (`TMAX_CAPTURE_WINDOW`). Heuristics never alone grant PASS. `CompatibilitySamplingPointGenerator` wraps the existing sampling engine.

## PK semantic model

`AUCMetricType` enum + `PKParameterDefinition` / `PKParameterProfile`. Compatibility aliases map legacy `AUC0-t` strings → `AUC_0_LAST`. Display via DisplayValueRegistry (`AUC0-x`, `AUC0-72`, …).

## CriteriaRuleSet

Standard + SmPC overlays (CYP, contraindications, smoking, contraception, vomiting `2×Tmax` as PROPOSED). No hardcoded CYP lists or contraception days without SmPC evidence.

## PreviousProtocolDiff

`PreviousProtocolComparison` + `ProtocolDiffItem` including `LEGACY_SUSPECTED` — warn/review only; never silent delete.

## ProtocolQA

`ProtocolQAService` / `run_protocol_qa` — categories IDENTITY…DOCUMENT; severities INFO/WARNING/ERROR/CRITICAL. Foundation checks for canonical mismatches, placeholders, enum leakage, broken refs, legacy suspicion.

## API (selected)

- `GET/POST/PATCH /knowledge-rules`, `POST /knowledge-rules/seed`
- `GET/POST /expert-decisions`, `…/approve`, `…/reject`
- `GET/POST /knowledge-gaps`, `…/resolve`
- `POST /projects/{id}/design/propose`
- `POST /projects/{id}/sampling/evaluate|propose`
- `POST /projects/{id}/pk/analytes/propose`, `…/pk/parameters/propose`
- `POST /projects/{id}/criteria/evaluate`
- `POST/GET /projects/{id}/qa`
- `POST /projects/{id}/protocol-diff`

## Out of scope (Phase 12A.1)

Full protocol generation, DOCX P2 expansion, medical text authorship, Potvin B/C numerics, universal meal kcal/fat/ml, ±25% as regulatory PASS, auto reference product finalization, invented safety checklists.
