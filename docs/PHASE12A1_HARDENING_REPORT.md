# Phase 12A.1-HARDENING Report

**Version:** 0.12.2  
**Status:** COMPLETE — do not start Phase 12A.2  
**Medical rules added:** **ZERO**

## 1. Audit scope

Technical audit of Expert Knowledge Foundation (Phase 12A.1): architecture SoT, status machines, silent-mutation absence, approve≠apply, provenance, gaps, design/sampling/PK/criteria/diff/QA, API, migration, trust boundary. No medical expansion, no DOCX expansion.

## 2. Architecture findings

| Entity | Role | SoT? |
|--------|------|------|
| Study / Design / Sampling / Washout / Food / Subjects / Stats | Canonical study state | Yes (ORM + Canonical Snapshot) |
| Evidence / EvidenceClaim | Provenance inputs | Yes for claims |
| ValidationIssue | Validation findings | Yes |
| ProtocolDraft / ProjectVersion | Document / version | Yes |
| KnowledgeRule | Evaluate / propose / gap | Decision support — not Study SoT |
| ExpertDecision | Formal decision record | Decision SoT (until apply exists) |
| KnowledgeGap | Missing knowledge | Blocking when CRITICAL/OPEN |
| RegulatoryBasis | Citation infrastructure | Supporting |
| ExpertRule (Phase 12A) | Empty content-generation catalog | **Legacy shell — not deleted** |

**No silent proposal→Study writes found** in knowledge proposal services.

## 3. KnowledgeRule vs ExpertRule

| | ExpertRule | KnowledgeRule |
|--|------------|---------------|
| Introduced | Phase 12A | Phase 12A.1 |
| Catalog | Empty by design | 36 seeded PROPOSED rules |
| API | None | Full CRUD + seed |
| Role | Future section wording hook | Authoritative knowledge/decision layer |

**Safe to deprecate ExpertRule eventually?** Yes, after content generators stop referencing the framework. **Not deleted in this phase.**

**Risk:** Dual catalogs could confuse future authors. Mitigated by KnowledgeGap + docstring in `expert_rules.py`.

## 4. Silent mutation audit

Checked: `knowledge_service`, `DesignDecisionEngine`, `decision_proposals`, `sampling_rules`, `pk_semantic`, `criteria_rules`, `protocol_qa`.

**Result: 0 silent Study mutations.** Proposals persist only knowledge tables (rules, decisions, gaps, QA, diffs).

Regression tests: `test_*_proposal_does_not_mutate_*`, `test_approve_decision_is_not_apply_decision`.

## 5. Status machine

**KnowledgeRule** (`knowledge_transitions.py`):

- REJECTED → VERIFIED **blocked**
- VERIFIED requires regulatory_basis_id **or** evidence_claim_ids **or** source_ids
- Re-seed no longer downgrades VERIFIED/REJECTED

**ExpertDecision:**

- Create forced to PROPOSED (client cannot POST APPROVED)
- Approve: PROPOSED|REJECTED → APPROVED; supersedes prior APPROVED (history kept)
- Reject: PROPOSED|APPROVED → REJECTED
- SUPERSEDED cannot re-approve
- `decided_at` set; `decided_by` optional (**limitation**)

## 6. Provenance

- VERIFIED rule without provenance → API 422 + validation `VAL.KNOWLEDGE.VERIFIED_WITHOUT_PROVENANCE.v1`
- VERIFIED RegulatoryBasis requires `document_identifier` + `section_reference`
- Fake `source_id` (missing Source) rejected when provided

## 7. Design audit

- Adaptive / 2×2 / replicate paths intact
- Expanded BE = gap only
- No numeric CV / long-HL thresholds in engine source
- Proposal always includes reasons, inputs, triggered_rules, expert flag

## 8. Sampling audit

- Adequacy vs `TMAX_CAPTURE_WINDOW` heuristic separated
- Heuristic alone does not PASS
- Generator does not write Canonical

## 9. PK audit

- Semantic `AUCMetricType` + aliases; `AUC0-x` ≠ `AUC0-72`
- DisplayValueRegistry human labels

## 10. Criteria audit

- Overlays require SmPC evidence flags; vomiting `2×Tmax` remains PROPOSED

## 11. Previous Protocol Diff

- LEGACY_SUSPECTED → review; no silent delete

## 12. Protocol QA

- Findings carry code/severity/message/blocking; CRITICAL placeholders block

## 13. API audit

- 404/422 covered; project-scoped listing; create cannot bypass approve
- **Limitation:** no RBAC / auth layer (app-wide)

## 14. Migration audit

- `0013` additive create-only upgrade; downgrade drops only new tables
- Unique `rule_code` is global (accepted limitation)

## 15. Security / trust boundary

| Check | Status |
|-------|--------|
| Client POST APPROVED decision | Blocked |
| VERIFIED without evidence | Blocked |
| Approve SUPERSEDED | Blocked |
| Cross-project list leak of other decisions | Filtered by project_id |
| Full auth / ownership RBAC | **Absent — documented limitation** |

## 16–17. Tests

| | Count |
|--|------|
| Before hardening | **255** |
| After | **286 passed** |
| New | **31** (`test_phase12a1_hardening.py`; prior 12A.1 file kept at 25) |
| Full suite | **286 passed** (~16:29) |
| Regression | **PASS** |

## 18. Fixed findings

1. REJECTED → VERIFIED allowed → **blocked**
2. VERIFIED without provenance → **blocked**
3. Create ExpertDecision as APPROVED → **blocked**
4. Re-seed downgraded VERIFIED → **preserved**
5. Weak `assert … or True` → **removed**
6. Soft critical-gap assert → **strict rule_id check**
7. ExpertRule vs KnowledgeRule ambiguity → **docs + KnowledgeGap**
8. Missing apply workflow → **KnowledgeGap (approve ≠ apply)**
9. UI wording clarified (Approve = decision only)

## 19. Accepted limitations

- No explicit Apply Decision → Canonical workflow yet
- No RBAC / actor enforcement beyond optional `decided_by`
- DOCX `_gate_mode` does not read gaps directly (indirect via validation → BLOCKED draft)
- Global unique `rule_code`
- PROPOSED numeric adequacy multipliers (5×t½, 3 points, 0.8 AUC) remain as PROPOSED — not new medical invention this phase
- LOW/MEDIUM gaps do not auto-emit INFO spam (only CRITICAL/blocking)

## 20. New KnowledgeGaps

1. ExpertRule vs KnowledgeRule coexistence / deprecation plan  
2. Explicit decision-to-canonical application boundary (approve ≠ apply)

## 21. Release recommendation

**PASS** for Phase 12A.1-HARDENING exit criteria. Safe to keep 0.12.2 as knowledge foundation hardening release.

**Next:** Do **not** auto-start 12A.2.
