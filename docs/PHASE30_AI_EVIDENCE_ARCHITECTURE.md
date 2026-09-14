# PHASE 30 — AI Evidence Architecture (audit + integration)

**Version:** 0.35.1  
**Date:** 2026-09-14  
**Rule:** Do **not** create a second AI architecture. Extend Writer → ResearchClaim lane.

---

## Existing lanes (reuse)

| Lane | Scope | Status machine | Writer use |
|---|---|---|---|
| Phase 7 AI (`ai_provider`, `/projects/.../ai/extract`) | Project ORM EvidenceClaim | AI → PROPOSED only | Legacy Dashboard |
| Phase 15.2 Research Center | Study ResearchClaim (in-memory) | PROPOSED → VERIFIED/REJECTED | Gaps panel + research |
| Phase 13 Regulatory | RegulatoryEvidenceClaim | assistive | Interview / import |

**Phase 30 integrates into the Study ResearchClaim + Writer Gaps lane**, optionally calling the same `AIProvider` (Mock / Ollama / OpenAI) for assistive extraction.

---

## Flow (required)

```
SOURCE (uploaded study docs / SmPC / research)
  → AI or deterministic extract (assistive)
  → ResearchClaim(status=PROPOSED, provenance, confidence label)
  → expert review (Verify / Reject / Request another source)
  → VERIFIED + applicability
  → apply_verified_research_to_context (structured_facts)
  → template contamination FINAL gate may clear
  → renderer (never fed by PROPOSED AI)
```

Forbidden:

```
AI → direct Canonical Snapshot / Approved Decision / FINAL DOCX
```

---

## Key modules

| Role | Path |
|---|---|
| Providers | `backend/app/domain/ai_provider.py` |
| Prompts | `backend/app/domain/ai_prompts.py` (+ `EXTRACT_PHARMACOLOGY`) |
| Product field catalog | `backend/app/domain/product_knowledge.py` |
| Study extract → ResearchClaim | `backend/app/domain/product_evidence_service.py` |
| Apply verified → context | `backend/app/domain/research_decision_bridge.py` |
| Gaps / MANUAL / RESEARCH | `backend/app/domain/workspace_gaps.py` |
| FINAL pharmacology gate | `backend/app/domain/template_contamination.py` |
| API | `GET/POST .../product-evidence*` in `study_workspace.py` |
| UI | `frontend/src/components/ProductEvidenceReview.tsx` |

---

## Product knowledge categories

PRODUCT_IDENTITY, ACTIVE_SUBSTANCE, PHARMACOLOGICAL_CLASS, MECHANISM_OF_ACTION,  
THERAPEUTIC_INFORMATION, CHEMICAL_INFORMATION, PHARMACOKINETIC_FACTS,  
TMAX (expected/planning), HALF_LIFE (expected/planning), FOOD_EFFECT,  
CONTRAINDICATIONS, INTERACTIONS, RELEVANT_SAFETY.

Source priority (configurable): SmPC → OHLP → official regulatory → verified regulatory → literature → other.

---

## Confidence vs verification

| AI confidence | Expert status |
|---|---|
| HIGH / MEDIUM / LOW (label) | PROPOSED until Verify |
| Never equals VERIFIED | VERIFIED only after human review + applicability |

---

## FINAL gate (Phase 29.2 unchanged policy)

- PROPOSED pharmacology → FINAL **blocked**
- REJECTED → **blocked**
- VERIFIED + applicable → `has_verified_product_pharmacology` may clear FINAL contamination gate
- DRAFT may still clear template example content without inventing Upadacitinib text

---

## AI-off

`AI_ENABLED=false`: deterministic regex extract from document/candidate text only; MANUAL gap resolve remains; system does not break.
