# Phase 20 — Field Study Report

**Version:** 0.25.0  
**Executed:** see `fixtures/field_study/phase20_ops_evidence.json`

## Policy adherence

- No synthetic packages counted as REAL
- No fabricated ROI / estimated / remembered timings
- No extrapolation from UPDCB n=1 conflict metrics to population-level claims
- No PRODUCTION-READY claim from tests alone
- P2/P3 defects recorded; not blindly fixed

## 1. Real package count

| Class | Count |
|-------|------:|
| Full REAL (sanitized) | **1** |
| REAL_PARTIAL | **1** |
| Empty intake slots | **8** |
| Meets ≥10 full REAL | **NO** (explicit limitation) |

Packages: `REAL-UPDCB-02-BE-2026`, `REAL-DESIGN-ONLY-UPDCB`  
Registry: `fixtures/real_packages/registry.json`  
Intake manifest API: `GET /api/field-study/real-packages`

## 2. Writer count

**0** writers completed paired field-study sessions in this execution environment.

Infrastructure supports pseudonymous `writer_id` / paired MANUAL + SYSTEM_ASSISTED sessions (`POST /api/field-study/pairs`).

## 3. Study patterns

Covered in-repo: conflicting documents, incomplete package, complete SmPC, crossover-like.  
Not covered (empty slots): fed, fasting+fed, different API, missing CVintra, long HL/parallel, replicate, legacy-as-input, incomplete SmPC diversity.

## 4. Session methodology

Paired design: Session A manual baseline → Session B system-assisted (prefer same writer).  
Sanitization gate enforced: unsanitized / unknown packages cannot start sessions.  
Required events catalog unchanged from Phase 19. Sensitive excerpts stripped from event payloads.

## 5–8. Timing / ROI

| Metric | Result |
|--------|--------|
| Median manual time | **unpublished** (no observed paired sessions) |
| Median assisted time | **unpublished** |
| Median review time | **unpublished** |
| Median time saved | **unpublished** |
| P25 / P75 | **unpublished** |

Aggregate publish gate: `n >= 5` paired ROI-eligible sessions (`MIN_PAIRED_FOR_AGGREGATE`).  
Per-session TIME_SAVING still requires direct observation of both sides.

**B-003 remains OPEN** — infrastructure ≠ observed data.

## 9. Extraction results

No writer field classifications recorded in live sessions.  
Classification API ready; `CORRECT_AFTER_REVIEW` ≠ automatic success.

## 10. Conflict results

UPDCB case-level (reliable labels, **n=1**): precision 1.0, recall 1.0.  
**Not** validated population-level performance.

## 11–13. Evidence / research / decisions

No live writer evidence/research/decision workload observations recorded.  
APIs: `/metrics/evidence`, `/metrics/research`, `/metrics/decisions`.

## 14–15. Sample size / statistics

No new formulas. Engine review statuses ACCEPTED/MODIFIED/REJECTED/BLOCKED supported on sessions. No live writer reviews recorded.

## 16. Protocol quality

Domain review API ready; no live writer protocol corrections recorded.

## 17. Writer feedback

Template extended (friction, least trusted, desired automation, never automate). No completed feedback rows.

## 18. Repeated defects

| Defect | Sev | Freq | Impact | Action |
|--------|-----|------|--------|--------|
| Dose conflict OPEN (expected) | Monitor | Known golden | Blocks FINAL until expert | Keep |
| <10 REAL packages | P1 | Persistent | Blocks field-study power | Intake |
| No paired timings | P1 | Persistent | Blocks ROI / B-003 | Run writers |
| Docker/Postgres absent here | P1 | Env | Full beta compose not run | Partial ops |

## 19. B-002

**Schema:** RESOLVED — `subjects.*` vocabulary sufficient on observed packages; no invented medical rule.  
**Package population:** OPEN — still 1 full REAL.

## 20. B-003

**OPEN** — requires actual observed paired writer sessions (manual + assisted + review).

## 21. B-005

**PARTIAL execution evidence:**

| Check | Result |
|-------|--------|
| AUTH_REQUIRED=true | Yes (ops script) |
| AUTH_SECRET configured | Yes |
| Backup → hydrate restore | **EXECUTED_OK** (file DB) |
| Restart durability (cache clear + hydrate) | **EXECUTED_OK** |
| docker-compose.beta Postgres | **NOT_EXECUTED** (Docker unavailable on host) |

Evidence file: `fixtures/field_study/phase20_ops_evidence.json`

## 22. Production gate

**NOT READY**

Blockers: <10 full REAL packages; zero completed paired writer sessions; timing aggregates unpublished; Postgres compose not executed in this environment.

---

## PHASE 20 COMPLETE — Final Report

```
PHASE 20 COMPLETE

Version: 0.25.0
Real full packages: 1
Real partial packages: 1
Synthetic regression packages: Phase 18 suite (not counted as REAL)
Writers: 0 completed paired sessions
Paired sessions: 0
Study patterns: conflict + incomplete covered; diversity slots empty

Median manual time: unpublished
Median assisted time: unpublished
Median review time: unpublished
Median time saved: unpublished
P25: unpublished
P75: unpublished

Extraction accuracy: not observed (writer classifications pending)
Wrong value rate: not observed
Missing rate: not observed
Provenance completeness: not observed

Conflict precision: 1.0 (UPDCB n=1 case-level only)
Conflict recall: 1.0 (UPDCB n=1 case-level only)

Research usefulness: not observed on real writer runs
Decision workload: not observed

Protocol correction rate: not observed
DOCX correction rate: not observed

B-002: Schema RESOLVED; package population OPEN
B-003: OPEN (no observed paired timings)
B-005: PARTIAL (file-DB backup/restore + restart OK; Postgres compose not executed)

P0: none new
P1: package intake; paired writer study; Postgres compose on capable host
P2: B-004 incomplete labeling; B-006 research corpus
P3: deferred cosmetics

Backup/restore: EXECUTED_OK (AUTH_REQUIRED file DB)
Restart durability: EXECUTED_OK
Postgres: compose NOT_EXECUTED (Docker absent)
Regression: Phase 19/20 tests + prior suites required green
Golden: required green
AI-off: required green

Production readiness: NOT READY

Recommended Phase 21: Obtain ≥9 additional sanitized distinct REAL packages; run ≥5 paired writer sessions with observed timings; execute docker-compose.beta backup/restore on a Postgres host; then re-evaluate CONTROLLED BETA gate.
```
