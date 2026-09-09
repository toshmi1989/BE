# Phase 12B.4 — Appendices + Conclusion + Literature + Full Document Finalization

**Version:** 0.13.4  
**Extends:** Phase 12B.3 (sections 9–15)  
**Medical rules added:** ZERO  
**Invented medical defaults:** ZERO  
**Invented administrative values:** ZERO  
**FINAL forced PASS:** NO

## 1. Scope

Controlled generation for existing `SECTION_TREE` codes only (no invented numbers):

| Code | Title | Generator overlay |
|------|--------|-------------------|
| **16** | Appendices | `appendices` |
| **17** | Итог / conclusion | `conclusion` |
| **18** | Literature | `literature` |

Plus **full-document finalization**: assemble sections 1–18 → ProtocolDraft → `run_full_document_qa` → completeness → DRAFT / REVIEW / FINAL gate → DOCX.

APIs:

- `POST /api/projects/{id}/content/generate-sections-16-18`
- `POST /api/projects/{id}/content/generate-full-document`

Does **not** mutate Study. Does **not** force FINAL PASS.

## 2. Appendix architecture

```
STATIC_BLOCKS (16* / APP.*)
  + SIGNATURES (StudyAdministration / persons)
  + STUDY_METADATA (when study identity present)
  → AppendixInventory
  → gen_appendices_12b4
```

- Inventory classifies `STATIC_VERIFIED` / `FORM` / `DYNAMIC_CANONICAL` — does **not** invent appendix letters.
- `APP.*` forms preserved as STATIC_VERIFIED (“не переписывается”).
- Signatures: table from canonical persons/orgs only; missing → `{{SIGNATURES}}` + KnowledgeGap.
- No rewrite of verified form bodies.

## 3. Conclusion

`gen_conclusion_12b4` is deterministic and fact-only:

- Requires product name + design display + (reference product **or** study title).
- Missing critical identity → `{{CONCLUSION.REQUIRED}}` + CRITICAL gap.
- Phrasing uses **планируется** (planned assessment) — never invents completed **результат** / efficacy / safety / PK outcomes.
- Optional periods, food display, randomized N only from canonical SubjectPlan.

## 4. Reference generation

Bibliographic `ReferenceBuilder` (distinct from cross-ref `ReferenceRegistry`):

- Sources: `ctx.sources`, `evidence_claims` (via `source_id`), `regulatory_bases`.
- Deduplicate by `source_id` → `document_identifier` → normalized citation.
- Deterministic order: `(year, title, source_id)` → `REF-001`…
- Empty bibliography → `{{SOURCES.LIST}}` + SOURCES gap — no invented citations.
- Helpers: `find_duplicate_reference_ids`, `find_orphan_source_ids`.

## 5. Full ContentResolver

Existing ContentResolver / matrix / ExpertDecision filter remain:

| Status | Behaviour |
|--------|-----------|
| APPROVED | Eligible for final render (`filter_decision_for_render`) |
| PROPOSED | Draft / review markers only — not final |
| REJECTED / SUPERSEDED | Not rendered as current |

12B.4 overlays do not invent ExpertDecisions.

## 6. Document completeness

`assess_document_completeness(assembled, qa_findings)`:

- Counts resolved / proposed / unresolved / blocked / static / conditional blocks.
- Collects critical KnowledgeGaps and missing-source markers.
- Readiness: `READY` | `READY_WITH_WARNINGS` | `BLOCKED`.
- Draft `status == BLOCKED` → completeness **BLOCKED**.
- Informational only — does **not** replace DRAFT/REVIEW/FINAL gates.

## 7. Full QA

`run_full_document_qa`:

- Aggregates `run_content_generation_qa`, sections 5–8 / 9–15 QA, `run_protocol_qa`.
- Full-text scans: forbidden placeholder phrases, broken reference text, TODO/TBD, raw enums, legacy hints, randomized N, sampling times, AUC0-x≠AUC0-72.
- Table / cross-ref issues from `build_report`.
- DRAFT: gate always `READY` (markers allowed).
- REVIEW / FINAL: blocking or CRITICAL findings → gate `BLOCKED`.
- Never forces FINAL PASS.

## 8. Legacy detection

`legacy_hints` values appearing in document text → `LEGACY_SUSPECTED` / `CONTENT.LEGACY_VALUE`. Previous-protocol / template values are not truth.

## 9. Placeholder detection

- Bare `TODO` / `TBD`, Word “Error! Reference source not found”, unresolved `{{…}}` markers.
- FINAL/REVIEW: unresolved placeholders → `CONTENT.PLACEHOLDER_UNRESOLVED` (CRITICAL, blocking).
- DRAFT may show markers (e.g. `{{SOURCES.LIST}}`).

## 10. Table / reference QA

- Unresolved `TABLE` blocks vs table registry → `QA.TABLE.UNRESOLVED`.
- Broken / unresolved cross-refs in registry → `QA.REF.BROKEN` / `QA.CROSSREF.UNRESOLVED`.
- Bibliography entries must be source-backed (no invented citations).

## 11. Cross references

`ReferenceRegistry` resolves section/table/appendix links collected from REFERENCE blocks. Appendix may emit `target_type=appendix` when forms are present. Broken refs block draft status and full QA.

## 12. DOCX full build

- Targeted path: `only_sections=["16","17","18"]`.
- Full DRAFT build when `protocol_number` + product present.
- Unselected section bodies preserved.
- **No** global find/replace; **no** positional `cells[0]` invent mapping in `protocol_generators_12b4.py`.
- `docx_renderer` uses semantic `only_sections` body replace.

## 13. DRAFT / REVIEW / FINAL gates

| Mode | Behaviour |
|------|-----------|
| DRAFT | Always allowed; placeholders / review markers OK |
| REVIEW | Explicit gate; blocking → `BLOCKED` |
| FINAL | Blocking / critical / unresolved required → `BLOCKED`; **never** forced PASS |

Completeness readiness is separate from gate.

## 14. Reproducibility

- Deterministic bibliography order and `REF-NNN` ids.
- Appendix inventory sorted (static forms first, then dynamic).
- Generators: `CORE_12B4_GENERATORS` overlaid onto `GENERATORS`.
- Version bump: **0.13.4**.

## 15. Limitations

- Medical rules added: **ZERO**.
- No invented study results, signatures, citations, insurance, ethics approvals, or sample size.
- STATIC_VERIFIED appendix forms are classified/preserved, not rewritten.
- Full FINAL readiness still depends on project completeness outside 12B.4.
- Binary DOCX byte-identical not required across runs.

## 16. Remaining blockers

Typical blockers that correctly prevent FINAL (not silenced):

- Missing product / design / reference for conclusion
- Empty literature sources
- Unresolved `{{…}}` required content
- Raw enum leaks, broken references, canonical N/sampling mismatches
- Draft status `BLOCKED` or blocking QA findings
- Missing signature persons when signatures required

Tests: `backend/tests/test_phase12b4_full_document.py` (≥45 meaningful cases).
