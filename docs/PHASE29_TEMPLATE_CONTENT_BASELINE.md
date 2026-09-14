# PHASE 29 — Template Content Baseline (semantic)

**Version:** 0.34.1  
**Date:** 2026-09-14  
**Template:** `templates/protocol/BE_Protocol_Template_v2.0.docx`  
**Inventory:** `docs/_phase29_template_inventory.json` → `phase29_2_semantic_audit`

## Policy

| Classification | Final DOCX rule |
|---|---|
| UNIVERSAL_STATIC | Preserve (structure, generic BE procedure text) |
| DYNAMIC | Populate from canonical / approved workspace data |
| PRODUCT_SPECIFIC | CLEAR if no verified study evidence; else populate from VERIFIED / APPROVED / CANONICAL only |
| UNKNOWN | Must not silently remain — BLOCK |

Sources allowed for PRODUCT_SPECIFIC: VERIFIED evidence, APPROVED decision, CANONICAL study fact.  
Forbidden: template example, Golden PКИ, Legacy Project, hardcoded Upadacitinib, unsupported LLM text.

## Audit counts (Phase 29.2)

| Class | Count |
|---|---|
| Inventoried blocks | 188 |
| PRODUCT_SPECIFIC | 81 |
| UNKNOWN (marker-weak) | 15 |
| UNIVERSAL headings | 92 |
| Content fingerprints | 71 |

## High-risk PRODUCT_SPECIFIC sections

| Section (template) | Category | Example dependency | Replacement strategy |
|---|---|---|---|
| 2.1 Наименование и описание… | PHARMACOLOGY / DISEASE / MECHANISM | Bosutinib = TKI for CML; Bcr-Abl/Src | CLEAR_OR_BLOCK until verified pharmacology for current product |
| 2.1 chemical name / formula / MW | CHEMICAL_FORMULA | `C26H29Cl2N5O3`, 530,45; dichlorophenyl quinazoline | CLEAR_OR_BLOCK (never rename-only) |
| 2.1.1 / 2.1.2 product tables | PRODUCT + attrs | Bosutinib / Bosulif identity | DYNAMIC from product facts; unresolved `{{TEST_PRODUCT.*}}` stay gated |
| 2.8 Фармакологические свойства бозутиниба | PHARMACOLOGY | Named bosutinib properties | CLEAR_OR_BLOCK + neutralize heading |
| 2.9–2.12 justifications | PRODUCT_SPECIFIC PK/dosing narrative | Example product PK / washout justifications | CLEAR_OR_BLOCK or populate from verified PK facts |
| 4.x / 6.x / 10.x cells with names | PRODUCT_NAME / dosing examples | 400 mg bosutinib sample | CLEAR fingerprint blocks; token scrub secondary |
| Headers | PRODUCT_NAME | «Исследуемый препарат: Бозутиниб…» | Replace with study product identity |

## Protection layers

1. **Primary:** `template_contamination` registry + `clear_product_specific_contamination`  
2. **Secondary:** `docx_stale_scrub` name tokens  
3. **Tertiary:** `scan_docx_contamination` + XML package scrub; fail closed

## Preflight

`CRITICAL_TEMPLATE_CONTAMINATION`  
- DRAFT: OK when all PRODUCT_SPECIFIC blocks are mapped to CLEAR_OR_BLOCK (or evidence available)  
- FINAL: OK only with verified pharmacology sources (cleared empty pharmacology not accepted for FINAL)

## Notes

- Token rename of «Бозутиниб» → «Upadacitinib» is **insufficient** (Phase 29.1 page 21).  
- Fingerprints: `docs/_phase29_2_fingerprints.txt` / inventory `contamination_fingerprints`.
