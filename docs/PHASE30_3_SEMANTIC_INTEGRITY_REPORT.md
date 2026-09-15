# PHASE 30.3 COMPLETE — DOCX Semantic Correctness Hardening

**Version:** 0.35.3

## Goal

Eliminate hybrid DOCX output (partial mapping + stale template + placeholders)
via typed field mapping, semantic integrity gates, and FINAL fail-closed policy.
No second renderer. No template redesign. No new AI features.

## Root cause fixed

Cover T01 was filled via `STUDY_METADATA` English rows + **ordinal fallback**.
When Russian labels did not match, row 5 (`Лекарственная форма`) received
`Randomized N` (e.g. **56**).

## Changes

| Area | Fix |
|------|-----|
| P0.1 Typed mapping | `semantic_field_types.py`, `cover_mapping.py`; ordinal fallback **off** |
| P0.2 Stale content | Dose/date scrub in `docx_stale_scrub`; integrity `STALE_TEMPLATE_DOSE_400` |
| P0.3 Placeholders | `UNRESOLVED_TEMPLATE_PLACEHOLDER` CRITICAL for FINAL |
| P0.4 Block classes | `template_block_registry.py` |
| P0.5 Mapping registry | Cover + required dynamic blocks catalogued |
| P0.6 Sampling | Table columns: # / time / volume / deviation / condition |
| P0.8 Subjects | Separate evaluable / randomized / screened — never shared into dosage_form |
| P0.9 Washout | Cross-section invariant `WASHOUT_INCONSISTENT` |
| P0.10 Date/version | Template date scrub; missing date blocks FINAL |
| P0.17 PK table ref | Human display text (no `таблица PK_PARAMETERS`) |
| P0.18 TOC | `docx_toc.refresh_toc_fields` (LO or clear stale page numbers) |
| P0.19–P0.23 | `docx_semantic_integrity` + FINAL semantic preflight |
| P0.24 Tests | `tests/test_phase30_3_docx_semantic_integrity.py` |

## Acceptance snapshot

| Check | Status |
|-------|--------|
| no wrong typed mapping (dosage_form≠N) | PASS (gate + typed cover) |
| no stale 400 mg in FINAL | PASS (integrity CRITICAL) |
| no stale washout mismatch | PASS (integrity CRITICAL) |
| no stale date in FINAL | PASS (integrity CRITICAL) |
| unresolved placeholders FINAL | BLOCK |
| internal table IDs | BLOCK |
| sampling / eligibility / bioanalysis / stats | FINAL preflight BLOCK if missing |
| TOC refreshed | PASS (clear/LO) |
| contamination | retained from 29.2 |
| FINAL fail-closed | PASS |
| DRAFT still exportable when only FINAL gaps | PASS |

## Production readiness

**DRAFT:** usable after assemble; template example cleared/scrubbed; wrong
subject→dosage_form mapping blocked even in DRAFT.

**FINAL:** blocked until typed sources present, placeholders gone, stale
content cleared, washout consistent, TOC refreshed, contamination OK.

Phase 31: **not started** (per charter).
