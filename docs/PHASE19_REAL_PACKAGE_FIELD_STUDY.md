# Phase 19 — Real Package Expansion & Writer Field Study

**Version:** 0.24.0

## Policy

- Synthetic fixtures **never** count as REAL packages
- TIME_SAVING published **only** when `T_manual` and `T_total` observed directly
- No estimated ROI
- AI cannot approve decisions / conflicts / sample size / statistics / FINAL
- Golden protocol = reference artifact, not SoT

## Real package population (honest)

| Class | Count in-repo |
|-------|---------------|
| REAL full (sanitized) | **1** (UPDCB-02-BE-2026) |
| REAL_PARTIAL | **1** (design-only) |
| Intake slots empty | **8** |
| Meets ≥10 full REAL | **NO** |

Registry: `fixtures/real_packages/registry.json`  
Sanitization: `fixtures/real_packages/SANITIZATION_CHECKLIST.md`

**Limitation:** Phase 19 delivers field-study infrastructure and investigation tooling. Filling ≥10 distinct REAL packages requires writer-provided sanitized intakes into intake slots REAL-INTAKE-03…10.

## Methodology

### Baseline (manual)

Writer works without system assistance → record `T_manual` (and optional breakdown). No back-dating.

### System-assisted

Same writer, system on → `T_system` + `T_review` → `T_total = T_system + T_review`

```
TIME_SAVING = (T_manual - T_total) / T_manual
```

only if both sides observed directly.

### Order effect

Store `case_order`, pseudonymous `writer_id`, `date`, `system_used`.

### Events

See `FIELD_EVENTS` in `app.domain.field_study` / `GET /api/field-study/events/catalog`.

## APIs

| Endpoint | Purpose |
|----------|---------|
| `GET /api/field-study/real-packages` | Real registry + population gate |
| `GET /api/field-study/population-gap` | B-002 population field observation |
| `POST /api/field-study/sessions` | Start observed session |
| `POST .../timings` | Record observed times |
| `POST .../events` | Stage events (no sensitive payloads) |
| `POST .../feedback` | Structured UX feedback |
| `GET /api/field-study/metrics/timing` | Median / P25 / P75 |

## B-001 / B-002 / B-003 / B-005

See `docs/PHASE19_REAL_CASE_RESULTS.md` and updated `docs/BETA_ISSUE_LOG.md`.

## Production readiness

**READY-WITH-BLOCKERS** — gate fails on `meets_minimum_10_full_real=false` until intakes land and observed timings exist.
