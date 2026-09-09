# Phase 14.1 — Binary Ingestion Hardening

**Version:** 0.15.1  
**Scope:** Hardening only — no Phase 15, no new medical decisions, no new regulatory rule activation.

## 1. Supported binary formats

| Format | Path | Notes |
|--------|------|-------|
| DOCX | first-class | paragraphs + **tables** with cell locations |
| PDF | first-class | page-aware text + heading hints |
| TXT | baseline / design dumps | not a substitute for production binary path |

Fixture layout:

```text
fixtures/study_inputs/updcb_02_be_2026/
  raw/         # binary sources (production path)
  extracted/   # text dumps (equivalence baselines only)
  expected/    # semantic + conflict expectations
  sources/     # compatibility copies
```

## 2. DOCX extraction

`ingest_docx_bytes` / `ingest_binary_file`:

- Extracts paragraphs (index, style) and tables (index, row, col, text)
- Flattens to text for deterministic field extractors
- Checklist is table-heavy — candidates retain locations like `table=1|row=3|col=1`
- Empty / unreadable DOCX → `extraction_status=FAILED` (never silent SUCCESS)

## 3. PDF extraction

`ingest_pdf_bytes`:

- Per-page text + `heading_hint`
- SmPC candidates use `page=N` provenance
- Identity/signal-oriented SmPC extraction remains (name, dose, INN, form; section presence signals)
- **Not** claimed as full SmPC semantic structuring

## 4. Classification

Runs on **binary-extracted** text (not pre-baked dumps in the production path).

Deterministic heuristics; explicit user type never silently overwritten.

## 5. Provenance

| Level | Example |
|-------|---------|
| EXACT / STRUCTURAL | `table=1\|row=3\|col=1`, `page=1` |
| SECTION | `synopsis.sampling.times` |
| DOCUMENT_ONLY | coarse fallback |

Binary and text paths may differ in location precision; semantic values must still MATCH.

## 6. Hash / version handling

- Hash = SHA-256 of **original binary bytes** (not extracted text)
- Same bytes → same hash; changed bytes → different hash
- Idempotent attach: identical hash reuses active document
- Replacement (`replace_document`): preserves old document + version; new `source_version_id`; prior candidates marked `REVIEW_REQUIRED` (verified values not silently kept authoritative)

## 7. Binary / text semantic equivalence

`study_input_equivalence.py` states:

`MATCH | BINARY_ONLY | TEXT_ONLY | VALUE_MISMATCH | TYPE_MISMATCH | NOT_COMPARABLE`

Production default: `prefer_text_dump=False` (binary-first).  
Text dumps used only for equivalence baselines (`prefer_text_dump=True`).

## 8. Conflict regression

Binary package CHECKLIST + SYNOPSIS + SMPC:

| Source | `reference_product.dose` |
|--------|--------------------------|
| Checklist DOCX | **30 mg** (`table=…`) |
| Synopsis DOCX | **15 mg** |
| SmPC PDF | **15 mg** (`page=1`) |

→ **OPEN CONFLICT** · no majority vote · `study_mutated=False`

## 9. AI-off behavior

All binary ingestion / extraction tests require `AI_ENABLED=false`.  
MockAI may only add PROPOSED enrichment after deterministic binary extraction.

## 10. Security handling

Reuses / wraps existing conventions:

- size limit (`MAX_UPLOAD_BYTES`)
- safe filename / path traversal rejection
- MIME + magic-byte checks (PDF `%PDF`, DOCX `PK`)
- forbidden executables
- corrupt binaries → controlled FAILED / HTTP 400

## 11. Known limitations

- SmPC extraction remains identity/signal-oriented
- DOCX location is table/row/col (not Word XML path IDs)
- In-memory package store unchanged from Phase 14
- No new medical decision algorithms

## Tests

`backend/tests/test_phase14_1_binary_ingestion.py` (≥50 meaningful tests).

## API

- Multipart upload validates binary then binary-ingests
- `POST .../documents/{id}/ingest` re-ingests stored binary
- Extract / candidates / conflicts / coverage unchanged contract
