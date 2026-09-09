# Beta Issue Log

Severity: P0 Critical · P1 Major · P2 Moderate · P3 Minor

| ID | Case | Stage | Problem | Severity | Frequency | Impact | Repeatability | Root Cause | Fix | Regression Test | Status |
|----|------|-------|---------|----------|-----------|--------|---------------|------------|-----|-----------------|--------|
| B-001 | REAL-UPDCB | Conflict | Dose conflict stays OPEN | Monitor | Known golden | Blocks FINAL until expert | High | Invariant | Keep gate | conflict_benchmark | **Monitor** |
| B-002 | Schema | Subjects | Population schema gap? | — | — | — | — | Resolved | None | population_gap | **Schema RESOLVED** |
| B-002-PACK | Intake | Fixtures | &lt;10 distinct full REAL | P1 | Persistent | Blocks beta entry | High | Packages not provided | Writer intake | population_status / phase23 | **Open** |
| B-003 | Writer time | Metrics | Need ≥5 observed paired sessions | P1 | Persistent | Blocks ROI/time study | High | Writers not run | Timed pairs + gate | phase23_beta_gate | **Open** |
| B-004 | Incomplete | Completeness | MISSING labels | P2 | Occasional | UX | Med | Incomplete packages | Defer | — | Open |
| B-005 | Postgres | Env | Compose Postgres + backup/restore/restart | P1 | Persistent | Blocks Controlled Beta | High | Docker/ops not executed | docker-compose.beta on capable host | phase23_beta_gate | **Open / BLOCKED** |
| B-006 | Research | Real corpus | Research usefulness | P2 | Low n | Metrics thin | Med | Few packages | Defer | — | Open |

## Priority

`Priority Score ≈ Severity × Frequency × Impact`  
Do not optimize P2/P3 before P1 evidence is understood.

## Phase 25 notes

- Handoff package: `docs/BETA_HOST_HANDOFF.md`, `.env.example`, `scripts/start_beta.*`
- Smoke/diagnostics scripts ready; Docker runtime **NOT_EXECUTED** on prior host
- `GET /api/version` — no secrets
- TEST/SYNTHETIC never count as REAL
- Gate requirements **not** weakened — still **BETA_NOT_READY**
