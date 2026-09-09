# API (Phase 4)

Base: `/api`

Error codes: `NOT_FOUND`, `CONFLICT`, `PROVENANCE_GUARD`, `VALIDATION_ERROR` (422).

## Phase 2 engines

| Method | Path |
|--------|------|
| POST/GET/PATCH | `/projects/{id}/design` |
| POST | `/projects/{id}/design/recommend` |
| POST/GET/PATCH | `/projects/{id}/food` |
| GET/PUT | `/projects/{id}/eligibility` |
| POST/PATCH/DELETE | `/projects/{id}/eligibility/criteria[/{id}]` |
| POST/GET/PATCH | `/projects/{id}/subjects` |
| POST/GET/PATCH | `/projects/{id}/client-input` |
| GET | `/reference-data/design` |

`design/recommend` accepts structured inputs only (guideline recommendation, variability flags, dosage form, route, expert override, evidence IDs). No literature/web/LLM inside Design Engine.

## Phase 3 PK / Sampling

| Method | Path |
|--------|------|
| CRUD | `/projects/{id}/analytes` |
| POST/GET | `/projects/{id}/pk/parameters`, `/pk/recommend` |
| POST/GET | `/projects/{id}/washout/calculate`, `/washout` |
| POST/GET | `/projects/{id}/observation/calculate`, `/observation` |
| POST/GET/PATCH | `/projects/{id}/sampling/recommend`, `/sampling`, `/sampling/validate` |
| POST/GET | `/projects/{id}/blood-volume/calculate`, `/blood-volume` |

## Phase 4 Statistics

| Method | Path |
|--------|------|
| POST/GET | `/projects/{id}/statistics/cv` |
| POST | `/projects/{id}/statistics/cv/pool` |
| POST | `/projects/{id}/statistics/cv/select` |
| GET | `/projects/{id}/statistics/cv/selection` |
| POST/GET | `/projects/{id}/statistics/sample-size` |
| POST | `/projects/{id}/statistics/validate` |
| GET | `/projects/{id}/statistics/config` |

Sample-size math is deterministic (scipy NCT for 2×2). Defaults come from `StatisticalConfig` / `STAT.DEFAULTS.ABE.v1` — never hardcoded in the UI.

## Phase 5 Validation + Evidence Foundation

| Method | Path |
|--------|------|
| POST | `/projects/{id}/validate` |
| GET | `/projects/{id}/validation` |
| GET | `/projects/{id}/validation/summary` |
| POST | `/projects/{id}/validation/{issue_id}/acknowledge` |
| POST | `/projects/{id}/validation/{issue_id}/resolve` |
| POST | `/projects/{id}/validation/impact` |
| GET | `/projects/{id}/validation/snapshot` |
| POST/GET | `/projects/{id}/research-case` |
| POST/GET | `/projects/{id}/research-case/tasks` |
| POST/GET | `/projects/{id}/research-case/evidence` |
| POST/GET | `/projects/{id}/research-case/conflicts` |
| POST | `/projects/{id}/research-case/conflicts/{id}/resolve` |
| POST | `/projects/{id}/research-case/apply-verified` |
| GET | `/reference-data/source-ranking` |

No web-search endpoints. Protocol / DOCX engines are not in Phase 5.

## Phase 6 Research Engine + Document Ingestion

| Method | Path |
|--------|------|
| POST/GET | `/projects/{id}/research-profile` |
| POST | `/projects/{id}/research-case/tasks/generate` |
| POST/GET | `/projects/{id}/documents` |
| POST | `/projects/{id}/documents/{document_id}/ingest` |
| GET | `/projects/{id}/documents/{document_id}/pages` |
| POST | `/projects/{id}/research/search` |
| POST/GET | `/projects/{id}/research/evidence` |
| POST | `/projects/{id}/research/conflicts` |
| POST | `/projects/{id}/research/completeness` |
| GET | `/reference-data/evidence-fields` |

No Ollama / OpenAI / PubMed / crawler / vector DB. Upload limits + MIME/checksum validation apply.

## Phase 7 Local AI Structured Extraction

| Method | Path |
|--------|------|
| GET | `/ai/status` |
| POST | `/projects/{id}/ai/extract` |
| GET | `/projects/{id}/ai/runs` |
| GET | `/projects/{id}/ai/proposed` |
| POST | `/projects/{id}/ai/claims/{claim_id}/review` |

`POST .../ai/extract` body: `{ "task_type": "EXTRACT_PK", "query"?, "document_ids"?, "limit_chunks"?, "force_mock"? }`.

`POST .../ai/claims/.../review` body: `{ "action": "verify"|"reject"|"edit_verify", "edited_value"?, "edited_normalized_value"?, "analyte_id"? }`.

AI writes only `PROPOSED` / `AI_PROPOSED` evidence. Study updates only via existing `apply_verified` after expert verify. If `AI_ENABLED=false`, extract fails safely; `/ai/status` reports disabled. No OpenAI / web search / autonomous agent.

## Phase 8 Protocol Assembly (no DOCX)

| Method | Path |
|--------|------|
| POST | `/projects/{id}/protocol/build` |
| GET | `/projects/{id}/protocol` |
| GET | `/projects/{id}/protocol/sections` |
| GET | `/projects/{id}/protocol/build-report` |
| GET | `/projects/{id}/protocol/preview` |
| POST | `/projects/{id}/protocol/sections/{section_code}/rebuild` |

Builds structured `ProtocolDraft` from Study + validation. Blocking validation → `status=BLOCKED`. HTML preview only — no Word generation.

## Phase 9 DOCX Rendering

| Method | Path |
|--------|------|
| POST | `/projects/{id}/protocol/docx/build` |
| GET | `/projects/{id}/protocol/docx/status` |
| GET | `/projects/{id}/protocol/docx/validation` |
| GET | `/projects/{id}/protocol/docx/download` |

Modes: `DRAFT` | `REVIEW` | `FINAL`. Renderer is presentation-only (no Study mutations). Missing sponsor / protocol_number / products block FINAL. Template file is never modified. Inventories: `docs/DOCX_TEMPLATE_INVENTORY.md`, `docs/DOCX_TABLE_INVENTORY.md`.
