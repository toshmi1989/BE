# Phase 13.1 — Regulatory Evidence Foundation

**Version:** 0.14.1  
**Package status:** `PARTIAL` (not `REAL`)  
**Medical rules added:** **ZERO**  
**Auto-verify:** **NO**  
**Study / Design / Sampling / PK / Safety / ReferenceProduct mutation:** **NO**

---

## Purpose

Phase 13.1 introduces an **evidence discovery and review foundation** for regulatory sources. It classifies sources, tracks provenance, detects conflicts, and queues expert review. It does **not** invent Decision 85 (or other official) PDFs, does **not** auto-verify claims or KnowledgeRules, and does **not** mutate canonical Study objects.

## Pipeline

Entry point: `app.domain.regulatory_evidence_pipeline.run_regulatory_evidence_pipeline`

1. **Load manifest** — `load_regulatory_manifest()` from `fixtures/regulatory/manifest.json`
2. **Detect duplicates** — by `source_id`, `document_identifier`, content hash
3. **Ingest present files** — via `extract_document` when `ingestion_status=OK` (official slots are MISSING)
4. **Build claims** — RAW_EXTRACT from ingest (UNVERIFIED/EXTRACTED); interview claims as `EXPERT_INTERVIEW_CLAIM`
5. **Detect conflicts** — value conflicts + optional StudyEvidenceConflict (Study unchanged)
6. **Review queue** — pending claim reviews + priority rule candidates
7. **Coverage report** — domain gaps, verified/proposed counts, knowledge gaps

Guarantees on every run:

| Field | Value |
|-------|--------|
| `study_mutated` | `False` |
| `rules_auto_verified` | `0` |
| `package_status` | `PARTIAL` (current fixtures) |
| `coverage.verified_claims` | `0` until explicit expert verify |

## Source classes

Defined in `app.domain.regulatory_source_classes.SOURCE_CLASSES`:

| Class | Role |
|-------|------|
| `EEC_REGULATORY` | EAEU / Decision-class regulatory documents |
| `FDA_GUIDANCE` | FDA guidance |
| `EMA_GUIDANCE` | EMA guidelines |
| `REGULATORY_REPORT` | Other regulatory reports |
| `SMPC_OHLP` | SmPC / ОХЛП |
| `SCIENTIFIC_ARTICLE` | Literature (not regulation) |
| `EXPERT_INTERVIEW` | Practice / interview — **not** regulatory proof |
| `OTHER` | Fallback |

Regulatory document classes (`is_regulatory_document_class`) exclude interview and literature.

## Verification states

`SOURCE_VERIFICATION_STATUSES`:

- `UNVERIFIED` → `EXTRACTED` → `REVIEW_REQUIRED` → `VERIFIED` / `REJECTED` / `SUPERSEDED`

Hard rules:

- Ingest never sets `VERIFIED`
- `build_claim(..., verification_status="VERIFIED")` raises unless `allow_verified=True`
- `assert_not_auto_verified("VERIFIED")` raises
- High confidence does **not** imply verification

## Interview vs regulation

| | Expert interview | Regulatory claim |
|--|------------------|------------------|
| Source class | `EXPERT_INTERVIEW` | EEC / FDA / EMA / SmPC / … |
| Claim kind | `EXPERT_INTERVIEW_CLAIM` | `REGULATORY_CLAIM` |
| Fixture | `fixtures/regulatory/interview/interview_claims.json` | Official PDFs (**missing**) |
| Proof of requirement? | **No** — practice only | Only after provenance + explicit verify |

Interview seeds reference Decision 85 page *hints* from writer interview. Those hints are **not** substitutes for the official document.

## Conflicts

`app.domain.regulatory_conflicts`:

- Types: VALUE, DEFINITION, POPULATION, JURISDICTION, VERSION, TIME, METHODOLOGY
- `detect_value_conflicts` / `detect_study_evidence_conflict` leave `resolution_status=OPEN`
- `resolve_conflict_forbidden_auto` always raises — no auto-resolve in 13.1

## Review queue

`RegulatoryReviewQueue` items: claim | conflict | rule_candidate | regulatory_basis | interpretation

Approve / reject:

- Updates review item status only
- `study_mutated=False`, `canonical_mutated=False`
- Approving an interview claim does **not** make it a verified regulatory claim

Priority rule workspace (`PRIORITY_RULE_WORKSPACE`: REF-01, DESIGN-01…05, FOOD-01/02, WASH-01, ANALYTE-01) remains **PROPOSED** in the knowledge seed.

## API

Router: `/api/regulatory-evidence/*` (`app.api.regulatory_evidence`)

| Endpoint | Notes |
|----------|--------|
| `GET /meta` | Classes, statuses; `auto_verify=false` |
| `GET /manifest` | Current PARTIAL package |
| `POST /pipeline/run` | Full pipeline; no Study mutation |
| `GET /review-queue` | Expert review items |
| `GET /coverage` | Domain coverage report |
| `GET /interview-claims` | Interview ≠ regulatory |
| `POST /study-conflict/detect` | Conflict only; Study unchanged |

## Package PARTIAL

Official files **not** in repository (do not fabricate):

- Decision 85 PDF
- FDA BE guidance
- EMA BE guideline
- Reference SmPC / ОХЛП
- Post–June 2026 safety protocol files

Present: manifest structure + interview JSON → **`package_status=PARTIAL`**, never `REAL`.

## Medical rules

Phase 13.1 modules add **zero** new medical numeric thresholds and **zero** new verified KnowledgeRules. Seed catalog rules stay `PROPOSED`. Evidence tasks are discovery titles only.

## Tests

`backend/tests/test_phase13_1_regulatory_evidence.py` — §46 named tests + package/API/mutation/no-auto-verify gates.

## Related docs

- `docs/REGULATORY_EVIDENCE_COVERAGE.md` — domain coverage and missing sources
- `docs/PHASE12C_PRODUCTION_READINESS.md` — production readiness (field `regulatory_evidence_coverage`)
