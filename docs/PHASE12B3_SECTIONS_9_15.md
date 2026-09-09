# Phase 12B.3 — Protocol Content Generation: Sections 9–15

**Version:** 0.13.3  
**Extends:** Phase 12B.2 (sections 5–8)  
**Medical rules added:** ZERO  
**Invented medical defaults:** ZERO  
**Invented administrative values:** ZERO

## 1. Sections

Existing `SECTION_TREE` codes only (no invented sub-numbers):

| Area | Codes | Generator overlay |
|------|--------|-------------------|
| Statistics | 9, 9.1–9.7.4 | `statistical_method`, `sample_size`, `alpha`, policies, `be_criteria`, … |
| Direct access / data | **10** only | `data_access` — no invented **10.2** tree node |
| Quality | 11 | `standard_text` → quality |
| Ethics | 12 | `standard_text` → ethics |
| Data and records | 13 | `standard_text` → data records |
| Financing / insurance | 14 | `financing_insurance` |
| Publications | 15 | `publications` |

API: `POST /api/projects/{id}/content/generate-sections-9-15`

## 2. Statistics architecture

```
SubjectPlan (protocol N)
  + SampleSizeCalculation (calculated N — labeled separately)
  + StatisticalConfig (alpha / power / BE limits / method)
  + CVSelection (+ source_study_ids)
  + Approved ExpertDecision (adaptive / Potvin / policies)
  → Section 9 blocks
```

- **SubjectPlan** owns protocol randomized / evaluable N.
- **SampleSizeCalculation** must never silently substitute randomized N.
- When both exist and differ → both are shown; QA may flag `STAT.N_SEMANTIC_MISMATCH`.
- Alpha / power / dropout / BE 80–125 **only** from canonical config or approved decision — never invented.
- Display formatting: power `80%`, alpha `0,05` via generators (no hardcoded default injection).
- Potvin / adaptive: render only with approved `POTVIN_METHOD` / `ADAPTIVE_STATS`; otherwise gap + non-final.
- CV requires provenance (`source_study_ids`); missing → `STAT.CV_MISSING_SOURCE` / `QA.STAT.MISSING_PROVENANCE`.

## 3. Administrative architecture

```
study_administration + organizations / persons
  + STATIC_VERIFIED shells (GCP boilerplate)
  → Sections 10–14 dynamic fields
```

- Section **10** is Direct access/data only (TREE code `10`).
- Study-specific monitoring / deviation thresholds are not invented.
- Missing study-specific policy → STATIC_VERIFIED shell and/or KnowledgeGap — not template-as-truth.

## 4. Ethics architecture

- Principles / consent shell: STATIC_VERIFIED only.
- Ethics committee name from `study_administration` or orgs with ethics roles — **never invented**.
- Missing committee → `{{ETHICS.COMMITTEE}}` + gap.
- Insurance may appear in §12 only if canonical insurance fields/orgs exist.

## 5. Data management

- Section 13: STATIC_VERIFIED records/confidentiality shell.
- Retention years only from canonical admin / data_records fields.
- Missing retention → `{{DATA.RETENTION_YEARS}}` — no default (e.g. 15/25 years).

## 6. Finance / insurance

- Sponsor from canonical `sponsor` / org roles.
- Insurance / financing text from `study_administration` or role-matched orgs via `org_render`.
- Missing → `{{INSURANCE.DETAILS}}` / `{{FINANCING.DETAILS}}` — no invented company, policy, or budget.

## 7. Publication

- Source: `study_administration.publication_policy` (+ contacts).
- Missing → `{{PUBLICATION.POLICY}}` — contractual clauses not invented.
- Unapproved / proposed publication as final → QA `QA.PUBLICATION.UNAPPROVED_CLAUSE`.

## 8. Content Matrix

Generators registered in `CORE_12B3_GENERATORS` and overlaid onto `GENERATORS` in assembly:

- Statistics keys: `statistical_method`, `sample_size`, `alpha`, `be_criteria`, stopping/missing/SAP/populations/ANOVA/descriptive/outliers/safety_stats
- Admin keys: `data_access`, `standard_text`, `financing_insurance`, `publications`
- **No global `heading` overlay** in 12B.3

Section codes: `CORE_12B3_SECTION_CODES`.

## 9. Provenance

Blocks carry: `section` / `block_code`, `canonical_source`, `source_ids`, `rule_id`, `expert_decision_id` (when used), `resolution_status`, `knowledge_gaps`, `display_as_final`, `content_type` (`STATIC_VERIFIED` | `CANONICAL_VALUE` | `PLACEHOLDER` | …).

## 10. ExpertDecision behavior

| Status | Behaviour |
|--------|-----------|
| APPROVED | Eligible for final (e.g. Potvin, policies, alpha) |
| PROPOSED | Draft / REVIEW REQUIRED only — `display_as_final=False` |
| REJECTED / SUPERSEDED | Not rendered as current content (`filter_decision_for_render`) |

## 11. KnowledgeGaps

Examples: missing randomized N, CV without sources, unverified Potvin, empty alpha/BE/policy fields, missing ethics committee, insurance, retention, financing, publication policy.

Never silent `N/A` or invented defaults.

## 12. QA

`run_sections_9_15_qa` adds / reuses:

- `STAT.N_RANDOMIZED_MISSING`, `STAT.N_CALCULATED_MISSING`, `STAT.N_SEMANTIC_MISMATCH`
- `STAT.CV_MISSING_SOURCE`, `QA.STAT.MISSING_PROVENANCE`
- `STAT.POTVIN_UNVERIFIED`, `STAT.ADAPTABLE_METHOD_UNVERIFIED`
- `STAT.UNAPPROVED_PARAMETERS`, `QA.STAT.UNAPPROVED_VALUE`
- `QA.CONTENT.PROPOSED_AS_FINAL`, `QA.CONTENT.REJECTED_DECISION`, `QA.CONTENT.SUPERSEDED_DECISION`
- `QA.ETHICS.*`, `QA.ADMIN.INSURANCE_UNRESOLVED`, `QA.DATA.MISSING_SOURCE`, `QA.PUBLICATION.UNAPPROVED_CLAUSE`
- `QA.CONTENT.LEGACY_VALUE` (legacy admin hints)

Cross-checks: SubjectPlan ↔ SampleSizeCalculation ↔ StatisticalConfig ↔ design; sponsor consistency on §14.

## 13. DOCX

Targeted path: `only_sections` for codes such as `9.2` / `12` / `14`.

- Unselected section bodies preserved (static template text unchanged)
- No global find/replace
- No positional cell/paragraph invent mapping in `protocol_generators_12b3.py`
- STATIC_VERIFIED blocks outside selection remain intact

## 14. Limitations

- No new statistical algorithms, Potvin B/C numerics, or sample-size formulas
- No invented alpha/power/dropout/BE limits / CV / N uplift rules
- Section 10 has no invented `10.2` SECTION_TREE child; admin sub-topics may appear only as STATIC_VERIFIED narrative blocks inside `10`
- Previous-protocol / template admin values are not truth; QA flags legacy hints
- FINAL readiness still depends on project completeness outside 12B.3
- Medical rules added: **ZERO**; invented medical defaults: **ZERO**
