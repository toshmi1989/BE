# PHASE 29 — Template-based Workspace DOCX (implementation)

**Version:** 0.34.0  
**Date:** 2026-09-13  
**Status:** Implemented

## Verdict

Workspace Generate DOCX now calls the **existing** `docx_renderer.render_protocol_docx` on
`templates/protocol/BE_Protocol_Template_v2.0.docx`. No second renderer was added.
Content authority is Workspace Canonical Snapshot + approved decisions / ACCEPTED sample size /
APPROVED statistics via `workspace_assembly_context` → `assemble_protocol`.

## Deliverables

| Item | Path |
|---|---|
| Field registry | `backend/app/domain/protocol_template_registry.py` |
| Workspace → assembly ctx | `backend/app/domain/workspace_assembly_context.py` |
| Stale product scrub | `backend/app/domain/docx_stale_scrub.py` |
| Wiring | `backend/app/domain/workspace_protocol.py` → `generate_docx_artifact` |
| Tests | `backend/tests/test_phase29_template_docx.py` |
| Audit (prior) | `docs/PHASE29_TEMPLATE_AUDIT.md` |

## Acceptance checklist

1. Workspace Generate DOCX uses real template — **yes** (`shutil.copy2` inside legacy renderer)
2. Output is full BE protocol structure (not 2-page stub) — **yes** (≥30 tables, ≥400 paras, >500KB)
3. No stale Bosutinib/Bosulif for non-bosutinib studies — **yes** (registry token scrub incl. header tables; XML `w:t` check)
4. UPDCB values only from canonical/approved workspace data — **yes** (no Golden/Legacy Project content path)
5. Legacy renderer tests green — **yes** (`test_phase9_docx_unit.py`)
6. New Workspace integration tests pass — **yes** (`test_phase29_template_docx.py`)
7. Artifact stores SHA256 + source versions — **yes** (`snapshot_id`, `decision_set`, `statistics_version`, `sample_size_version`)
8. AI-off path remains functional — **yes** (deterministic assemble + template fill)
9. Preflight still blocks when required approved data missing — **yes** (existing preflight + `workspace_docx_blockers`)

## Known blockers (by design)

- `MISSING_TEST_PRODUCT` — cannot leave template Бозутиниб
- `UNRESOLVED_REFERENCE_DOSE_CONFLICT` / open CRITICAL conflicts
- Existing workspace preflight CRITICAL / stale protocol dependencies
- Required medical fields must not be silently filled with `—` / N/A

## Not done / out of scope

- Morphologically perfect RU inflection when replacing Бозутиниба → product name
- Regenerating Word TOC field results (left as Word fields per profile)
- Using Golden PКИ as content seed (forbidden)
