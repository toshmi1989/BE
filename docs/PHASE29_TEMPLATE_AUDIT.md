# PHASE 29 — Template-based Protocol DOCX Audit

**Status:** AUDIT ONLY (no renderer rewrite in this step)  
**Target version:** 0.34.0  
**Date:** 2026-09-13  
**Repo:** `C:\Projects\BE`

Related (do not confuse): `docs/PHASE29_GAP_PIPELINE_REPORT.md` covers the **writer gaps / research pipeline**.  
This document is the **template DOCX generation** audit required before coding Phase 29 (template-based DOCX).

---

## 0. Executive verdict

| Question | Finding |
|---|---|
| Does the **writer workspace** path produce a full BE protocol DOCX? | **No.** `workspace_protocol.generate_docx_artifact` builds a **2-page technical draft** with `Document()` + 14 English headings. |
| Does a **template-based** renderer already exist? | **Yes** — Legacy Project path: `docx_renderer.render_protocol_docx` copies `BE_Protocol_Template_v2.0.docx` and fills sections/tables. |
| Is that path wired to the Phase 16–28 workspace UI? | **No.** Workspace API uses the technical draft; Project DOCX uses `docx_service` → template renderer. |
| Is the template the Russian “Шаблон Протокола БЭ … v2.0”? | **Yes, byte-identical.** Repo `BE_Protocol_Template_v2.0.docx` == Downloads `Шаблон Протокола БЭ финальный с комментариями v2.0.docx` (same size + SHA-256 `8e6be6aa…25d8a6`, matches `docx_profile`). |
| Golden UPDCB protocol in-repo? | **Full PКИ:** Downloads only (reference). **Also** fixture copies named `golden_protocol.docx` under `fixtures/study_inputs/updcb_02_be_2026/{raw,sources}/` — still reference-only, not content authority. |

**Phase 29 coding goal (from product TZ):** make the **workspace → DOCX** path load the real template, populate from Canonical Snapshot + VERIFIED evidence + APPROVED decisions / StatisticsPlan / Sample Size — without inventing medical rules, without using Golden as data source.

---

## 1. Artifact locations

### 1.1 Current DOCX renderer (template-based)

| Item | Path |
|---|---|
| Renderer | `backend/app/domain/docx_renderer.py` |
| Entry | `render_protocol_docx(...)` |
| Behavior | `shutil.copy2(template)` → `Document(out_path)` → fill by section codes / table keys |
| Profile / mapping | `backend/app/domain/docx_profile.py` |
| Validation | `backend/app/domain/docx_validation.py` |
| Service (Legacy Project) | `backend/app/services/docx_service.py` → `render_protocol_docx` |

Key property (already correct for Phase 29 structure rule):

```text
LOAD template → preserve structure → populate → save
NOT: new Document() for the full protocol
```

### 1.2 Current “Protocol Draft” (two meanings)

| Kind | Path / store | Role |
|---|---|---|
| **Workspace ProtocolDraft** (Phase 16+) | `study_workspace.put_protocol_draft_version` / `WorkspaceProtocolDraftRecord` | Immutable version marker + `based_on_*` ids. Preview text is **not** full protocol content. |
| **Legacy ProtocolDraft ORM** (Phase 8–12) | `app.models.protocol.ProtocolDraft` + sections/tables | Full assembled content blocks for Project DOCX. |

Writer UI “Собрать черновик” creates the **workspace** draft via `run_protocol_workflow` / orchestrator — not the Legacy ORM draft.

### 1.3 Protocol Assembly Engine

| Item | Path |
|---|---|
| Assembly | `backend/app/domain/protocol_assembly.py` → `assemble_protocol` |
| Section tree | `backend/app/domain/protocol_sections.py` (`SECTION_TREE`) |
| Generators | `protocol_generators_p0/p1/12b1/12b2/12b3/12b4*.py` |
| Tables | `protocol_tables.py`, `table_registry.py` |
| Text blocks | `protocol_text_blocks.py` |
| Cross-refs | `reference_registry.py` |
| Display enums→RU | `display_value_registry.py` |

Assembly is **deterministic content construction** (no DOCX). DOCX is a separate presentation step.

### 1.4 Template file

| Expected product name | Repo file |
|---|---|
| «Шаблон Протокола БЭ финальный с комментариями v2.0.docx» | `templates/protocol/BE_Protocol_Template_v2.0.docx` |

- Absolute Downloads original (confirmed identical):  
  `C:\Users\ali31\Downloads\Шаблон Протокола БЭ финальный с комментариями v2.0.docx`
- Size: **1 413 844** bytes  
- SHA-256: `8e6be6aa6f0514dc4ba6a1016feb141946a2ded538a58d306bcf0fa68725d8a6` (pinned in `docx_profile`)  
- README: `templates/protocol/README.md`

### 1.5 Golden / reference protocol

| Expected name | Location |
|---|---|
| `ПКИ_UPDCB-02-BE-2026_corr_21.08.2026_31.08.2026.docx` | `C:\Users\ali31\Downloads\ПКИ_UPDCB-02-BE-2026_corr_21.08.2026_31.08.2026.docx` |
| Related Downloads variants | `БИ_…corr…25.08…`, pregnancy form DOCXs |
| Fixture-named golden (UPDCB package) | `fixtures/study_inputs/updcb_02_be_2026/raw/golden_protocol.docx` and `…/sources/golden_protocol.docx` |

**Policy:** Golden = structural / regression reference only. Never seed Study Snapshot / decisions / doses from Golden (including fixture `golden_protocol.docx`).

### 1.6 UPDCB study input fixture (data package, not Golden DOCX)

`fixtures/study_inputs/updcb_02_be_2026/` — used by `load_real_fixture_package()` for Decision Center / workflow demos. Contains extracted package inputs; **not** the final PКИ DOCX.

---

## 2. Dual DOCX architecture (root cause of 2-page draft)

```text
Writer workspace (Phase 16–28 UI)
  → POST /studies/{id}/protocol/docx
  → workspace_protocol.generate_docx_artifact
  → Document() + 14 stub sections          ← PROBLEM (current UX)

Legacy Project path (Phase 9–12)
  → docx_service.build…
  → assemble_protocol → ProtocolDraft ORM
  → docx_renderer.render_protocol_docx
  → BE_Protocol_Template_v2.0.docx         ← TARGET behavior to reuse
```

Evidence — workspace stub (debug / technical draft):

- Heading: `Protocol Draft — {study_key}`
- Section 11 body: `"From approved statistics plan when present."`
- Design body can print raw facts / enums (`design.crossover`)
- Missing values shown as `"—"`

This matches the product complaint exactly.

---

## 3. Template inventory (programmatic)

Machine extract saved at:

- `docs/_phase29_template_inventory.json`
- `docs/_phase29_inventory_print.txt` (readable headings/tables)

### 3.1 Counts

| Metric | Value |
|---|---|
| Paragraphs | 1432 (1012 non-empty) |
| Tables | **33** |
| Word sections | 1 (continuous) |
| Strict `Heading*` styles | **94** (Heading 1: 1 · Heading 2: 93) |
| Top-level titles style `1 абзац` | **17** (1–4, 5, 7–18… — not Word Heading) |
| Heading-like incl. TOC styles | 193 |
| `{{PLACEHOLDER}}` patterns | **0** (filled sample text + comments, not tokens) |
| Word comments (`word/comments.xml`) | **74** |
| Authoring-ish body paras (заполнить/TODO/…) | ~4 (plus many table-cell hits inflated by merges) |
| TOC field present | **Yes** (`instrText` TOC) |
| Page estimate | **~103–114** (`lastRenderedPageBreak` ≈103 + explicit page breaks 11) |
| Header (first section) | Dynamic sample: «Исследуемый препарат: Бозутиниб…»; «Код протокола: № номер протокола»; «Версия 1.0 от 18.04.2025 г.» |
| Footer | Empty text via extract |

### 3.2 Major section outline (from body + TOC)

Authoritative structure is the template TOC / body, not the 14-section workspace stub.

**Style note for renderer:** top-level chapters use style **`1 абзац`**, subsections mostly **`Heading 2`**. Section matching must not assume only Word Heading styles (existing `docx_renderer` already has `SECTION_TITLE_STYLES` / flex heading regex — keep and extend).

Outline (high level):

1. **Общая информация** (1.1–1.9) — metadata, sponsor, experts, sites, labs, orgs, signatures, investigator agreement  
2. **Обоснование** (2.1–2.12) — products, preclinical/clinical, risk-benefit, dose, conditions, subjects, literature, pharmacology, observation, washout  
3. **Цель и задачи**  
4. **Дизайн** (4.x) — PK parameters, design schema, randomization/blinding, treatment, stages, **blood sampling**, duration, stop rules, drug accountability, randomization codes…  
5. **Отбор субъектов** (5.x)  
6. **Отбор и исключение добровольцев** (Heading 1 sample title in tree)  
7. **Оцениваемые параметры**  
8. **Безопасность** (8.x)  
9. **Статистика** (9.7.x ANOVA / BE criteria / outliers / safety analysis)  
10. Conduct / compliance / deviations / data storage  
… through **15 Публикации**, then appendices / literature / forms  

**Appendices / forms:** AE / SAE / pregnancy report tables (large merged grids, e.g. T27 61×42)

### 3.3 Tables (index → purpose sketch)

Mapped partially today in `docx_profile.TABLE_KEY_TO_INDEX`:

| idx | Profile key (if any) | Observed header / purpose |
|---|---|---|
| 0 | STUDY_METADATA | Study title / design synopsis line |
| 1 | — | Abbreviations glossary |
| 2 | SYNOPSIS_N | Protocol synopsis block |
| 3 | SIGNATURES | Signature grid |
| 4 | TEST_PRODUCT | Test product (sample: Бозутиниб) |
| 5 | REFERENCE_PRODUCT | Reference (sample: Бозулиф) |
| 6 | PK_PARAMETERS | Primary/secondary PK |
| 7 | SCHEDULE_OF_ASSESSMENTS | SoA |
| 8 | (STATIC lab) | Lab parameters |
| 9 | BLOOD_SAMPLING | Sampling schedule |
| 10 | — | Cotinine / screening tests |
| 11 | MEAL_TIMING | Meal timing |
| 12–15 | — | Vitals / AE severity / causality / seriousness |
| 16 | CV_EVIDENCE | Sample size / CVintra evidence |
| 17+ | — | Forms: AE, SAE (61×42), pregnancy, signatures |

**Full per-cell registry is Phase 29 implementation work** — this audit establishes the inventory baseline, not the complete field map.

### 3.4 Comments policy (preliminary)

- 74 Word comments = authoring instructions inside the source template.  
- **Do not** print review comments into the clean final DOCX.  
- **Do not** strip comments from the **source** template file on disk.  
- Final artifact: follow existing clean-output intent (strip/ignore comment range on export). Exact mechanism to confirm against current `docx_renderer` / Word XML.

### 3.5 Critical template content issue

The template body still contains **product-specific sample data** (e.g. Бозутиниб / Бозулиф, pharmacology §2.8 titled with бозутиниб).  

For UPDCB / other molecules:

- Template = **structure / layout / static normative wording** authority  
- Product-specific strings = **must be overwritten** from Canonical Snapshot + verified evidence  
- Leaving Bosutinib text in an UPDCB protocol = **stale template leakage** (blocker class: `STALE_TEMPLATE_VALUES` / product mismatch)

This is separate from Golden copying — it is “sample content embedded in template”.

---

## 4. Existing registries (reuse, do not fork)

| Registry | Path | Use in Phase 29 |
|---|---|---|
| Docx profile | `docx_profile.py` | Template id, checksum, active section codes, table index map |
| Section tree | `protocol_sections.py` | Logical section codes ↔ generators (align to template headings) |
| Table registry | `table_registry.py` | Numbering |
| Reference registry | `reference_registry.py` | Cross-refs |
| Display values | `display_value_registry.py` | Enums → human RU (no `CROSSOVER_2X2` in body) |
| Text blocks | `protocol_text_blocks.py` | Controlled narrative snippets |

**Gap:** there is **no** first-class `protocol_template_registry.py` that maps every template field → canonical source + render rule + required/optional. Phase 29 must add that registry **on top of** the above, not replace assembly.

---

## 5. Data sources (content authority)

### 5.1 Canonical Study Snapshot

`backend/app/domain/study_snapshot.py` — `StudyCanonicalSnapshot` / `build_canonical_snapshot` / `build_consistency_snapshot`.

Owns (among others): protocol identity, sponsor/orgs, test/reference products, design, food, subject counts, analytes, PK parameters, washout, sampling, statistics summary, evidence summary.

**Workspace path today** often reads a thinner snapshot payload (`candidates` field_path→value) in `build_preview_from_draft` — insufficient for full template fill.

### 5.2 Approved decisions

`decision_engine` / `decision_store` / Decision Center domains (DESIGN, FOOD, WASHOUT, SAMPLING, STATISTICS, …).  
Terminal statuses: `APPROVED` / `REJECTED` / `KEEP_CURRENT`.

### 5.3 StatisticsPlan

`statistics_engine` / `statistics_store` — APPROVED plan: primary BE, population, transform, model, CI, acceptance interval, parameter roles.

### 5.4 Sample size

`sample_size_engine` / store — ACCEPTED calculation: CV, power, alpha, ratio, evaluable/randomized N, assumptions.

### 5.5 Evidence / provenance

Research claims (`verification_status`, `applicability`), regulatory evidence, fact_sources on DecisionContext (`EXPERT_INPUT`, verified extraction, etc.).

**Render rule (product TZ):**  
`CANONICAL → VERIFIED/APPROVED → RENDER`  
Forbidden as final text sources: raw extraction, unverified AI, stale template product values, Golden DOCX values, Legacy Project values when workspace is authoritative.

---

## 6. Placeholder / missing-value policy (current vs required)

| Current workspace stub | Required Phase 29 |
|---|---|
| Inserts `"—"` for missing facts | Required fields → **BLOCK** DOCX with field/section/reason |
| Prints debug English sentences | Forbidden in final artifact |
| May print internal enums | Must use `display_value_registry` / existing humanizers |

Template has **no** `{{TOKEN}}` markers — fill strategy must be **registry-driven section/table cell targeting** (as `docx_renderer` already does), not global find/replace.

---

## 7. Preflight (DOCX-specific) — gaps vs TZ §30

Existing: `build_preflight`, `detect_stale_protocol_dependencies`, docx_renderer gates for REVIEW/FINAL.

Still need explicit DOCX codes (extend, do not replace):

- `REQUIRED_TEMPLATE_SECTIONS`
- `MISSING_REQUIRED_FIELDS`
- `UNRESOLVED_CONFLICTS` (esp. reference dose 15 vs 30)
- `UNVERIFIED_CRITICAL_EVIDENCE`
- `STALE_SNAPSHOT` / `STALE_STATISTICS` / `STALE_SAMPLE_SIZE`
- `MISSING_PROTOCOL_DRAFT`
- `PLACEHOLDERS` / debug text / enum leakage
- `NUMBERING_INCONSISTENCY` / `CROSS_REFERENCE_ERROR`
- `TEMPLATE_STRUCTURE_ERROR` / checksum mismatch
- `STALE_TEMPLATE_PRODUCT` (Bosutinib left in non-Bosutinib study) — recommended add

CRITICAL → block generation.

---

## 8. Template vs Golden differences (policy)

| Authority | Role |
|---|---|
| Template DOCX | Structure, styles, tables, forms, normative static text |
| Canonical + approved/verified state | Dynamic medical/administrative values |
| Golden PКИ | Regression / coverage checklist only |

If Template ≠ Golden wording: **document the difference; do not silently prefer Golden text.**

Known expected divergence examples to track in implementation:

- Product names / doses (Bosutinib template sample vs UPDCB case)  
- Reference dose conflict: Golden may show one dose; unresolved conflict must **BLOCK** or use explicit expert APPROVED choice — never auto-pick from Golden.

---

## 9. Mapping sketch (initial — not complete registry)

| Template area | Canonical / approved source | Notes |
|---|---|---|
| Protocol title / id / date | Snapshot study + protocol metadata | Overwrite sample title |
| Sponsor / sites / labs | Snapshot orgs | |
| Test / reference product tables | Snapshot products + APPROVED product decisions | Conflict on dose → block |
| Design narrative | APPROVED design + display registry | No raw enums |
| Food | APPROVED food / verified facts | |
| Washout | APPROVED washout only | Renderer must not recalculate |
| Sampling table T10 | Canonical sampling plan + verified Tmax/t½ deps | Missing expected Tmax → block dependent section |
| PK table T07 | Approved PK / statistics parameter roles | Not hardcode UPDCB list globally |
| Statistics §9.7 | APPROVED StatisticsPlan | Replace stub phrase |
| Sample size / CV table T17 | ACCEPTED sample size | |
| SoA T08 | Procedure schedule when present | PRESERVE static rows where profile says STATIC |
| Safety / SAE / pregnancy forms | Mostly preserve template structure; fill identity fields only | |
| TOC | Preserve field; refresh if supported | Do not replace with plain text |
| Comments | Strip from output | Keep in source template |

---

## 10. Recommended implementation plan (after audit sign-off)

1. **Wire workspace DOCX** to template path:  
   assemble workspace-canonical payload → `render_protocol_docx` (or thin adapter), **delete** `Document()` stub for production path (keep behind flag only if needed for tests).
2. Add `protocol_template_registry.py` (or extend `docx_profile`) with full field inventory from template.  
3. Bridge Phase 15–16 stores (decisions, stats, sample size, gaps) into the assembly context used by generators.  
4. Extend DOCX preflight per §7.  
5. Tests demanded by TZ §33 (`test_phase29_template_*`).  
6. Golden structural regression against Downloads golden (fixture copy into `fixtures/golden/` only when explicitly approved).  
7. Bump version → **0.34.0**.

**Do not** invent a second assembly architecture. Reuse Assembly Engine + existing `docx_renderer`.

---

## 11. Acceptance checklist (from TZ — audit coverage)

| Criterion | Audit status |
|---|---|
| Template located & loadable | Done |
| Template inventory exists | Baseline JSON + this doc; full field-level registry = implementation |
| Mapping registry exists | Partial (`docx_profile` + section tree); full field registry TBD |
| Dual-path problem identified | Done |
| Golden located | External Downloads; not in-repo |
| Data provenance model identified | Done |
| Coding of new renderer | **Not started** (per TZ: audit first) |

---

## 12. Known blockers before coding

1. ~~Confirm product identity of repo template ≡ Downloads «Шаблон … v2.0»~~ — **Confirmed byte-identical** (SHA-256 match).  
2. Decide how to store Golden PКИ for CI (Downloads path known; import into `fixtures/golden/` only with explicit approval). Fixture `golden_protocol.docx` already exists for UPDCB package — clarify whether it equals PКИ corr 31.08 before using in regression.  
3. Header already carries Bosutinib / placeholder protocol code / version — must be driven by study facts (`_apply_header_footer_vars` exists).  
4. Complete field-level cell registry for all 33 tables (inventory baseline done).  
5. Uncommitted workspace stability fixes (hydrate / package / approvals) should land before relying on draft→DOCX E2E.

---

## 13. Scratch artifacts

| File | Purpose |
|---|---|
| `docs/_phase29_template_inventory.json` | Raw inventory |
| `docs/_phase29_audit_compact.json` | Compact inventory summary |
| `docs/_phase29_fs_search.json` | Filesystem search for template/golden |
| `docs/_phase29_inventory_print.txt` | Human-readable heads/tables |
| `docs/_phase29_inventory_script.py` / `_phase29_inventory_print.py` | Re-run helpers |

These are audit aids, not production modules.

---

**PHASE 29 TEMPLATE AUDIT COMPLETE — ready for implementation planning / coding only after explicit go-ahead.**
