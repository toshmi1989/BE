# Phase 11C — P1 Administrative Coverage Report

**Date:** 2026-08-27  
**Version:** 0.11.2 / `DOCX.PROFILE.v3`  
**Baseline:** Phase 11B P0 + test hardening (189 tests)  
**Regression:** 208 passed

## Scope

Fully data-driven administrative / organizational protocol layer:

| # | Section | Canonical source | ProtocolDraft | DOCX |
|---|---------|------------------|---------------|------|
| 1 | Sponsor (1.2) | `Sponsor` / org `SPONSOR` | `sponsor` | ACTIVE overwrite |
| 2 | Authorized representatives (1.3) | `Person` SPONSOR_* | `sponsor_persons` | ACTIVE |
| 3 | Medical expert (1.4) | `Person` MEDICAL_EXPERT | `medical_expert` | ACTIVE |
| 4 | Investigators (1.5) | `Person` PI/INVESTIGATOR | `investigators` | ACTIVE |
| 5 | Clinical centers (1.5) | `Organization` CLINICAL_* | `investigators` | ACTIVE |
| 6 | Analytical lab (1.6) | `Organization` LAB roles | `analytical_lab` | ACTIVE |
| 7 | CRO / key orgs (1.7) | `Organization` CRO/KEY/… | `key_orgs` | ACTIVE |
| 8 | Signatures (1.8) + T04 | Persons / sponsor / PI | `signatures` + `SIGNATURES` | LABEL when data; unresolved+FINAL block when empty |
| 9 | Investigator agreement (1.9) | `Person` PI | `investigator_agreement` | ACTIVE |
| 10 | Insurance (14) | `StudyAdministration` / org INSURANCE | `financing_insurance` | ACTIVE |
| 11 | Financing (14) | `StudyAdministration` / org FINANCING | `financing_insurance` | ACTIVE |
| 12 | Publications (15) | `StudyAdministration` | `publications` | ACTIVE |

## Design rules followed

- No `N/A` fillers — missing required data → explicit `{{…}}` unresolved markers
- No reading data from legacy DOCX template bodies
- P1 admin sections no longer left as uncontrolled legacy blocks (`DYN.P1_ADMIN`)
- Canonical architecture unchanged (SubjectPlan / DisplayValueRegistry / Research Engine)

## New entities

- `Person` — authorized persons, medical expert, investigators (`organization_id` optional)
- `StudyAdministration` — insurance, financing, publication policy fields
- Alembic `0011_phase11c_admin.py`

## Validation / provenance / missing-data

- `VAL.ADMIN.SPONSOR_MISSING.v1` — ERROR, blocking FINAL/REVIEW
- `VAL.ADMIN.INVESTIGATOR_MISSING.v1` — WARNING
- `VAL.ADMIN.LAB_MISSING.v1` — WARNING
- `VAL.ADMIN.INSURANCE_MISSING.v1` — WARNING
- Generators attach `source_ids` / entity provenance where available
- Missing fields emit section-level placeholders (e.g. `{{SPONSOR.NAME}}`, `{{SIGNATURES.TABLE}}`)

## API

- `GET/POST/PATCH/DELETE /projects/{id}/persons`
- `PUT /projects/{id}/study-administration`
- Existing `PUT /projects/{id}/sponsor`

## Tests (`test_phase11c_p1.py`)

- complete sponsor, multiple orgs, investigator, medical expert, lab
- signatures, insurance, financing, publication
- missing required organization → unresolved
- no legacy placeholders in P1 sections / DOCX
- canonical consistency Synopsis ↔ Section 1 sponsor

## Known limitations

- Synopsis narrative (`SYNOPSIS_CORE`) still does not inject sponsor name into body text; sponsor appears in §1.2 and can be present in metadata/cover fills
- `LEGACY.SYNOPSIS_N46` residual unmatched synopsis cells remain REVIEW/FINAL risk (partial scrub of subject-count phrasing added in renderer)
- TOC page numbers in template may still show `46` as page refs (not subject N)
- Person model is flat (no separate FIO parts); sufficient for T04 LABEL fill

## Remaining legacy blocks

- `LEGACY.SYNOPSIS_N46` (SYNOPSIS unmatched cells)
- Static SOP blocks unchanged (T08/T09/T12/T13–T16, appendix forms, 10.2–10.4)

## Next phase

**P2** — remaining template-only rationale / procedure depth (not started)
