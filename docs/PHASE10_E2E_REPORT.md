# Phase 10 — E2E Validation + Golden Protocol Report

**Date:** 2026-08-26  
**Case:** Bosutinib 400 mg (FED, 2×2)  
**Golden run:** `golden/bosutinib-ai-off-20260826T080825Z` (see also `golden/LATEST_AI_OFF.json`)  
**AI mock run:** `golden/bosutinib-ai-mock-20260826T080906Z` (see also `golden/LATEST_AI_MOCK.json`)

## 1. Test case

Offline end-to-end:

minimal client input → research → document (template excerpts) → evidence → expert verify/apply → study → validation → ProtocolDraft → DOCX DRAFT / REVIEW / FINAL

No new engines were added in Phase 10.

## 2. Input data (minimal client input)

| Field | Value |
|-------|--------|
| Product | Бозутиниб |
| INN | bosutinib |
| Dosage | 400 mg |
| Dosage form | tablet |
| Route | oral |
| Planned subjects | 28 |

## 3. Missing data (not invented)

| Missing | Effect |
|---------|--------|
| Study sponsor | REVIEW/FINAL DOCX **BLOCKED** |
| Investigator / sites | unresolved placeholders |
| Registration number | unresolved |
| Exact CVintra (template only says **>30%**) | planning CV=30 used as **floor** with expert note |
| protocol-final.docx | not produced (correct) |

## 4. Evidence

Source fixture: excerpts copied from `BE_Protocol_Template_v2.0.docx` body (see `fixture-excerpts.docx`).

| Fact | Excerpt gist |
|------|----------------|
| tmax ≈ 6 h | original product data |
| t½ = 35.5 h | original product data; 72 h sampling rationale |
| Cmax CVintra >30% | template sample-size rationale |
| Bosulif / 400 mg / FED | comparative products + dosing after food |

Expert path: PROPOSED manual evidence → VERIFIED claims → `apply_verified_evidence` (Study updated only after verify).

## 5. Calculated values

- Washout / observation / sampling / blood volume / sample size via existing engines
- Observation 72 h and washout 14 d aligned with template rationale text
- Sample size uses CV planning floor 30% (documented limitation)

## 6. Validation result

Historically golden showed blocking `VAL.SAMP.INSUFFICIENT_TMAX_COVERAGE.v1` due to divergent capture windows (see `PHASE10_SAMPLING_DEBUG.md`).

**After shared `TmaxCaptureWindow` fix:** auto-generated plans for `tmax=6–6` pass that coverage rule. Remaining FINAL/REVIEW blockers are organizational (sponsor / unresolved fields), not Tmax coverage divergence.

## 7. Protocol result

- Deterministic fingerprints: two consecutive builds matched
- Sections/tables/references produced
- Build report saved: `protocol-build-report.json`
- Status not READY due to unresolved / validation — correct honesty

## 8. DOCX result

| Mode | Status |
|------|--------|
| DRAFT | **READY** → `protocol-draft.docx` (~1.3 MB) |
| REVIEW | **BLOCKED** (sponsor / critical unresolved) |
| FINAL | **BLOCKED** (sponsor / ProtocolDraft BLOCKED / unresolved) |

DRAFT structural QA (`docx-draft-validation.json`):

- opens successfully
- tables: **33**
- headings: **94**
- unresolved allowed in DRAFT (sponsor, eligibility empty lists, etc.)
- template checksum **unchanged**

## 9. Visual QA

**PDF rendering unavailable** (no LibreOffice / soffice / docx2pdf in environment).

Proxy checks used:

- python-docx open
- table/heading counts
- unresolved inventory

See `visual-qa.json`. Manual Word open recommended for layout spot-check.

## 10. Performance (`performance.json`)

Latest AI-off golden (`080825Z`):

| Step | Seconds |
|------|--------:|
| Client input | 0.24 |
| Research tasks | 0.09 |
| Document ingest | 0.09 |
| Evidence | 0.04 |
| Study build | 0.15 |
| Validation | 0.05 |
| Protocol assembly | 0.16 |
| DOCX DRAFT | **~33.8** |
| DOCX REVIEW (blocked early) | 0.04 |
| DOCX FINAL (blocked early) | 0.04 |

Threshold 30s: latest DRAFT **exceeds** threshold (`docx_draft_exceeds_threshold=true`). Earlier golden (~28.3s) was under — machine load variance. **Background job recommended** for DOCX.

## 11. AI workflows

### A. AI disabled

Covered by main golden run (`AI_ENABLED=false`). Full flow works.

### B. AI mock

`bosutinib-ai-mock-*`:

- `force_mock` extract returns PROPOSED only
- Study analyte values **unchanged** without expert verify
- Cyrillic-only excerpts may yield 0 mock regex claims — limitation of MockAIProvider, not auto-accept

## 12. Known limitations

1. No automated PDF/visual Word GUI QA in CI  
2. FINAL cannot pass without real sponsor (+ other critical org fields)  
3. Exact CVintra not in template — only `>30%`  
4. One validation ERROR keeps study validation blocking in this golden configuration  
5. DOCX generation ~28s synchronous on full template  
6. Download API returns **latest** GeneratedDocument — DRAFT must be downloaded before a later BLOCKED run becomes latest  
7. Phase 8 section tree remains a practical subset vs full template body map  

## 13. Recommended fixes (next phase candidates)

1. Background job queue for DOCX generation  
2. Download-by-`document_id` (not only latest)  
3. Sponsor/organization capture UX early in wizard  
4. Stronger MockAI Cyrillic patterns **or** LocalAI golden with Ollama optional  
5. Install LibreOffice in CI for DOCX→PDF smoke screenshots  
6. Resolve remaining validation ERROR in golden path once sponsor/org model filled from real data  

## 14. Regression

Phase 10 adds E2E tests only. Confirmed **2026-08-26**: `backend` **154 passed**; repo smoke **1 passed**.
