# Phase 14 — Real Writer Input Workflow

**Version:** 0.15.0  
**Status:** Implemented (AI-off deterministic path)

## 1. Real-world writer workflow

Writers typically provide a package of source documents (not a finished Study):

1. Upload documents into a **Study Input Package**
2. **Classify** each document (CHECKLIST / SYNOPSIS / DESIGN / SMPC / …)
3. **Extract** candidate structured values (PROPOSED)
4. Preserve **provenance** (source, version, location, excerpt)
5. **Detect conflicts** (no auto-resolve, no majority vote)
6. **Detect missing inputs** → KnowledgeGap / ResearchTask
7. **Expert review** (VERIFY / REJECT / resolve conflict)
8. **Canonical projection** from VERIFIED/resolved values only
9. ProtocolDraft / DOCX remain downstream of Canonical Study

**Forbidden shortcut:** documents → LLM → Study.

## 2. Supported document types

| Type | Role |
|------|------|
| CHECKLIST | Administrative / product packaging inputs |
| SYNOPSIS | Full study overview (optional if DESIGN present) |
| DESIGN | Short design/subjects text (first-class) |
| SMPC | Official product information |
| PREVIOUS_PROTOCOL | Contextual evidence only — not Study SoT |
| REGULATORY / PUBLICATION | Registered; no uncontrolled Study field fill |
| OTHER / UNKNOWN | Registered; no controlled extraction |
| GOLDEN_PROTOCOL | REFERENCE_OUTPUT for semantic regression only |

## 3. Study Input Package architecture

Entity: `StudyInputPackage` (`backend/app/domain/study_input_package.py`)

- Container for documents + candidates + conflicts + gaps + coverage
- Does **not** duplicate Canonical Study as a second source of truth
- Statuses: DRAFT → EXTRACTING → READY_FOR_REVIEW / REVIEW_REQUIRED / BLOCKED / READY_FOR_ASSEMBLY

## 4. Extraction pipeline

`study_input_pipeline.py`:

```
attach/classify → extract_document(type) → CandidateStudyValue[]
→ conflict detection → missing-input → coverage → readiness
```

Deterministic extractors:

- `extract_checklist`
- `extract_synopsis`
- `extract_design_only`
- `extract_smpc` (PDF via pypdf)

## 5. Provenance

Every candidate requires:

- `source_id`
- `excerpt`
- controlled `field_path`
- `document_type` / extraction method
- optional location / source_version_id / document_id

Missing provenance is rejected at construction time.

## 6. Conflict handling

`study_input_conflicts.py`

- Conflict when material values differ for the same field path
- Statuses: OPEN / UNDER_REVIEW / RESOLVED / DISMISSED
- Outcomes: SELECT_VALUE / KEEP_BOTH_WITH_CONTEXT / REQUIRES_EXTERNAL_EVIDENCE / DATA_ENTRY_ERROR
- Resolution requires reviewer + timestamp + reason

**Golden conflict (UPDCB-02-BE-2026):**

| Source | reference_product.dose |
|--------|------------------------|
| CHECKLIST | 30 mg |
| SYNOPSIS | 15 mg |
| SMPC | 15 mg |

→ **OPEN CONFLICT** (not auto-resolved; majority vote forbidden).

## 7. Missing-input handling

Profiles: REQUIRED / RECOMMENDED / OPTIONAL

- DESIGN **or** SYNOPSIS required for assembly
- SMPC required for product-specific medical/safety facts
- Missing SmPC → `MISSING_SMPC_REFERENCE_PRODUCT` KnowledgeGap (no fabricated medical text)
- Missing Synopsis with DESIGN present → non-blocking `MISSING_SYNOPSIS_OPTIONAL`

## 8. Research handoff

Missing SmPC creates ResearchTask `FIND_SMPC_REFERENCE_PRODUCT`.  
External search results remain assistive until SOURCE → CLAIM → REVIEW → VERIFIED (Phase 13 pipeline).

## 9. Canonical resolution

`resolve_to_canonical_projection`:

- Only VERIFIED (or SELECT_VALUE after resolve) values may populate projection
- Open conflicts are skipped
- PREVIOUS_PROTOCOL / GOLDEN_PROTOCOL / OTHER never overwrite Study
- `study_mutated` always false from extraction path

## 10. AI-off behavior

Full real package extraction works with `AI_ENABLED=false`.  
AI may add PROPOSED candidates only; cannot verify, resolve conflicts, activate rules, or mutate Study.

## 11. Golden Fixture

`fixtures/study_inputs/updcb_02_be_2026/`

- Fixture id: `UPDCB-02-BE-2026-REAL-01`
- Documents: checklist.docx, synopsis.docx, smpc_ranvek.pdf, golden_protocol.docx
- Design-only: `fixtures/study_inputs/design_only_updcb/`

Semantic comparison compares structured values (MATCH/MISMATCH/MISSING), not DOCX byte equality.

## 12. Limitations

- Extractors are heuristic/regex — not a full NLP protocol parser
- SmPC extraction is identity/safety-signal oriented, not full SmPC structuring
- Canonical projection is a read-only map in this phase (Study ORM mutation remains via existing expert apply paths)
- No new medical decision algorithms (Potvin, sampling optimization, etc.)

## 13. Test coverage

`backend/tests/test_phase14_study_input_workflow.py` — groups A–T + parametrized extras (≥100 tests).

## 14. Migration notes

- Version bump: **0.14.3 → 0.15.0**
- New API prefix: `/api/study-input/*`
- In-memory package store for API contract (same pattern as regulatory review queue)
- Phase 13 regulatory evidence architecture unchanged
- Dashboard: Study Input Package panel added

## API surface (minimum)

- Create / list / get package
- Upload / classify / list documents
- Run extraction
- Candidates / conflicts / missing / coverage / readiness
- Verify/reject candidate
- Resolve conflict
- Load real + design-only fixtures
- Golden semantic compare
- AI propose (PROPOSED only)
