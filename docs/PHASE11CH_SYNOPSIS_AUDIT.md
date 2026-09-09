# Phase 11C-H — Synopsis unmatched cell audit (T03)

**Template:** `BE_Protocol_Template_v2.0.docx`  
**Table:** T03 (index 2) — 33 rows × 3 cols (merged label/value)

## Classification legend

| Kind | Meaning |
|---|---|
| SUBJECT_COUNT | Template SubjectPlan-like N=46 — must replace |
| TOC_PAGE_NUMBER | Word TOC page digit — safe to preserve |
| CV_OR_BARE_N | Bare `46` in CV evidence table — not SubjectPlan |
| ADMIN_PLACEHOLDER | Sponsor/org template stubs — fill from canonical |
| SAFE_NARRATIVE | No subject-count 46 — preserve or later P2 |

## Unmatched / residual cells (pre-11C-H)

| Location | Reason not matched by SYNOPSIS_N metrics | Current content (snip) | Subject-related | Safe to preserve | Must replace |
|---|---|---|---|---|---|
| T03 R03 «Спонсор исследования» | Metric labels ≠ «Спонсор…» | «Наименование спонсора, страна» | No (admin) | No | Yes — canonical Sponsor |
| T03 R04 «Ответственные лица…» | No person mapping | «ФИО / Тел / почта» | No (admin) | No | Yes — Person SPONSOR_* |
| T03 R05 «Главный исследователь» | No person mapping | «ФИО, профессия» | No (admin) | No | Yes — PI Person |
| T03 R06 monitoring org | No org mapping | Legacy CRO/center boilerplate | No (admin) | No | Yes — key org when present |
| T03 R07 «Исследовательский центр» | No org mapping | Legacy site address | No (admin) | No | Yes — CLINICAL_CENTER |
| T03 R08 «Аналитическая лаборатория» | No org mapping | «Название / адрес» | No (admin) | No | Yes — LAB org |
| T03 R12 «Исследуемая популяция» | Labels were «Оцениваемые/Рандомизированные» only | `Рандомизированные добровольцы: 46` (+ screen 53 / doubles 7) | **Yes** | **No** | **Yes** — SubjectPlan N |
| T03 R15 «Сбор образцов крови…» | No blood-row mapping | `у 46 добровольцев` | **Yes** | **No** | **Yes** — randomized_n phrase |
| Body P1162 (pre-§9 replace) | Outside SYNOPSIS_N table fill | `участие 46 добровольцев` | **Yes** | **No** | **Yes** — cleared by ACTIVE §9.2 replace |
| TOC P60/P61 | N/A (not a data cell) | `…\t46` page numbers | **No** | **Yes** | **No** — `TOC_PAGE_NUMBER` |
| T17 (idx 16) R1C2 | CV evidence n_total | bare `46` | **No** | **Yes*** | **No** for SubjectPlan gate (*overwritten when CV_EVIDENCE rebuilt) |

## Control after 11C-H

- T03 admin rows filled via `build_synopsis_admin_rows` (canonical Sponsor/Person/Org)
- T03 R12/R15 rewritten via `rewrite_subject_count_text` (deterministic; **no global digit scrub**)
- REVIEW/FINAL gated by `find_legacy_subject_count_46` (ignores TOC tabs + bare CV `46`)
- `LEGACY.SYNOPSIS_N46` **removed** → `DYN.SYNOPSIS_SUBJECT_N`
- SYNOPSIS_CORE includes `sponsor_name` from same `resolve_sponsor` as §1.2

## Subject count single source

`SubjectPlan` → `get_canonical_subject_counts` → consistency snapshot → SYNOPSIS_CORE / SYNOPSIS_N / §2.6 / §9.2 / T03 subject-count cells.
