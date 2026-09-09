# Phase 12A.2 — Protocol Content Foundation

**Version:** 0.13.0  
**Extends:** Phase 12A content models + Phase 12A.1 knowledge layer  
**Medical rules added:** ZERO  
**Invented medical defaults:** ZERO

## Pipeline

```
CANONICAL STUDY
      ↓
CONTENT DEFINITIONS (Procedure / Bioanalysis / Safety / Blocks)
      ↓
CONTENT PLAN (ProtocolContentMatrix)
      ↓
ContentResolver → ResolvedContent
      ↓
ContentRenderer (stubs) / content_draft_adapter
      ↓
PROTOCOL ASSEMBLY / DOCX (unchanged mass coverage)
```

## Domain models

| Model | Role |
|-------|------|
| ProcedureDefinition | Structured procedure (extended categories) |
| ProcedureSchedule | Composition from canonical Design/Food/Sampling/… |
| ProcedureEvent | Timeline event projection (no invented times) |
| ProcedureDependency | Technical REQUIRES/PRECEDES graph |
| BioanalysisPlan + BioanalysisPlanProposal | Empty/partial; no HPLC/LLOQ defaults |
| SampleProcessingDefinition | Empty shell |
| SafetyPlan + SafetyPlanProposal | Explicit flags only; safety library gap |
| ProtocolContentBlock | Block typing |
| ProtocolContentMatrix | Section ↔ source ↔ canonical map |
| ContentResolver | Priority: Canonical → Approved Decision → Verified → Proposed → Gap |
| ContentRenderer | CanonicalValue / Procedure / Condition / Table / Reference |
| CONTENT.* validation | Missing source, proposed-as-final, gaps, legacy mismatch |

## ExpertDecision / KnowledgeGap boundaries

- Only **APPROVED** decisions may be `display_as_final`
- PROPOSED / REJECTED / SUPERSEDED never final
- Missing content → KnowledgeGap, never `"N/A"` invention
- Proposals do **not** mutate Study/Canonical

## API

- `GET/POST /api/procedure-definitions`
- `GET/POST /api/projects/{id}/procedure-schedule` (+ `/validate`)
- `GET /api/projects/{id}/bioanalysis`, `POST …/propose`, `POST …/validate`
- `GET /api/projects/{id}/safety-plan`, `POST …/propose`, `POST …/validate`
- `GET /api/projects/{id}/content-matrix`
- `POST /api/projects/{id}/content/resolve`, `POST …/content/validate`

No approve endpoints (use ExpertDecision).

## DOCX

Thin `content_draft_adapter` only. No P0/P1 mass rewrite. Existing renderer remains functional.

## KnowledgeGaps

- Standard BE safety library not yet formally verified
- Bioanalysis method / field gaps when proposing empty plan

## Out of scope

Full protocol text generation, DOCX section expansion, invented safety checklist, invented bioanalysis method/LLOQ, universal procedure times, AI-required path.
