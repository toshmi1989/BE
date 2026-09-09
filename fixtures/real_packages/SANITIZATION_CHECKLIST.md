# Real Package Sanitization Checklist (Phase 19)

Before any REAL package is loaded into beta dataset:

## Blockers (must be NO)

| Check | Present? |
|-------|----------|
| Patient identifiers / subject names | |
| Medical record numbers | |
| Signatures (handwritten / scanned personal) | |
| Personal phone / email of subjects | |
| Home addresses of subjects | |
| Credentials / API keys / passwords | |
| Secrets / tokens | |
| Unredacted confidential metadata not needed for protocol drafting | |

## Allowed (study metadata)

- Sponsor / CRO / site organization names (as in protocol admin)
- Product / dose / SmPC text
- Study design / sampling / statistics method text
- Writer notes without PII

## Gate

```
REAL PACKAGE SANITIZED = yes | no
```

If **no** → do **not** load into beta dataset.

Record in package registry:

- `sanitized: true|false`
- `sanitization_notes`
- `sanitized_by` (role, not personal email if avoidable)
- `sanitized_at`

Automation must **not** attempt to discover or extract sensitive personal data beyond refusing known PII patterns in filenames during intake validation.
