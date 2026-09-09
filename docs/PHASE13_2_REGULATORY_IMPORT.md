# Phase 13.2 — Real Regulatory Evidence Import & Verification

**Version:** 0.14.2  
**Package status:** `PARTIAL` (not `REAL`)  
**Medical rules added:** **ZERO**  
**Auto-verify:** **NO**  
**Study / Design / Sampling / PK / Safety / ReferenceProduct mutation:** **NO**

---

## Purpose

Phase 13.2 adds a working **import → SourceVersion → pages → claims → review → explicit verify** pipeline on top of the 13.1 evidence foundation. Official Decision 85 / FDA / EMA / SmPC files remain **MISSING** and are never invented.

## Import & SourceVersion

Domain: `app.domain.regulatory_source_version`

| Function | Role |
|----------|------|
| `import_regulatory_file` | Validate bytes, hash, store under `fixtures/regulatory/_imported/{source_id}/`, register version |
| `copy_fixture_into_import` | Import an on-disk technical fixture |
| `list_source_versions` | List registry entries; optional `project_id` filter |
| `load_registry` / `save_registry` | JSON registry at `_imported/registry.json` |

Import statuses:

| Status | Meaning |
|--------|---------|
| `IMPORTED` | New content hash stored |
| `EXISTING_SOURCE_VERSION` | Same bytes already present |
| `VERSION_CONFLICT` | Same `document_identifier`, different hash — prior marked `SUPERSEDED` |
| `FAILED` | Validation/extraction failure (e.g. malformed PDF) |

Guarantees:

- Original file bytes preserved on disk
- `content_hash` = SHA-256
- Ingest never sets source/claim `VERIFIED`
- `study_mutated` always `False`
- Optional `base=` Path isolates registry for tests

## Provenance

Page extraction uses `extract_document` (human-facing page numbers start at **1**).

`claims_from_import` builds `RAW_EXTRACT` claims with:

- `source_id`, `source_version_id` / `document_id`
- `page` (1-based)
- `quoted_text` / `raw_extract` (exact excerpt)
- `normalized_claim` (review-facing; not a medical assertion)
- Technical fixtures tagged `TECHNICAL_FIXTURE_ONLY` in notes

`document_identifier` is stored separately from filename (filename is not assumed to be the identifier).

## Verify guards

Domain: `app.domain.regulatory_verify`

`verify_claim_explicit` / `validate_verify_payload` require:

1. Non-empty `reviewer`
2. `source_id`
3. Source version id
4. `page` for page-based claim kinds
5. Exact excerpt (`quoted_text` or `raw_extract`)
6. `normalized_claim`

Raises `VerifyGuardError` (API → **422**). Interview claims (`EXPERT_INTERVIEW` / `EXPERT_INTERVIEW_CLAIM`) raise with code `INTERVIEW_NOT_REGULATORY`.

Client `status=VERIFIED` on `/verify` does **not** bypass guards. Client `status=APPROVED` / `VERIFIED` on `/review` returns **422**.

Rule candidates from verified claims stay **`PROPOSED`** (`create_rule_candidate_from_claim`). Review actions append to an in-memory audit trail (`GET /audit`).

## Slots

Domain: `app.domain.regulatory_source_slots` — `OFFICIAL_SLOTS`, `refresh_slots`, `gaps_for_missing_required_slots`.

| Slot | Required | Typical status |
|------|----------|----------------|
| `DECISION_85` | yes | `MISSING` → `REG.DECISION85.MISSING` |
| `FDA_BE_CORE` | no | `MISSING` |
| `EMA_BE_CORE` | no | `MISSING` |
| `REFERENCE_SMPC` | yes | `MISSING` |
| `SAFETY_REFERENCE_PROTOCOL` | yes | `MISSING` |
| `TECHNICAL_FIXTURE` | no | may become `INGESTED` after import |

Slots are never auto-`VERIFIED`.

## Technical fixtures

Path: `fixtures/regulatory/test/technical_fixture_only.txt`

- Must contain / declare **`TECHNICAL_FIXTURE_ONLY`**
- Must **not** be labeled Decision 85 / FDA / EMA / SmPC verification
- Used only to exercise import → page → claim → review → explicit verify

## API (Phase 13.2 extensions)

Prefix: `/api/regulatory-evidence`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/import` | multipart file + form metadata |
| GET | `/sources`, `/sources/{id}`, `/sources/{id}/claims` | |
| GET | `/claims/{id}` | |
| POST | `/claims/{id}/review\|verify\|reject\|rule-candidate` | server-side guards |
| GET | `/slots` | slots + gaps |
| GET | `/audit` | review audit trail |

## Limitations

- Official regulatory PDFs are **not** in the repo — package remains `PARTIAL`
- KnowledgeRule seeds remain **PROPOSED** (no bulk verify)
- Verifying a claim does **not** verify KnowledgeRules or mutate Study
- Technical fixture claims are pipeline practice only, not regulatory proof
- Import registry under `_imported/` is filesystem-backed (not Alembic); use isolated `base=` in unit tests

## Tests

`backend/tests/test_phase13_2_regulatory_import.py` — 50 named tests from phase §43.

```text
python -m pytest tests/test_phase13_2_regulatory_import.py -q --tb=line
```

See also: `docs/PHASE13_1_REGULATORY_EVIDENCE.md`, `docs/REGULATORY_EVIDENCE_COVERAGE.md`.
