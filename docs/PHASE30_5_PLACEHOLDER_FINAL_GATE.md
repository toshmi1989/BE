# Phase 30.5 — FINAL Gate and Placeholder Closure

**Version:** 0.35.5  
**Date:** 2026-09-15  

## Goal

Make the DRAFT / FINAL boundary deterministic: no required or unknown unresolved placeholder may reach FINAL. No new medical engines, AI features, or template redesign.

## Deliverables

### 1. Required Placeholder Registry

`backend/app/domain/placeholder_registry.py`

| Classification | FINAL policy |
|---|---|
| `REQUIRED_DYNAMIC` | BLOCK |
| `OPTIONAL_DYNAMIC` + `ALLOW` | permitted (`PUBLICATION.POLICY`, `SOURCES.LIST`, `FINANCING.DETAILS`, `INSURANCE.DETAILS`) |
| `STATIC_TEMPLATE` | BLOCK if seen unresolved |
| `UNKNOWN` (unregistered) | always BLOCK |

### 2. FINAL Placeholder Gate

`assess_docx_semantic_integrity` scans body, tables, headers/footers, and XML `w:t`.

FINAL with any `REQUIRED_DYNAMIC` or `UNKNOWN` →

`CRITICAL: UNRESOLVED_TEMPLATE_PLACEHOLDER` → render `status=BLOCKED` (file deleted). No silent delete of markers.

### 3. DRAFT Output

DRAFT may keep explicit `{{CODE}}` markers. Non-brace unresolved forms are rejected as `DRAFT_PLACEHOLDER_NOT_EXPLICIT`.

### 4. FINAL Output Policy

- 0 required placeholders  
- 0 unknown placeholders  
- Optional allowlisted only  

### 5. Protocol UI

Shows **FINAL BLOCKED** + list: section, field, reason, **Resolve** → tab. Reads `preflight.final_gate`.

### 6. No False Success

- `build_preflight.can_finalize = false` when blocked  
- `final_gate.status = BLOCKED`  
- `generate_docx_artifact(mode=FINAL)` raises `ValidationError` with `can_finalize: false`  

### 7. Regression

`tests/test_phase30_5_placeholder_final_gate.py`

- required → FINAL blocked  
- optional allowlist → permitted  
- unknown → FINAL blocked  
- DRAFT allowed  

### 8. TOC

`TOC_VISUAL_VALIDATION = NOT_EXECUTED` — environment limitation (no LibreOffice PDF visual proof on this host). Do not fake PDF verification.

## Acceptance

- [x] placeholder registry complete  
- [x] required placeholders block FINAL  
- [x] unknown placeholders block FINAL  
- [x] DRAFT allows explicit unresolved placeholders  
- [x] FINAL has zero required placeholders (gate enforced)  
- [x] UI explains blockers  
- [x] backend/frontend state agree (`can_finalize` + `final_gate`)  
- [x] no false FINAL success  
- [x] AI-off (unchanged; no AI features added)  
- [x] regression tests added  

## FINAL REPORT

```
PHASE 30.5 COMPLETE
Version: 0.35.5
Required placeholders: registry + FINAL BLOCK
Unknown placeholders: FINAL BLOCK
DRAFT: explicit {{…}} allowed
FINAL: 0 required / 0 unknown (else BLOCKED)
Gate: final_gate.status + can_finalize=false
TOC visual validation: NOT_EXECUTED
AI-off: pass (no AI change)
Regression: test_phase30_5_placeholder_final_gate.py
Production readiness: DRAFT export OK; FINAL fail-closed until sources closed
```
