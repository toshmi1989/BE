# First Writer Session Checklist

## Before

- [ ] Beta environment ready (`python scripts/beta_preflight.py` — no BLOCK)
- [ ] Postgres active (`docker compose -f docker-compose.beta.yml ps`)
- [ ] Auth active (`AUTH_REQUIRED=true`, strong `AUTH_SECRET`)
- [ ] Package sanitized (`REAL_PACKAGE_SANITIZED=yes`)
- [ ] Writer assigned (pseudonym)
- [ ] Baseline instructions provided (`docs/WRITER_QUICKSTART.md`)

## During

- [ ] Manual session started (timer)
- [ ] Manual timings captured on stop
- [ ] Assisted session started (same `pair_id`)
- [ ] Assisted timings captured on stop
- [ ] Review events captured
- [ ] Corrections classified

## After

- [ ] Protocol reviewed
- [ ] DOCX reviewed
- [ ] Feedback recorded
- [ ] Session completed
- [ ] Backup executed
- [ ] Metrics exported (`GET /api/field-study/export`)

## Do not

- [ ] Estimate times
- [ ] Count synthetic packages as REAL
- [ ] Let AI approve medical decisions
