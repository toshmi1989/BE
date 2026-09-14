# PHASE 30.2 COMPLETE — Traceability polish & human-facing cleanup

**Version:** 0.35.2

## Goal

Remove remaining technical enum leakage, add section-level DOCX↔claim reverse
traceability for writer preview, and keep all Phase 29–30.1 safeguards.

## Changes

### 30.2.1 — ACCEPTED_CALCULATION leak

- Registered `ACCEPTED_CALCULATION` → «Расчёт подтверждён» in
  `display_value_registry` (`selection_method` + `general`).
- Added to `RAW_ENUM_CODES` and `TECHNICAL_TOKEN_LABELS_RU`.
- Protocol tables already call `resolve_display(..., context="selection_method")`
  — raw enum no longer falls through as display text.
- Frontend `writerLabels.ts` maps the same label for audit/UI.
- Regression: `tests/test_phase30_2_traceability.py`

Internal API enum / assembly context value **unchanged**
(`selection_method: "ACCEPTED_CALCULATION"` stays internal).

### 30.2.2 — Section-level DOCX → claim traceability

New module `protocol_traceability.py` emits:

| Field | Meaning |
|-------|---------|
| `protocol_section_id` | Preview/protocol section code |
| `canonical_field` | Canonical field path |
| `claim_id` | ResearchClaim id when present |
| `decision_id` | Linked decision when matched |
| `source_id` / `source_label` / `source_type` | Evidence source |
| `location` | Claim location or excerpt |

Wired into `build_preview_from_draft` as `section_traceability` and per-section
`sources[]`. Artifact generate response includes `section_traceability`.

**Scope:** section-level only — no fake paragraph provenance.

### 30.2.3 — Writer Protocol Preview «Источник»

- Preview sections show collapsible **Источник** with field, source, claim,
  status, provenance labels.
- Side panel bindings include source line when mapped.

### 30.2.4 — AI provenance

Provenance flags distinguish:

- 🤖 AI proposal (`verification_status=PROPOSED`)
- ✓ Verified by expert
- ✓ Approved for protocol

AI confidence is surfaced separately and is **not** verification.
UI updates: ProductEvidenceReview, GapsPanel.

### 30.2.5 — Final DOCX

`scrub_docx_technical_enums` runs after contamination/token scrub on generated
DOCX, replacing known internal tokens (incl. `ACCEPTED_CALCULATION`) with
human labels before store/scan.

### 30.2.6 — Missing data

Unchanged fail-closed policy: no invention of formula/MW; chemistry fields
absent from traceability when not in facts/claims.

## Regression

| Suite | Result |
|-------|--------|
| Phase 29 / 29.2 / 30 / 30.1 / 30.2 | 45 passed |
| Phase 30.2 unit | 11 passed |
| Full suite | 2090 passed |

## Acceptance checklist

- [x] ACCEPTED_CALCULATION never leaks as raw enum to writer/DOCX tables
- [x] Section-level DOCX↔claim traceability exists
- [x] Writer can inspect Источник for mapped content
- [x] AI proposal vs verified clearly separated
- [x] Missing data remains fail-closed
- [x] UPDCB path / contamination / AI-off gates preserved (no gate weakening)
- [x] Phase 29–30.2 regression pass
- [x] Full regression pass

## Remaining blockers

- Paragraph-level / DOCX XML bookmark provenance not implemented (by design).
- Formula/MW still missing when SmPC does not contain them — correctly blocked,
  not invented.
- Claim IDs are shown in writer preview when useful for support; they are
  scrubbed/not emitted as body text in final DOCX technical-token pass
  (workflow IDs are not written into narrative).
