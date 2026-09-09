# Golden comparison (Phase 10)

Comparison is **structural**, not byte-identical.

## Baseline

- Template: `templates/protocol/BE_Protocol_Template_v2.0.docx`
- Checksum (sha256): `8e6be6aa6f0514dc4ba6a1016feb141946a2ded538a58d306bcf0fa68725d8a6`
- Tables in template: **33**
- Paragraphs in template: **1432**

## Generated DRAFT (Bosutinib golden)

Artifacts live under versioned folders:

`golden/bosutinib-ai-off-<UTC>/`

| Check | Expected | Result |
|-------|----------|--------|
| Template checksum unchanged after render | yes | yes |
| Generated table count | 33 | 33 (see `docx-draft-validation.json`) |
| File opens (python-docx / OOXML) | yes | yes |
| Byte equality with template | **not required** | n/a |
| Protocol number present when set | `BE-BOS-400-GOLDEN` | see `structural-comparison.json` |
| Headings / section markers | present | present |
| Unresolved org/sponsor placeholders | allowed in DRAFT | allowed |
| FINAL DOCX without sponsor | BLOCKED | BLOCKED (correct) |

## Section / table inventory alignment

Mapped against `docs/DOCX_TEMPLATE_INVENTORY.md` and `docs/DOCX_TABLE_INVENTORY.md`:

- Dynamic fills: T01/T03/T05/T06/T07/T10/T17 where ProtocolDraft tables exist
- Appendices T18–T33: preserved from template (static forms)
- Body headings used as anchors (not TOC paragraph indexes)

## Critical values (template-sourced)

| Value | Source in golden fixture | Used in Study |
|-------|--------------------------|---------------|
| tmax ≈ 6 h | template body excerpt | yes |
| t½ = 35.5 h | template body excerpt | yes |
| Cmax CVintra >30% | template body excerpt | planning floor CV=30 (expert note) |
| FED / 400 mg / Bosulif | template excerpts | yes |
| Sponsor | **missing** | FINAL blocked |
| Investigator | **missing** | unresolved |

## Not compared

- Exact Word layout / kerning / floating objects
- TOC page numbers (Word field update-on-open)
- Byte-level ZIP equality
