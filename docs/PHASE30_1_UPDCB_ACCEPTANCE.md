# PHASE 30.1 COMPLETE

**Version:** 0.35.1  
**UPDCB:** UPDCB-02-BE-2026  
**Date:** 2026-09-14  

## Verdict

**PASS** — real UPDCB package → product evidence PROPOSED → human verify → canonical promotion → contamination gate → template DOCX; AI-off control also **PASS**.

---

## FINAL REPORT

| Field | Result |
|---|---|
| **Version** | 0.35.1 |
| **UPDCB** | UPDCB-02-BE-2026 (`fixtures/study_inputs/updcb_02_be_2026`) |
| **Source package** | Checklist + Synopsis + SmPC/OХЛП (RANVEK); Golden protocol registered as `REFERENCE_OUTPUT` only — never used as content SoT |
| **AI proposals** | Created via `/product-evidence/extract`; all start `PROPOSED`; `auto_verified=false` |
| **Verified claims** | Human verify via Writer review API: pharmacological_class, mechanism, pharmacology, expected Tmax, expected t½, INN (SmPC-preferred); garbage INN proposals rejected |
| **Pharmacology** | FINAL gate requires **all** `required_for_final_pharmacology` fields; cleared only after class + mechanism + pharmacology verified from SmPC |
| **TMAX** | Verified planning value **2–4 ч** from `SRC-SMPC-RANVEK` (`Tmax) (ч) 2–4`) — not observed post-study |
| **HALF_LIFE** | Verified planning range **9–14 ч** from SmPC; washout scalar = expert upper bound **14 ч** of that range (not invented, not Golden) |
| **Applicability** | `DIRECT` set explicitly at human verify |
| **Conflicts** | Dose 15 vs 30 remains expert-controlled (`EXPERT_DECISION`); numeric PK conflicts not auto-resolved |
| **Canonical promotion** | Verified claims → `structured_facts` / `fact_sources=VERIFIED_EVIDENCE` via existing bridge |
| **Contamination** | No Bosutinib / Bosulif / CML / C26H29Cl2N5O3 / Bcr-Abl needles; page-21 area clean |
| **FINAL gate** | `MISSING_PRODUCT_PHARMACOLOGY` cleared only with full required verified set; not weakened |
| **Template renderer** | `BE_Protocol_Template_v2.0.docx` via Workspace `render_protocol_docx` |
| **DOCX** | `docs/phase30_1_artifacts/main/artifact/ART-baf1addfe764.docx` (~1.2 MB, 33 tables, 637 paragraphs, 55 PDF pages) |
| **Page 21** | Visual export includes `page_021.png`; programmatic contamination clean |
| **Traceability** | Claim → source → location → excerpt recorded; reverse DOCX-section→claim map **not implemented** (documented gap) |
| **AI-off** | `AI_ENABLED=false` → provider `disabled`; deterministic extracts still PROPOSED; human verify path works; **PASS** |
| **Full regression** | Phase 15–30.1 + Golden: **1089 passed** (docs/phase30_1_acceptance/regression_matrix.txt) |
| **Tests** | `test_phase30_*.py`, `test_phase30_1_acceptance.py`, contamination / template / manual-entry |
| **Remaining blockers** | Reverse section mapping; occasional raw enum `ACCEPTED_CALCULATION` still visible in DOCX blob (non-blocking for 30.1 PASS criteria); SmPC chemistry (formula/MW) absent → chemistry blocks cleared, not invented |
| **Production readiness** | Acceptance path proven for UPDCB; Writer must still complete dose / stats / sample-size expert gates |

---

## Acceptance criteria checklist

- [x] real UPDCB package used  
- [x] no synthetic source used for final claims  
- [x] AI / deterministic proposals created where expected  
- [x] proposals start PROPOSED  
- [x] human verification performed  
- [x] verified claims reach canonical fields  
- [x] product pharmacology blocker clears only when legitimately satisfied  
- [x] Tmax planning value handled correctly  
- [x] half-life planning value handled correctly  
- [x] applicability checked  
- [x] conflicts remain expert-controlled  
- [x] contamination gate passes  
- [x] real template renderer used  
- [x] generated DOCX is full template-based document  
- [x] no Bosutinib/CML contamination  
- [x] former page 21 clean  
- [x] DOCX opens  
- [x] AI-off works  
- [x] full regression matrix executed (results under `phase30_1_artifacts/`)  

---

## Implementation notes (wiring only — no new medical/AI engines)

1. Product evidence chunks now read package `_ingest_cache` text and persist it via `ingest_cache` on package serialize (binary SmPC text survived DB round-trip).  
2. Golden / `REFERENCE_OUTPUT` documents excluded from product-evidence chunks.  
3. Deterministic SmPC patterns: фармакотерапевтическая группа, механизм действия, Tmax/t½ table layout `(Tmax) (ч) 2–4`.  
4. `has_verified_product_pharmacology` requires **all** catalog `required_for_final_pharmacology` fields.  
5. Planning half-life **ranges** promote to facts without inventing washout scalar.  
6. Product-evidence API rehydrates after `after_mutation` so panels are not empty.  
7. Gap resolve refreshes protocol draft decision pointers to avoid stranding writers on `STALE_DECISION_SET`.

## Artifacts

- Runner: `docs/_phase30_1_acceptance_run.py`  
- Main: `docs/phase30_1_acceptance/main/acceptance_raw.json`  
- AI-off: `docs/phase30_1_acceptance/ai_off/acceptance_raw.json`  
- DOCX / PDF / page PNGs under `docs/phase30_1_acceptance/`  
