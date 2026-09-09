# Domain Model (Phase 11A+)

## Aggregate additions

```text
Project
 ├── ProtocolDraft[]
 │    ├── ProtocolSection[] / ProtocolTable[] / ProtocolReference[]
 │    └── ProtocolBuildReport
 └── GeneratedDocument[]  (versioned DOCX outputs under generated/{project_id}/)
```

## Canonical Study flow

```text
Study Model
    ↓
Canonical Study Snapshot (StudyCanonicalSnapshot)
    ↓
ProtocolDraft (+ TableRegistry / ReferenceRegistry)
    ↓
DOCX
```

**ONE STUDY VALUE → ONE CANONICAL SOURCE → MANY PROTOCOL SECTIONS**

| Concern | Canonical source |
|---------|------------------|
| Subject counts (evaluable / randomized / screened / reserve) | `SubjectPlan` |
| Sample size math result | `SampleSizeCalculation` (must sync/align with SubjectPlan) |
| Sampling points | `SamplingPlan` via `get_canonical_sampling_plan()` |
| Product / Reference | Product / ReferenceProduct entities |
| Design / Food / Eligibility | Design / FoodCondition / Eligibility |
| Enum display text | `DisplayValueRegistry` (`resolve_display`) |
| Table numbers | `TableRegistry` |
| Cross-refs | `ReferenceRegistry` |
| Placeholders | `PlaceholderRegistry` |
| Static template SOP blocks | `STATIC_VERIFIED` / `LEGACY_UNCONTROLLED` in `static_blocks` |

Consistency: `validate_canonical_consistency()` → `DocumentConsistencyReport`.

## PK / Sampling — TmaxCaptureWindow

```text
tmax_min, tmax_max + PK.SAMP.DENSITY.v1
        ↓
 TmaxCaptureWindow (window_min/max, density_requirement, rule_id, status)
        ↓
   ┌────┴────┐
Sampling   Validation
Engine     Engine
```

- Single reusable domain object; both engines must consume it (no divergent capture math).
- Rule status stays **PROPOSED** until a verified regulatory source is attached.
- Point-estimate Tmax (`min == max`) expands via rule margins (e.g. 6→4.5–7.5 under current params).

## DOCX Rendering (Phase 9)

```text
ProtocolDraft → DocxTemplateProfile → DOCX Renderer → GeneratedDocument
                     ↓
              DocxValidationReport
```

- Template: `BE_Protocol_Template_v2.0.docx` (immutable; checksum verified)
- Product/synopsis tables filled by **label match**, not row index
- No raw enums in generated protocol text (`RAW_ENUM_IN_DOCUMENT`)
- Modes: DRAFT (may show `{{...}}`), REVIEW/FINAL (critical unresolved → BLOCKED)
- Never invent N/A / ХХ / XXX
- TOC Word fields left for update-on-open (documented)

## Protocol Assembly (Phase 8)

Structured ProtocolDraft + HTML preview; Phase 11A adds registries + canonical consistency report on build.
