# DOCX Dynamic Requirements (Phase 10 → future phases)

**Date:** 2026-08-26  
**Companion:** `docs/DOCX_COVERAGE_MATRIX.md`  
**Constraint:** Audit / requirements only — no implementation in this pass.

Derived from Phase 10 state: ProtocolDraft subset + 19 DOCX active section replaces + 7 mapped tables vs ~107-page template (33 tables, 93 body headings).

---

## 1. Goal

Define what must become Study/ProtocolDraft-driven versus what may remain template-static, without inventing Research Engine, AI, or new generators in this document’s delivery.

---

## 2. Already linked to Study / ProtocolDraft (keep)

### DOCX body replaces (`ACTIVE_SECTION_CODES`)

`1.1`, `1.2`, `2.1.1`, `2.1.2`, `2.5`, `2.6`, `2.10`, `2.11`, `2.12`, `4.1`, `4.2`, `4.4.2`, `5.1`, `5.2`, `5.3`, `6.2.1`, `8.1`, `9.1`, `9.2`

### Tables wired

| table_id | key | notes |
|---|---|---|
| T01 | STUDY_METADATA | partial light-fill |
| T03 | SYNOPSIS_N | partial |
| T05 | TEST_PRODUCT | OK |
| T06 | REFERENCE_PRODUCT | OK |
| T07 | PK_PARAMETERS | OK |
| T10 | BLOOD_SAMPLING | OK |
| T17 | CV_EVIDENCE | conditional on CV rows |

### Draft-only (exists in ProtocolDraft, **not** yet pushed into DOCX body)

Examples: `SYNOPSIS`, `1.3`–`1.9`, `3`, `4.3`, `4.4`, `4.4.1`, `4.5`, `6.1`, `6.1.5`, `7.1`, `7.3.1`, `9.3`, `9.7.2`, `11`–`18`, etc.

**Requirement:** promote selected draft generators onto `ACTIVE_SECTION_CODES` (or equivalent mapping) — do not duplicate logic in the renderer.

---

## 3. Remain static (default)

| Area | Reason |
|---|---|
| T02 Abbreviations | Site glossary; optional later |
| T11 Screening checklist | Stable panel unless product-specific |
| T13–T16 Safety scales | Regulatory SOP tables |
| T18–T33 Appendix forms | AE/SAE/pregnancy forms — preserve |
| 8.2.1–8.5 most narrative | Standard safety/AE procedures |
| 10.2–10.4, 11–13, 15 boilerplate | Admin/QA/ethics/publication SOPs |
| 6.2.2 / 6.2.3 / 6.3* | Usually site SOP unless study-specific overrides |

Static sections may still receive **token** fills (protocol number, product name) without full body regeneration.

---

## 4. Must become dynamic (requirements backlog)

Prioritized by Study coupling and golden-case pain.

### P0 — Close draft→DOCX gaps for existing generators

| section_code | required source | generator | blocking fields | notes |
|---|---|---|---|---|
| 3 | study objectives | objectives | objectives text | activate DOCX replace |
| 4.3 | design sequences / blinding | randomization | DESIGN sequences | activate DOCX replace |
| 4.4 | design, food, products | treatment | products, food | activate DOCX replace |
| 4.4.1 | design.periods | stages | periods | activate DOCX replace |
| 4.5 | observation, washout | participation_duration | durations | activate DOCX replace |
| 6.1 | design, products | treatment_detail | products | activate DOCX replace |
| 6.1.5 | washout | washout_procedure | WASHOUT | activate; crossover-only |
| 7.1 | pk_parameters, analytes | eval_parameters | PK list | activate DOCX replace |
| 7.3.1 | analytes / method | bioanalysis | method | activate DOCX replace |
| 9.3 | stats.alpha | alpha | ALPHA | activate DOCX replace |
| 9.7.2 | BE limits | be_criteria | BE.LOWER/UPPER | activate DOCX replace |
| 18 | sources | literature | SOURCES.LIST | activate DOCX replace; map SOURCES table |
| 1.3–1.9 | organizations | org_details / signatures | SPONSOR_*, INVESTIGATORS, labs, SIGNATURE.* | model + DOCX |
| T04 | organizations | signature_table | signature rows | implement fill |

### P1 — Template headings with no SECTION_TREE entry (new draft sections + DOCX)

| section_code | required source | generator needed | type |
|---|---|---|---|
| 2.2 | evidence / SmPC summaries | preclinical_clinical_summary | dynamic molecule |
| 2.3 | risks from sources + expert | risk_benefit | dynamic |
| 2.4 | product dosage / regimen | dose_rationale | dynamic |
| 2.7 | sources | rationale_literature | conditional |
| 2.8 | pharmacology narrative | pharmacology | dynamic molecule |
| 2.9 | extended product attrs | test_product_details | dynamic |
| 4.6 | stop / withdrawal rules | stop_rules | conditional |
| 4.7–4.7.3 | products + pharmacy | drug_accountability* | dynamic/static mix |
| 4.8–4.8.3 | design blinding policy | randomization_codes / blinding | dynamic/conditional |
| 4.9 | primary data / CRF list | primary_data_list | static/conditional |
| 6.1.1–6.1.4, 6.1.6–6.1.10 | procedures, periods, sample prep | period_* / procedures_* | dynamic/conditional |
| 6.2 (parent) | allowed/prohibited meds | treatment_restrictions | conditional |
| 7.2, 7.3, 7.3.2–7.3.4 | bioanalysis depth | analytical_* | dynamic/static |
| 8.2, 8.2.3 | safety schedule / labs | safety_methods / safety_labs | dynamic/static |
| 9.4–9.7.1*, 9.7.3 | stats policy detail | stats_* generators | dynamic/static |
| 10.1 | completion policy | study_completion_admin | conditional |

### P2 — Tables to dynamize

| table_id | required source | required generator | priority |
|---|---|---|---|
| T04 | organizations / roles | signature_table | P0 |
| T08 | design schedule / periods | schedule_of_assessments | P1 |
| T09 | lab panel | lab_parameters_table | P1 |
| T12 | food timing | meal_timing_table | P1 |
| T01/T03 | full synopsis/cover map | deepen existing fills | P0/P1 |

---

## 5. Conditional rules (when dynamic)

| Condition | Sections / tables affected |
|---|---|
| `design` crossover / replicate | 2.12, 6.1.5, 6.1.6, washout tables/text |
| `food` FED/FASTING | 2.5, 6.2.1, T12, period dosing text |
| CV studies present | T17 |
| Parallel design | hide/skip washout period-2 blocks |
| Missing organizations | 1.2–1.9, T04 → unresolved; blocks FINAL |

---

## 6. Dependencies (shared Study nodes)

Any dynamic section must bind to existing Study SSOT — do not fork values:

- `study` (protocol_number, title, dates, country)
- `product` / `reference_product`
- `design` (type, periods, sequences, blinding)
- `food`
- `subjects` / `sample_size` / `cv_selection`
- `analytes` / `pk_parameters` / `observation` / `washout` / `sampling` / `blood_volume`
- `eligibility` lists
- `organizations` / sponsor / signatures (**model gap today**)
- `sources` / evidence (for 2.2–2.8, 18 — content provenance; not auto-AI)

---

## 7. Blocking fields (FINAL / REVIEW)

Already observed in golden DRAFT:

- `{{SPONSOR.NAME}}`, `{{SPONSOR_PERSONS.DETAILS}}`, `{{SIGNATURE.SPONSOR}}`, `{{STUDY.COUNTRY}}`
- Eligibility empties: `{{ELIGIBILITY.NON_INCLUSION}}`, `{{ELIGIBILITY.EXCLUSION}}`
- Org placeholders: investigators, lab, financing, etc.

Expanding dynamic coverage without org/eligibility capture will increase honest `{{…}}` surface — capture UX required before FINAL.

---

## 8. Non-goals (explicit)

- No Research Engine work in this requirements pass  
- No AI auto-writing of 2.2/2.8 narratives as verified text  
- No new generators implemented here  
- No Phase 11 implementation kickoff in this document  

---

## 9. Recommended sequencing (for later Phase 11+ planning only)

1. Org/signature model + T04 + activate 1.3–1.9 DOCX  
2. Activate existing draft generators into DOCX (P0 list)  
3. T08/T09/T12 + period procedure sections (6.1.*)  
4. Rationale molecule sections 2.2–2.4, 2.7–2.9 (expert/source-backed)  
5. Deep stats 9.3–9.7 and bioanalysis 7.2–7.3.*  
6. Leave appendix forms static  

---

## 10. Coverage snapshot (from matrix)

| Metric | Count |
|--------|------:|
| total sections (audited) | 118 |
| generated dynamically (DOCX core) | 19 |
| static | 52 |
| conditional | 14 |
| not implemented (gaps) | 61 |
| total tables | 33 |
| dynamic tables (wired, incl. partial/conditional) | 7 |
| static tables | 22 |
| not implemented tables | 4 |

**STOP.**
