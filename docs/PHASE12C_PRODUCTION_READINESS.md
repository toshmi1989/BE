# Phase 12C — Production Readiness / Real Protocol Validation

**Version:** 0.14.0  
**Test package classification:** `TECHNICAL_FIXTURE`  
**Package path:** `fixtures/packages/bosutinib-technical-v1/`  
**Medical rules added:** ZERO  
**Invented medical / administrative / reference values:** ZERO  
**FINAL forced PASS:** NO  
**Final recommendation:** **READY-WITH-BLOCKERS**

---

## 1. Test package

No real multi-document regulatory submission package exists in-repo. Phase 12C uses a clearly marked **TECHNICAL_FIXTURE**:

| Item | Value |
|------|--------|
| Package ID | `bosutinib-technical-v1` |
| Classification | `TECHNICAL_FIXTURE` |
| Medical validation | `false` (forced for TECHNICAL_FIXTURE) |
| Sources | Design notes (txt), test/reference product (txt), checklist (json), CV evidence (json), previous-protocol identity (json) |
| Provenance | Golden Bosutinib snapshot fields + Phase 10 template body excerpts — not new medical claims |

This package validates the **pipeline**, not medical correctness of a live study.

## 2. Input manifest

Module: `app.domain.real_protocol_input_manifest`

- `load_manifest(package_dir)` / `build_default_technical_manifest()`
- `RealProtocolInputManifest` with typed `InputSourceEntry` rows
- File SHA-256 refreshed for existing files; missing files → `completeness=MISSING`
- `REPO_ROOT = parents[3]` from `backend/app/domain/*.py` → repository root

## 3. Real workflow

Simulated end-to-end (see `test_complete_end_to_end_pipeline` / `test_user_workflow_simulation`):

1. Create project context  
2. Ingest design / product / reference / checklist / CV via `extract_document`  
3. Review evidence provenance (source_id retained in fixture JSON)  
4. ExpertDecision APPROVED required for final render (`filter_decision_for_render`)  
5. Assemble protocol → full QA → DRAFT DOCX  
6. Change one canonical field → content impact → reassemble → QA again  

JSON package files are ingested as plain text (`.json` treated like `.txt` by `extract_document`). DOCX coverage uses Phase 10 `build_fixture_docx_bytes()` (template excerpts).

## 4. AI-off results

| Item | Result |
|------|--------|
| `Settings.ai_enabled` default | `False` |
| Assemble + full QA + targeted DOCX | **PASS** |
| AI proposals mutate Study | **No** — PROPOSED decisions do not pass `filter_decision_for_render` |

## 5. AI-on results

| Item | Result |
|------|--------|
| AI ON | **NOT AVAILABLE** (default `ai_enabled=False`; external AI also off) |
| Production report `ai_on.status` | `NOT_AVAILABLE` |

No silent AI → canonical mutation path was exercised with simulated PROPOSED decisions.

## 6. Evidence extraction

- Design / product / reference txt extract pages + chunks  
- Checklist / CV JSON parse after text extract  
- CV fixture mirrors golden path (`Cmax` CV 35.0 FED) — not a new medical claim  
- EvidenceClaim / source_id wiring remains as in 12A–12B (no new medical rules)

## 7. Canonical consistency

- Single `ctx["sampling"].points` list (no parallel SamplingPlan list)  
- Subject N / sampling times / AUC metric checked via `run_full_document_qa`  
- Missing `planned_randomized_n` → `{{SUBJECTS.RANDOMIZED_N}}` / FINAL **BLOCKED**

## 8. Change propagation

Module: `app.domain.content_change_impact`

- `compute_content_change_impact` maps field → sections / tables / QA families  
- Dose / sponsor / sampling changes mark rebuild + affected sections  
- `detect_stale_content` finds old values still present when canonical expects new  
- Unaffected STATIC_VERIFIED appendix content preserved across sponsor change

## 9. Previous protocol diff

- Fixture `previous_protocol_identity.json` with synthetic legacy identity  
- `compare_identity_maps` → `LEGACY_SUSPECTED`  
- `run_full_document_qa(..., legacy_hints=...)` flags legacy strings in document text  

Legacy is never auto-deleted or treated as truth.

## 10. Full DOCX QA

- Full assemble + `run_full_document_qa` (DRAFT)  
- Targeted DOCX (`only_sections` 16/17/18) READY in DRAFT  
- Scans: no broken “Reference source not found”; no raw enum leaks on clean ctx  
- Placeholders may exist on incomplete fixture; **FINAL is BLOCKED** when unresolved markers remain (`test_docx_no_placeholders`)

## 11. Table error root cause

**Root cause (pre-fix):** §9.2 generator emitted a `TABLE` block with `table_key=CV_EVIDENCE` even when `build_tables` had no CV rows → `QA.TABLE.UNRESOLVED` → `table_errors=1`.

**Fix:** In `protocol_generators_12b3.py` (and assembly path), emit `CV_EVIDENCE` TABLE **only if** `build_tables` includes that key.

| Scenario | Expectation |
|----------|-------------|
| No `cv_studies` | No CV_EVIDENCE TABLE block; no CV_EVIDENCE table_errors |
| With `cv_studies` | CV_EVIDENCE registered in table registry and emitted |

## 12. Reference integrity

- `build_bibliography` + `find_duplicate_reference_ids` / `find_orphan_source_ids`  
- Dedup by source_id / document_identifier / citation  
- Empty sources → `{{SOURCES.LIST}}` gap (no invented citations)

## 13. Gate results

| Mode | Behaviour (unchanged) |
|------|------------------------|
| DRAFT | Gate READY; review markers allowed |
| REVIEW | BLOCKED on critical / blocking findings |
| FINAL | BLOCKED on critical / placeholders / gaps — never forced PASS |
| Completeness | Informational `assess_document_completeness` — does not replace gates |

Incomplete admin / signatures / sources → explicit gaps / unresolved markers.

## 14. Performance

Rough timings recorded in tests (`PERF` dict / readiness report `performance`):

- Ingestion (txt/json): typically sub-second  
- Full assemble + full QA + targeted DOCX: measured; fail only if absurd (>~2–3 min)

If synchronous full-template DOCX ever exceeds ~30s in production, prefer a background job — queue not added in 12C.

## 15. UX findings

See `docs/PHASE12C_UX_FINDINGS.md` (observations only; no redesign).

## 16. Limitations

- Package is **TECHNICAL_FIXTURE_ONLY** — not medical validation  
- AI ON path not available in default configuration  
- Fixture sources are PARTIAL completeness surrogates  
- Full FINAL medical readiness not claimed  
- TECHNICAL_FIXTURE cannot claim PRODUCTION-READY medical status

## 17. Production blockers

- FINAL gate remains BLOCKED for incomplete / unresolved content (by design)  
- No real regulatory input package  
- AI ON not available for dual-path validation  
- Checklist / CV are technical surrogates, not sponsor originals  
- Medical validation explicitly false

## 18. Recommendation

**READY-WITH-BLOCKERS**

Pipeline through assemble → QA → DRAFT DOCX is production-*capable* for technical validation. Do **not** treat this run as medical production readiness. Clear blockers remain until a real package, AI-on availability (if required), and FINAL-clean content are present.
