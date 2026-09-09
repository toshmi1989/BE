# Phase 15.3 — Real Research Provider & Source Review

**Version:** 0.18.0  
**Extends:** Phase 15.2 Research Evidence Engine  
**Does not start:** Phase 16 / Sample Size / Statistics / autonomous medical decisions

## 1. Provider architecture

| Provider | Kind | Role |
|----------|------|------|
| `RealWebResearchProvider` | `WEB` | DuckDuckGo HTML search (configurable); injectable `search_fn` for tests |
| `MockResearchProvider` | `MOCK` | Deterministic fixtures |
| `LocalDocumentProvider` | `LOCAL_DOCUMENTS` | Local storage scan |
| `InternalSourceProvider` | `INTERNAL_LIBRARY` | In-memory catalog |
| `NullResearchProvider` | `LOCAL_DOCUMENTS` | Empty offline |

Domain orchestration uses `ResearchProvider` only.

## 2. Real search

`POST /research-tasks/{id}/run-real-search` → query → results (`ResearchSearchResult`) → optional official auto-register (claims still PROPOSED) → conflict detect → `REVIEW_REQUIRED` when candidates exist.

Failed searches return explicit `RESEARCH_FAILED` / errors (timeout, 404, access denied, parse failure). Empty success → `NO_USABLE_EVIDENCE` (not silent).

## 3–4. Source registration & versioning

`SearchResult` → user/API `register-source` → `RegisteredSource` + `SourceVersion` → fetch HTML/PDF/DOCX (Phase 14.1 ingest) → snapshot (hash, mime, pages/tables) → claims **PROPOSED**.

Priority classes (`OFFICIAL_REGULATORY`, …) ≠ verification.

## 5–9. Numeric / CVintra / t½ / Tmax / SmPC

Reuses Phase 15.2 extraction + measurements. Between-subject CV ≠ CVintra. Ranges not collapsed. SmPC queries: `{product} SmPC|instruction|prescribing information`. Dose omitted from queries when `reference_product.dose` conflict is OPEN.

## 10–12. Applicability, usability, conflicts

Unchanged separation. Conflict resolve: `VALUE_A` / `VALUE_B` / `KEEP_BOTH` / `REQUEST_MORE_INFORMATION` — never average; AI cannot resolve.

## 13. Security

Sanitize title/snippet/URL/metadata. Reject `file://`, `javascript:`, local paths, executables. Untrusted HTML stripped. No code execution from fetched content.

## 14. Failure / limits

Timeouts, retries, backoff, `research_max_results` via settings.

## 15. AI-off

Core path works without AI. Mock/injected web for CI.

## 16. Testing

`tests/test_phase15_3_real_research_provider.py` — injected real provider (no live network required) + Mock coexistence + golden bootstrap.

## 17. Limitations

- Default web backend is DuckDuckGo HTML (may change / be blocked)  
- Live network optional; CI uses `use_injected_mock_web`  
- Auto-register of official sources does **not** verify claims  

See also: `docs/PHASE15_2_RESEARCH_EVIDENCE_ENGINE.md`
