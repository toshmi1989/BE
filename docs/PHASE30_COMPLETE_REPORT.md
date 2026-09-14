# PHASE 30 COMPLETE — AI Evidence Extraction for Product-Specific Content

**Version:** 0.35.1  
**Date:** 2026-09-14

## FINAL REPORT

### Version
**0.35.1**

### AI architecture reused
Yes — `AIProvider` (Mock / Ollama / OpenAI) + Study `ResearchClaim` + Writer gaps.  
**No second AI architecture.**

### Provider
Replaceable via existing runtime/settings: `mock` | `local`/`ollama` | `openai` | disabled.

### Product extraction
`product_evidence_service.extract_product_evidence_for_study`  
→ ResearchClaim **PROPOSED** with provenance (source, location, excerpt, confidence).

### Pharmacology
Gap `MISSING_PRODUCT_PHARMACOLOGY` + fields `product.pharmacology` / `product.mechanism` / `product.pharmacological_class`.  
Verified claims applied via `research_decision_bridge` → `evidence.pharmacology_verified`.

### TMAX
Expected/planning `pk.expected_tmax` (not observed post-study). Gap + extract + verify path preserved/extended.

### HALF_LIFE
Expected/planning `pk.expected_t_half`. Same lane.

### Evidence
PROPOSED only from AI/deterministic; expert Verify/Reject via `/product-evidence/review` and existing gap verify.

### Applicability
Required on verify; IR≠PR enforced in tests (`NOT_APPLICABLE` does not unblock).

### Conflicts
`detect_numeric_conflicts` — OPEN, no averaging, no auto-pick.

### Research fallback
Existing Gaps → ResearchTask (`GAP_TO_TASK` includes product pharmacology/chemistry/safety) → PROPOSED → verify.

### Verification
Human only. AI actors cannot verify/reject as authority.

### Template integration
Product fields map to Phase 29.2 contamination blocks; FINAL clears only with verified pharmacology.

### Contamination gate
**Fail-closed retained.** Unverified AI **cannot** clear FINAL.

### UPDCB
Extraction works against package/candidate text; SmPC-like strings produce PROPOSED claims; expert verify required for FINAL.

### AI-off
Deterministic extract + MANUAL gaps; `AI_ENABLED=false` supported.

### Tests
`test_phase30_*.py` + Phase 29.2 — **23 passed** (phase30 suite + contamination).

### Regression
Focused: Phase 29.2 contamination + Phase 30 suites green. Full 15–29 matrix not re-run in this session (run CI / local full suite before release).

---

## FINAL blockers remaining

1. FINAL still blocked until expert **verifies** applicable product pharmacology for the study.  
2. Empty / sparse package text → fewer auto-proposals (correct — no invention).  
3. Full chemical formula / safety narrative may still need MANUAL or research if absent from uploads.  
4. Traceability DOCX-field → claim reverse index is partial (claim → field_path → structured_facts; full DOCX reverse map future).

## Production readiness

**Assistive product-evidence lane: ready for Writer use (AI-off safe).**  
**FINAL DOCX: ready only after verified pharmacology — gate intentionally not weakened.**

Docs:
- `docs/PHASE30_AI_EVIDENCE_ARCHITECTURE.md`
- this report
