# Phase 12B.2 — Protocol Content Generation: Sections 5–8

**Version:** 0.13.2  
**Extends:** Phase 12B.1 core generation  
**Medical rules added:** ZERO  
**Invented medical defaults:** ZERO

## Sections covered

Existing `SECTION_TREE` codes only:

| Area | Codes |
|------|--------|
| Eligibility | 5, 5.1–5.3 |
| Procedures | 6, 6.1–6.3.x |
| PK / Bioanalysis | 7, 7.1–7.3.4 |
| Safety | 8, 8.1–8.5 |

API: `POST /api/projects/{id}/content/generate-sections-5-8`

## Criteria architecture

```
Canonical EligibilityCriteria
  + CriteriaRuleSet overlays (CRIT-*)
  + SmPC / evidence provenance
  + Approved ExpertDecision
  → Section 5 blocks
```

- Standard lists render from study eligibility (source of truth).
- Drug-specific overlays (CYP, contraindications, contraception, smoking) require evidence / SmPC ids.
- **CRIT-05 vomiting (2×Tmax)** stays **PROPOSED** unless ExpertDecision elevates — never auto-verified.
- Missing data → KnowledgeGap / unresolved placeholders — never `N/A`.

## Procedure architecture

```
ProcedureDefinition → ProcedureEvent → ProcedureSchedule → ProtocolContentBlock
```

- Timeline from `compose_procedure_schedule` (structural, no invented battery).
- Dosing from canonical Product/Design.
- Food: condition via DisplayValueRegistry only; no kcal/fat/water invention.
- Washout: canonical / approved only.
- Sampling: **single** `CanonicalSamplingPlan` shared with §4 / synopsis / tables.
- Sample prep: `SampleProcessingDefinition` / `BioanalysisPlan` fields only; provenance required for final.

## PK architecture

```
AnalyteSelectionDecision → PK profile → §7 content
```

- Analyte final text only with **APPROVED** `ANALYTE_SELECTION`.
- AUC metrics via `AUCMetricType` + DisplayValueRegistry (`AUC0-x` ≠ `AUC0-72`).
- STANDARD_PROPOSED profile is draft-only until `PK_PARAMETER_SET` approved.

## Bioanalysis architecture

- Source: `BioanalysisPlan`.
- Missing method → `{{BIOANALYSIS.METHOD}}` + gap — **no HPLC-MS/MS / LLOQ defaults**.
- Final requires resolved status + provenance (`source_ids` / evidence / decision).

## Safety architecture

- Source: `SafetyPlan` + safety rows from `ProcedureSchedule`.
- Only enabled categories render; empty plan → unresolved.
- Timing from schedule / plan fields — no hardcoded `-1h, 2h, 4h`.
- Unverified / PROPOSED safety never `display_as_final`.

## Provenance

Blocks carry: `section`, `block_code`, `canonical_source`, `source_ids`, `rule_id`, `expert_decision_id`, `resolution_status`, `knowledge_gaps`.

## Expert decisions

| Status | Behaviour |
|--------|-----------|
| APPROVED | Eligible for final |
| PROPOSED | Draft / REVIEW REQUIRED only |
| REJECTED / SUPERSEDED | Not rendered as current content |

## KnowledgeGaps

Examples: missing criteria, contraception without SmPC, smoking without evidence, empty sample processing, missing bio method, empty SafetyPlan / AE.

## Final vs draft

- **DRAFT:** may show PROPOSED / unresolved with markers.
- **FINAL:** only RESOLVED / approved; QA blocks proposed-as-final.

## DOCX

Targeted path: `only_sections` for 5–8 codes; unselected static bodies preserved; no global replace; no positional invent mapping.

## QA codes (12B.2)

`QA.ELIGIBILITY.*`, `QA.PROCEDURE.*`, `QA.SAMPLING.*`, `QA.PK.*`, `QA.BIOANALYSIS.*`, `QA.SAFETY.*`, `QA.CONTENT.REJECTED_DECISION`, `QA.CONTENT.SUPERSEDED_DECISION`, plus existing `CONTENT.*`.

## Limitations

- Clinical batteries / safety checklists not invented.
- Procedure schedule remains structural/PROPOSED for clinical completeness.
- Previous-protocol import still not a truth source.
- Sections 9+ deferred to later phases.

## Future

Phase 12B.3+ may extend remaining sections with the same controlled pipeline.
