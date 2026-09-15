# PHASE 30.4 — FINAL DOCX VISUAL ACCEPTANCE

**Version:** 0.35.5  
**Study:** UPDCB-02-BE-2026  
**AI:** off  
**Gate bypass:** none (expert dose-conflict resolution recorded explicitly)

## Result

**PASS-WITH-BLOCKERS**

## Generate

| Artifact | Status |
|----------|--------|
| DRAFT DOCX | **PASS** (~1.23 MB) after explicit expert resolve of open `reference_product.dose` conflict |
| FINAL DOCX | **BLOCKED** (`can_finalize=false`) — not attempted with bypass |

Acceptance runner: `docs/_phase30_4_acceptance_run.py`  
Evidence JSON: `docs/phase30_4_data/acceptance-latest.json`

## Visual review

PDF/image tooling (**LibreOffice / Word COM / pandoc**) was **not available** on the runner host. Review performed via python-docx structural inspection of the generated DRAFT.

| Area | Observation |
|------|-------------|
| Cover | Typed mapping OK — form+dose, not subject N |
| Synopsis / §1–2 | Structure present; many DRAFT placeholders remain |
| Product tables | No Bosutinib / 400 mg residue detected in content scan |
| Design | Present from golden assembly |
| Sampling | Table still shows `{{SAMPLING.*}}` (SamplingPlan empty in golden ctx) |
| PK | Table present; no `таблица PK_PARAMETERS` leak |
| Statistics / Safety | Placeholders remain → FINAL blocked |
| Appendices / References | Template structure retained |
| TOC | **P1:** TOC lines still show stale/duplicated page-number text; PDF page-proof N/A |
| Layout | DOCX opens; ≥30 tables; large body; no ordinal cover corruption |

**Page count:** N/A (no PDF renderer)

## Content integrity

| Check | DRAFT |
|-------|-------|
| wrong dosage form (=56) | **0** |
| wrong dose / stale 400 mg | **0** |
| stale date 18.04.2025 | **0** (cleared / replaced) |
| Bosutinib / Bosulif | **0** |
| internal table registry name | **0** |
| ACCEPTED_CALCULATION enum | **0** |
| `{{PLACEHOLDER}}` | **present (DRAFT-allowed)** — ~40 unique codes |
| wrong_mappings (integrity) | **0** |

Cover sample (canonical):

- Investigational product: upadacitinib  
- Dosage form cell: `prolonged-release film-coated tablet, 15 mg`  
- Protocol: UPDCB-02-BE-2026  

## Cross-section

Canonical dose/form appear on cover. Washout/sampling/observation still incomplete in golden package → placeholders in body (expected DRAFT; FINAL blocked).

## TOC

- LibreOffice refresh not available  
- Fallback cleared some TOC page tails; residual duplicate page text remains (**P1**)  
- Cannot verify displayed page numbers against actual PDF pages on this host  

## DRAFT / FINAL UX

Protocol tab updated:

- Banner: **Режим выгрузки: ЧЕРНОВИК (DRAFT)** — not an approved FINAL  
- **FINAL: PASS / BLOCKED** with explicit reason text  
- Button label: **Сгенерировать DOCX · черновик**

## FINAL blockers (legitimate)

From semantic FINAL preflight (examples):

- MISSING_PROTOCOL_DATE  
- MISSING_SAMPLING_PLAN  
- MISSING_OBSERVATION_DURATION  
- MISSING_ELIGIBILITY  
- MISSING_BIOANALYSIS  
- MISSING_STATISTICS_PLAN (APPROVED)  
- plus open FINAL pharmacology / contamination gates as applicable  

## Issues

### P0

*(none for DRAFT acceptance criteria of Phase 30.3 mapping fixes)*

### P1

1. DRAFT still contains many unresolved placeholders (eligibility, bioanalysis, safety, sampling, …)  
2. Sampling table not populated from SamplingPlan (plan absent)  
3. TOC page numbers not PDF-verified; residual TOC duplication  
4. FINAL correctly unavailable until sources verified  

## Checklist vs charter

| Item | Status |
|------|--------|
| Generate DRAFT | PASS |
| Generate FINAL only if gates OK | BLOCKED (correct) |
| No gate bypass | PASS (expert resolve logged) |
| Visual sections inspected (DOCX) | PASS-WITH-LIMIT (no PDF) |
| Content integrity zeros for mapping/stale product | PASS on DRAFT |
| Cross-section | PARTIAL (gaps → placeholders) |
| TOC page proof | FAIL tooling / P1 residual |
| DRAFT≠FINAL UX | PASS (UI clarified) |

## Production readiness

- **DRAFT export** after conflict resolution is usable for writer review; must not be treated as FINAL.  
- **FINAL** remains fail-closed until required dynamic sources are complete.  
- Phase 31: not started.
