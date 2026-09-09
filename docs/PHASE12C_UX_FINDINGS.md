# Phase 12C — UX findings (observations only)

**Version:** 0.14.0  
**Package:** `bosutinib-technical-v1` (`TECHNICAL_FIXTURE`)  
**Scope:** Notes from the simulated real-user workflow. **No redesign** in this phase.

---

## Confusing labels

- `TECHNICAL_FIXTURE` vs “real package” is clear in docs/manifest, but UI consumers may still show the same project chrome as a live study — easy to misread as medically validated.
- `resolution_status` values (`PROPOSED` / `UNRESOLVED` / `BLOCKED`) appear in content blocks; operators may confuse “PROPOSED content” with “approved for FINAL”.
- Gate names DRAFT / REVIEW / FINAL vs completeness `readiness` (`READY` / `READY_WITH_WARNINGS` / `BLOCKED`) are easy to conflate — completeness does not unlock FINAL.

## Duplicate fields

- Product dose appears in multiple sections (synopsis, product, conclusion). After a single change, users must trust rebuild rather than manually scanning every occurrence — stale-content detection helps but is not surfaced as a first-class UI step in this workflow.
- Subject N exists in `subjects` and `sample_size`; divergence is handled in engines but the dual fields remain cognitively heavy.

## Missing explanation

- Why FINAL is blocked is visible only by inspecting QA findings / unresolved `{{...}}` markers — no single “blocker summary” panel was exercised in the fixture workflow.
- `READY-WITH-BLOCKERS` production recommendation may sound like “almost ready for clinic” unless the TECHNICAL_FIXTURE limitation is adjacent in the UI.

## Unclear statuses

- AI OFF is the default; AI ON reports `NOT_AVAILABLE` — operators may not know whether AI was skipped, disabled, or failed.
- Ingestion `completeness=PARTIAL` on all fixture sources does not distinguish “partial by design (fixture)” from “partial because extraction failed”.

## Impossible / opaque transitions

- PROPOSED ExpertDecision cannot become FINAL content without APPROVED — correct, but the workflow test shows no guided “approve then regenerate” affordance beyond re-assembly.
- Changing one field requires full reassemble + QA; impact map exists in domain (`ContentChangeImpact`) but is not exposed as a user-facing preview in this phase.

## Hidden blockers

- Missing randomized N surfaces as `{{SUBJECTS.RANDOMIZED_N}}` inside section text — easy to miss in a long DOCX if QA is not run.
- Missing signatures / sources use markers and KnowledgeGaps; without reading section 16/18, the document can look “mostly done” in DRAFT.
- Historical CV_EVIDENCE orphan table error was a silent `table_errors=1` until root-caused — fixed, but shows registry mismatches can hide in aggregate counts.

## Missing provenance

- Fixture files carry `origin` in the manifest, but extracted text alone does not always show origin in assembled protocol blocks unless source_ids are wired on every block.
- Previous-protocol legacy values require explicit `legacy_hints` or identity compare — legacy is not auto-scanned from uploaded previous DOCX in this fixture path.

## Excessive manual work

- Operators must: upload/ingest each source type, map checklist fields, approve design/reference decisions, resolve KnowledgeGaps, run QA, review DOCX, then repeat after each canonical change.
- No background job for long DOCX builds in 12C — synchronous targeted DOCX is acceptable for tests; full-template builds may feel slow in interactive use.

---

*These findings are documentation only. No UI/UX redesign was performed in Phase 12C.*
