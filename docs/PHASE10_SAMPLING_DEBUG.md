# Phase 10 — Sampling / Validation Tmax Coverage Debug

**Case:** Bosutinib golden (`tmax_min = tmax_max = 6 h`)  
**Original issue:** `VAL.SAMP.INSUFFICIENT_TMAX_COVERAGE.v1`  
**Status:** **FIXED** — Sampling and Validation share `TmaxCaptureWindow` (`app/domain/tmax_capture_window.py`).

---

## INPUT

| Field | Golden value |
|-------|--------------|
| `tmax_min` / `tmax_max` | **6.0 / 6.0 h** (point estimate) |
| Observation | **72.0 h** |
| Density rule | `PK.SAMP.DENSITY.v1` (**PROPOSED**) |

---

## SAMPLING PLAN

Under shared capture window `4.5–7.5 h`, density places `TMAX_CAPTURE` at  
`4.5, 5.25, 6.0, 6.75, 7.5` (among full schedule).

---

## SAMPLING RULE

`PK.SAMP.DENSITY.v1` via `compute_tmax_capture_window()` → `TmaxCaptureWindow`.

Margins (`tmax_pre_margin_fraction` / `tmax_post_margin_fraction` = 0.25) remain **PROPOSED** workflow parameters — **not** verified regulatory norms.

---

## VALIDATION RULE

`VAL.SAMP.INSUFFICIENT_TMAX_COVERAGE.v1` now counts points inside the **same** `TmaxCaptureWindow.window_min/max` and requires `density_requirement.min_points_in_window` (default 2 from rule params).

No hardcoded `[tmax_min, tmax_max]`-only check.

---

## CONFLICT

| Before | After |
|--------|--------|
| Sampling: expanded 4.5–7.5 | Same |
| Validation: literal [6, 6] | **Aligned** to 4.5–7.5 via `TmaxCaptureWindow` |
| Auto-plan failed self-check | Auto-plan passes coverage rule |

---

## ROOT CAUSE

Divergent capture-window definitions between engines (not bad golden data).

---

## RECOMMENDED FIX

**Done:** reusable `TmaxCaptureWindow` / `compute_tmax_capture_window` used by both engines.  
Do not reintroduce literal-range-only validation.

---

## REQUIRED TESTS

Covered in `backend/tests/test_tmax_capture_window.py`:

1. Tmax 6–6 → window 4.5–7.5  
2. Generated plan passes validation  
3. Tmax 2–3 identical windows  
4. Multi-analyte merged consistency  
5. Manual override same canonical window  
6. Sparse `{0,6,72}` still fails coverage  

---

## STOP
