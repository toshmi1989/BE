# PHASE 29.2 COMPLETE — Template Contamination Audit & Clean Render

**Version:** 0.34.1  
**Date:** 2026-09-14  
**Priority:** P0

## Result

Semantic contamination protection is in place. Token rename alone is no longer the primary control.

Workspace **FINAL** DOCX remains blocked without verified product pharmacology.  
**DRAFT** generation clears product-specific template example content, then fails closed if any Bosutinib/CML/chemistry semantics remain.

## Contaminated blocks found

| Metric | Value |
|---|---|
| PRODUCT_SPECIFIC blocks (audit) | **81** |
| Fingerprints | **71** |
| UNKNOWN (weak markers) | 15 |
| Cleared on clean pass (template copy) | **80** paragraphs/cells |

## Contaminated sections

- **2.1** product description — CML / TKI / Bcr-Abl / Src narrative  
- **2.1** chemical name, formula `C26H29Cl2N5O3`, MW `530,45`  
- **2.8** «Фармакологические свойства бозутиниба»  
- **2.9–2.12** product-specific justifications  
- Multiple **4.x / 6.x / 10.x** cells and headers with Bosutinib/Bosulif / 400 mg example  
- See `docs/PHASE29_TEMPLATE_CONTENT_BASELINE.md`

## Dynamic mappings added

- Registry: `backend/app/domain/template_contamination.py`  
- Cleaner: `backend/app/domain/docx_contamination.py`  
- Preflight: `CRITICAL_TEMPLATE_CONTAMINATION` in `build_preflight`  
- Generate path: clear → token scrub → XML scrub → contamination scan  
- Inventory extension: `docs/_phase29_template_inventory.json` → `phase29_2_semantic_audit`

## Blocks removed

PRODUCT_SPECIFIC template example text replaced with explicit cleared placeholder:

> `[СОДЕРЖАНИЕ УДАЛЕНО: в шаблоне был пример другого препарата. Требуются верифицированные данные по исследуемому препарату текущего исследования.]`

Headings with «бозутиниба» neutralized to «исследуемого препарата».

## Blocks requiring evidence

For **FINAL** mode / finalize: all CLEAR_OR_BLOCK pharmacology / chemistry blocks require VERIFIED / APPROVED / CANONICAL pharmacology evidence (`has_verified_product_pharmacology`). Without it → unmanaged → block.

## Blocks now blocking

- Unmanaged registry actions (`BLOCK`, `POPULATE` without evidence)  
- FINAL without verified pharmacology  
- Post-render contamination scan hits (CML / chemistry / Bosutinib semantics)  
- Regression fixture: unmanaged `fixture.stale_pharmacology` → `ValidationError(CRITICAL_TEMPLATE_CONTAMINATION)`

## UPDCB

- Clean template pass: **no** CML, **no** `C26H29Cl2N5O3`, **no** Bosutinib strings, scan `contaminated=False`  
- Page 21 class content (pharmacology / formula): **cleared**, not renamed  
- Full Workspace regenerate still uses existing `render_protocol_docx` (no second renderer)

## Page 21

Fixed by **semantic clear**, not string substitution of Upadacitinib over Bosutinib pharmacology.

## DOCX contamination scan

Implemented: visible text + XML `w:t` parts; categories PRODUCT_NAME, DISEASE_CML, MECHANISM_TKI, CHEMISTRY_BOSUTINIB, ATC, INDICATION.

## Tests

`backend/tests/test_phase29_2_template_contamination.py` — **7 passed**

- `test_template_product_specific_blocks`  
- `test_no_bosutinib_semantic_contamination`  
- `test_no_cml_contamination`  
- `test_no_unrelated_pharmacology`  
- `test_no_unresolved_product_specific_placeholder`  
- `test_regression_stale_block_blocks_generation`  
- `test_updcB_generated_docx_content_audit`

## Regression

Known stale unmanaged block **blocks** generation (asserted).

## Production readiness

| Item | Status |
|---|---|
| Full template semantic audit | Done |
| Product-specific blocks identified | Done |
| Page 21 fixed (clear, not rename) | Done |
| No Bosutinib/CML contamination after clean | Done |
| No unrelated chemical formula after clean | Done |
| Token scrub secondary | Done |
| Generated DOCX content audit | Done |
| CRITICAL blocks FINAL / unmanaged | Done |
| Existing renderer reused | Done |
| No second renderer | Done |
| AI-off compatible | Done |
| DRAFT usable after clear | Yes |
| FINAL with empty pharmacology | **Blocked** (requires verified evidence) |
| Full medical rewrite of §2 from UPDCB evidence | **Not done** (correctly blocked / cleared) |

**Production readiness:** DRAFT clean-render **ready for contamination safety**; FINAL protocol **not** ready until verified product pharmacology/chemistry evidence is mapped into those blocks.
