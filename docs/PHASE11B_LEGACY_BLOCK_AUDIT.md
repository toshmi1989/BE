# Phase 11B — Legacy Block Audit (P0)

**Date:** 2026-08-26  
**Template:** `BE_Protocol_Template_v2.0.docx`  
**Scope:** P0 sections only (1.1–1.9, 2.2–2.4, 2.7–2.12, 3, 4.3–4.9, 6.1–6.3.*, 7.*, 8.1–8.5, 9.*, 18 + T04/T08/T09/T12).  
**Source of truth:** Canonical Study Snapshot + Verified Evidence + Calculated Results + Static Verified Blocks.

## Legend

| NEW STATUS | Meaning |
|---|---|
| DYNAMIC | Body/table driven from ProtocolDraft / snapshot |
| STATIC_VERIFIED | Intentionally preserved template content |
| CONDITIONAL | Preserved or rebuilt depending on study flags |
| LEGACY_UNCONTROLLED | Residual risk — not silently replaced |

| ACTION | Meaning |
|---|---|
| REPLACED | Section body cleared and rewritten from draft |
| PRESERVED | Template content kept |
| REMOVED | Former LEGACY flag lifted because content is now controlled |

---

## A. Section blocks (P0)

| Block | OLD STATUS | NEW STATUS | ACTION | REASON |
|---|---|---|---|---|
| 1.1 Protocol metadata | DOCX_REPLACED | DYNAMIC | REPLACED | Study snapshot |
| 1.2 Sponsor | PARTIAL / placeholder | DYNAMIC | REPLACED | Sponsor / org SPONSOR |
| 1.3 Authorized persons | LEGACY_UNCONTROLLED | DYNAMIC | REPLACED | Org roles; unresolved if empty (blocks REVIEW/FINAL) |
| 1.4 Medical expert | LEGACY_UNCONTROLLED | DYNAMIC | REPLACED | Org MEDICAL_EXPERT |
| 1.5 Investigators / sites | LEGACY_UNCONTROLLED | DYNAMIC | REPLACED | Org INVESTIGATOR / CLINICAL_* |
| 1.6 Analytical lab | LEGACY_UNCONTROLLED | DYNAMIC | REPLACED | Org BIOANALYTICAL_LAB |
| 1.7 Key organizations | LEGACY_UNCONTROLLED | DYNAMIC | REPLACED | Org CRO / KEY / OTHER |
| 1.8 Signatures | LEGACY + T04 static | DYNAMIC | REPLACED | Narrative + T04 LABEL fill when data present |
| 1.9 Investigator agreement | LEGACY_UNCONTROLLED | DYNAMIC | REPLACED | Investigator org data |
| 2.2 Clinical/preclinical | LEGACY (template molecule text) | DYNAMIC | REPLACED | Verified evidence only; else `{{EVIDENCE.*}}` |
| 2.3 Risk/benefit | LEGACY | DYNAMIC | REPLACED | Verified evidence only |
| 2.4 Dose rationale | LEGACY | DYNAMIC | REPLACED | Product.dosage + evidence; no invent |
| 2.7 Literature basis | LEGACY | DYNAMIC | REPLACED | Evidence / sources list |
| 2.8 Pharmacology | LEGACY | DYNAMIC | REPLACED | Verified evidence only |
| 2.9 Test product details | LEGACY | DYNAMIC | REPLACED | Product model |
| 2.10–2.12 | Already DYNAMIC (11A) | DYNAMIC | PRESERVED | Canonical washout/observation/ref |
| 3 Objectives | DRAFT_ONLY / non-Heading | DYNAMIC | REPLACED | Study objectives; heading via «1 абзац» |
| 4.3–4.5 | DRAFT_ONLY | DYNAMIC | REPLACED | Design / food / sampling snapshot |
| 4.6 Stop rules | LEGACY | DYNAMIC | REPLACED | Eligibility exclusion + placeholder if thin |
| 4.7–4.7.3 Accountability | LEGACY | DYNAMIC | REPLACED | Product / reference identity |
| 4.8–4.8.3 Codes / blinding | LEGACY | DYNAMIC | REPLACED | Design blinding via DisplayValueRegistry |
| 4.9 Primary data | LEGACY | DYNAMIC | REPLACED | Framework + explicit unresolved CRF list if unknown |
| 6.1–6.1.10 Procedures | LEGACY | DYNAMIC | REPLACED | Design/food/washout/sampling canonical |
| 6.2–6.3.1 Restrictions | Mixed | DYNAMIC / STATIC_VERIFIED mix | REPLACED | Food DYNAMIC; activity/contraception/compliance STATIC_VERIFIED wording |
| 7.1–7.3.4 Evaluation / bioanalysis | LEGACY / Normal titles | DYNAMIC | REPLACED | Analyte/PK/sampling; analytical details unresolved if unknown |
| 8.1–8.5 Safety | Mixed | DYNAMIC + STATIC_VERIFIED | REPLACED | Narrative replaced; T13–T16 scales PRESERVED |
| 9.1–9.7.* Statistics | Partial LEGACY N=46 | DYNAMIC | REPLACED | SubjectPlan N + stats config; LEGACY.STATS_N46 **REMOVED** |
| 18 Literature | LEGACY template list | DYNAMIC | REPLACED | Project sources with type/title/authors/year/URL |

---

## B. Tables (P0 focus)

| Table | Classification | OLD | NEW | ACTION | REASON |
|---|---|---|---|---|---|
| T04 Signatures | DYNAMIC / CONDITIONAL | Uncontrolled form | DYNAMIC when org/sponsor present; else PRESERVE | LABEL fill / PRESERVE | No silent blank form wipe |
| T08 Schedule | STATIC_VERIFIED (2×2 crossover) | Template | STATIC_VERIFIED PRESERVE | PRESERVED | Matches golden crossover; no invent of procedure matrix |
| T09 Lab panels | STATIC_VERIFIED | Template | STATIC_VERIFIED | PRESERVED | Clinical labs ≠ PK analytes — **not** mapped to overwrite |
| T12 Meal timing | STATIC_VERIFIED (FED+HIGH_CALORIE) / DYNAMIC (FASTING) | Template fed schedule | PRESERVE or REBUILD | PRESERVED / REPLACED | Food-conditioned; no invent of calorie timing for FED |

Existing dynamic tables (T01/T03/T05/T06/T07/T10/T17) unchanged in role; continue label/rebuild fills from canonical values.

---

## C. LEGACY inventory after 11B

| Block ID | Status | Notes |
|---|---|---|
| LEGACY.SYNOPSIS_N46 | LEGACY_UNCONTROLLED | Unmatched synopsis cells may still show template N=46 |
| LEGACY.STATS_N46 | **REMOVED** | Section 9.2 fully in ACTIVE_SECTION_CODES |
| P0 section bodies listed above | DYNAMIC | Controlled via ACTIVE_SECTION_CODES |

---

## D. Heading mapping notes

| Code | Template style | Detection |
|---|---|---|
| 1.x, 2.x, 4.x, 5.x, 6.x, 8.x, 9.x | Heading 2 | Existing |
| 3, 4 (parent), 7, 8 (parent), 18 | «1 абзац» | Extended `_find_heading_indexes` |
| 7.1 (`7. 1.`), 7.2–7.3.4 | Normal | Flex dotted-code matcher for ACTIVE only |

---

## E. Honest blocking

- Missing sponsor / critical org / evidence placeholders → REVIEW/FINAL gate via `CRITICAL_UNRESOLVED_PREFIXES` + `_gate_mode`.
- No `N/A` insertion for missing org/evidence.
- DRAFT may retain explicit `{{…}}` markers listed in Build Report.

---

## F. Out of scope (not started)

P1 / P2 / P3 sections, Research Engine, Local AI, statistics formula changes, appendix appendix form rewrites.
