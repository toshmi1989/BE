# Regulatory Evidence Coverage — Phase 13.1 / 13.2 / 13.3 (+ Phase 14 input handoff)

**Version:** 0.18.0  
**Package:** `fixtures/regulatory/` (`manifest_id`: `regulatory-evidence-pack-v1`)  
**Package status:** `PARTIAL`  
**Medical rules added in 13.1–13.3:** `ZERO`  
**Priority KnowledgeRules:** remain **PROPOSED**

### Phase 14 / 14.1 / 15 / 15.1 / 15.2 note (input / evidence / decision / research architecture)

Writer **Study Input Package** (`/api/study-input`) produces PROPOSED `CandidateStudyValue`s with provenance.  
Phase **14.1** makes **binary DOCX/PDF** the first-class ingestion path (`raw/`); text dumps under `extracted/` are equivalence baselines only.  
Phase **15.0** Decision Center (`/api/decision-center`) produces recommendations only — never silent Study mutation; PROPOSED ≠ VERIFIED; Recommended ≠ Approved.  
Missing SmPC creates KnowledgeGap `MISSING_SMPC_REFERENCE_PRODUCT` + ResearchTask `FIND_SMPC_REFERENCE_PRODUCT`.  
External SmPC research still follows Phase 13: SOURCE → SOURCE_VERSION → CLAIM → REVIEW → VERIFIED.  
These phases do **not** change Decision 85 / FDA / EMA slot conclusions below.

---

## Phase 13.3 Decision 85 status

| Capability | Status |
|------------|--------|
| Decision 85 file | **PRESENT** — `fixtures/regulatory/eec/16sr0085.doc` (MHTML) |
| Decision 85 slot | **PRESENT / INGESTED / REVIEW_REQUIRED** (never auto-VERIFIED) |
| SourceVersion import | **Available** — `import_decision85_source` / POST `/decision85/import` |
| Claim pack | **21** point-linked claims (section + chunk; page UNAVAILABLE) |
| First-batch verify | **8 VERIFIED** only with explicit `reviewer` |
| Rule candidates | **PROPOSED** only |
| Study mutation | **None** |
| FDA BE / EMA BE / SmPC | **MISSING** |
| Package `REAL` | **No** — remains `PARTIAL` |

Amendments embedded in source header: **№67 / №22 / №30** (`SOURCE_EMBEDDED`).

Typical first-batch pipeline: 21 claims · 8 verified · 13 proposed · conflicts OPEN · `study_mutated=False`.

---

## Phase 13.2 import status

| Capability | Status |
|------------|--------|
| Technical fixture import | **Available** — `fixtures/regulatory/test/technical_fixture_only.txt` (`TECHNICAL_FIXTURE_ONLY`) |
| SourceVersion registry | **Available** — `fixtures/regulatory/_imported/` + `import_regulatory_file` |
| Explicit claim verify guards | **Available** — `VerifyGuardError` / API 422 |
| Official Decision 85 | **INGESTED/PRESENT** (Phase 13.3) — MHTML, not PDF slot |
| FDA BE / EMA BE / SmPC | **MISSING** — do not invent |
| Package `REAL` | **No** — remains `PARTIAL` |

Import/verify of the technical fixture can produce a **VERIFIED** claim only via explicit human verify with full provenance. That does **not** make the regulatory package `REAL` or verify KnowledgeRules.

---

## Domain coverage table

Coverage is produced by `build_regulatory_coverage_report` / Decision 85 pipeline `coverage` / `run_regulatory_evidence_pipeline`. Domains below are evidence-discovery tasks (`REGULATORY_EVIDENCE_TASKS`), not medical PASS criteria.

| Domain | Example tasks | Official source in repo | Interview claim | D85 claims | Verified (first batch) | Gap codes / notes |
|--------|---------------|-------------------------|-----------------|------------|------------------------|-------------------|
| REFERENCE | `REFERENCE_SELECTION` | Decision 85 **INGESTED** | `INT-REF-01` | REF-01 (p.18) | 1 | Interview vs D85 conflict OPEN |
| DESIGN | 2×2, HV, replicate, long t½ | Decision 85 **INGESTED** | `INT-ENDOG-01` | DESIGN-01/02/04 (pp.15–16) | 0 | Not in first batch |
| FOOD | fasting, fed, standard meal | Decision 85 **INGESTED** | `INT-FOOD-01/02` | FOOD-01/02 (pp.44,46) | 2 | 800–1000 kcal, ~50% fat source-derived |
| SAMPLING | Tmax / AUC / terminal | Decision 85 **INGESTED** | — | 5 claims (pp.38,41) | 2 (AUC, terminal) | `REG.SAMPLING.TMAX_3PLUS3.NOT_IN_D85` |
| WASHOUT | `WASHOUT_RULE` (WASH-01) | Decision 85 soft wording | — | WASHOUT-15 (p.15) | 0 | `REG.WASH.HARD_THRESHOLD_UNCERTAIN` |
| ANALYTE | `ANALYTE_SELECTION` | Decision 85 **INGESTED** | `INT-ANALYTE-01` | ANALYTE-01/02/03 (pp.50–52) | 1 | Parent-compound general verified in batch |
| PK | primary AUC/Cmax | Decision 85 **INGESTED** | — | PK-01/02 (p.47) | 2 | Source-derived parameters only |
| STATISTICS (CV) | 90% CI, ANOVA, NTI | Decision 85 **INGESTED** | — | STAT-01..04 (pp.85–88) | 0 | `REG.POTVIN.NO_D85_SOURCE` |
| ELIGIBILITY | inclusion/exclusion | Missing beyond D85 scope | — | 0 | 0 | Discovery only |
| SAFETY | `STANDARD_BE_SAFETY` | Missing | `INT-SAFETY-01` | 0 | 0 | `REG.SAFETY.POST_2026_PROTOCOL.MISSING` |
| ETHICS | `ETHICS_CONDUCT` | Missing | — | 0 | 0 | Discovery only |
| REPORTING | `REPORTING_REFERENCES` | Missing | — | 0 | 0 | Technical fixture may feed RAW_EXTRACT |

Pipeline summary:

| Metric | Typical value |
|--------|----------------|
| `package_status` | `PARTIAL` |
| Decision 85 claims | 21 |
| Decision 85 verified (first batch) | 8 |
| Decision 85 proposed | 13 |
| Interview vs D85 conflicts | ≥ 1 OPEN |
| `knowledge_rules_verified` | `0` |
| `rules_auto_verified` | `0` |

Official slots (`OFFICIAL_SLOTS` / `GET /api/regulatory-evidence/slots`): Decision 85 **PRESENT/INGESTED**; FDA, EMA, SmPC, safety protocol — still **MISSING** until real files are supplied.

---

## Missing sources (do not invent)

| Source ID | Class | Expected / actual path | Gap / status |
|-----------|-------|------------------------|--------------|
| `SRC-DECISION85` | `EEC_REGULATORY` | `fixtures/regulatory/eec/16sr0085.doc` | **INGESTED** (Phase 13.3); manifest PDF slot path is legacy |
| `SRC-FDA-BE` | `FDA_GUIDANCE` | `fixtures/regulatory/fda/be_guidance.pdf` | `REG.FDA.MISSING` |
| `SRC-EMA-BE` | `EMA_GUIDANCE` | `fixtures/regulatory/ema/be_guideline.pdf` | `REG.EMA.MISSING` |
| `SRC-SMPC-REF` | `SMPC_OHLP` | `fixtures/regulatory/smPC/reference_smpc.pdf` | `REG.SMPC.MISSING` |
| (safety protocols) | SAFETY practice | Post–June 2026 protocol files | `REG.SAFETY.POST_2026_PROTOCOL.MISSING` |

**Do not fabricate** FDA / EMA / SmPC PDFs for tests. Decision 85 pages must not be invented (web-archive → section/point/chunk only).

Technical (non-official) fixture for import tests only:

| Path | Marker |
|------|--------|
| `fixtures/regulatory/test/technical_fixture_only.txt` | `TECHNICAL_FIXTURE_ONLY` |

---

## Interview claims list

Source: `fixtures/regulatory/interview/interview_claims.json`  
All rows: `source_type=EXPERT_INTERVIEW`, `is_regulatory_document=false`.

| Claim ID | Domain | Field | Interview hint |
|----------|--------|-------|----------------|
| `INT-REF-01` | REFERENCE | `reference_selection` | Decision 85 p.18 |
| `INT-FOOD-01` | FOOD | `food_condition` | Decision 85 p.44 |
| `INT-FOOD-02` | FOOD | `fed_meal` | Decision 85 p.46 |
| `INT-ENDOG-01` | DESIGN | `endogenous` | Decision 85 pp.41,56 |
| `INT-ANALYTE-01` | ANALYTE | `analyte_selection` | Decision 85 p.50 §6 III |
| `INT-SAFETY-01` | SAFETY | `be_safety` | Protocols after June 2026 (practice only) |

Interview claims remain **practice evidence**. Uploading Decision 85 does **not** upgrade them to VERIFIED. Phase 13.2/13.3 reject interview verify with `INTERVIEW_NOT_REGULATORY`. Conflicts with D85 stay OPEN.

---

## Priority rule workspace (still PROPOSED)

From `PRIORITY_RULE_WORKSPACE` / `KNOWLEDGE_RULE_SEEDS`:

| Rule code | Status |
|-----------|--------|
| REF-01 | PROPOSED |
| DESIGN-01 | PROPOSED |
| DESIGN-02 | PROPOSED |
| DESIGN-03 | PROPOSED |
| DESIGN-04 | PROPOSED |
| DESIGN-05 | PROPOSED |
| FOOD-01 | PROPOSED |
| FOOD-02 | PROPOSED |
| WASH-01 | PROPOSED |
| ANALYTE-01 | PROPOSED |

VERIFIED KnowledgeRules still require regulatory basis and/or evidence claim IDs and/or source IDs (`assert_verified_provenance`). Phase 13.3 rule candidates from verified D85 claims stay **PROPOSED**.

---

## How to refresh coverage

```text
POST /api/regulatory-evidence/pipeline/run
GET  /api/regulatory-evidence/coverage
GET  /api/regulatory-evidence/slots
POST /api/regulatory-evidence/import
POST /api/regulatory-evidence/decision85/import
POST /api/regulatory-evidence/decision85/pipeline
GET  /api/regulatory-evidence/decision85/claims
```

Or in Python:

```python
from app.domain.decision85_pipeline import run_decision85_verification_pipeline
result = run_decision85_verification_pipeline(verify_first_batch=True, reviewer="expert")
print(len(result["claims"]), len(result["verified_claims"]), result["study_mutated"])
```

See also: `docs/PHASE13_1_REGULATORY_EVIDENCE.md`, `docs/PHASE13_2_REGULATORY_IMPORT.md`, `docs/PHASE13_3_DECISION85_VERIFICATION.md`, `docs/PHASE14_REAL_WRITER_INPUT_WORKFLOW.md`, `docs/PHASE14_1_BINARY_INGESTION_HARDENING.md`, `docs/PHASE15_DECISION_ENGINE.md`.
