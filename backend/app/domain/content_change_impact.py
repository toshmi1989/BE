"""ContentChangeImpact — Phase 12C.

Maps canonical field changes → affected protocol sections/blocks/tables/QA.
Does not mutate Study. Does not invent medical policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.validation_graph import NODE_ALIASES, change_impact as validation_change_impact


# Canonical field path → content sections / tables / QA families (deterministic).
FIELD_CONTENT_MAP: dict[str, dict[str, list[str]]] = {
    "sponsor.name": {
        "sections": ["1.1", "1.2", "1.8", "SYNOPSIS", "16", "17"],
        "tables": ["STUDY_METADATA", "SIGNATURES"],
        "qa_rules": ["IDENTITY", "LEGACY", "ADMINISTRATION"],
    },
    "sponsor": {
        "sections": ["1.1", "1.2", "1.8", "SYNOPSIS", "16", "17"],
        "tables": ["STUDY_METADATA", "SIGNATURES"],
        "qa_rules": ["IDENTITY", "LEGACY", "ADMINISTRATION"],
    },
    "product.dosage": {
        "sections": ["1", "2", "2.1", "SYNOPSIS", "4", "6", "9", "17"],
        "tables": ["TEST_PRODUCT"],
        "qa_rules": ["IDENTITY", "LEGACY", "PK"],
    },
    "product.dose": {
        "sections": ["1", "2", "2.1", "SYNOPSIS", "4", "6", "9", "17"],
        "tables": ["TEST_PRODUCT"],
        "qa_rules": ["IDENTITY", "LEGACY", "PK"],
    },
    "product.trade_name": {
        "sections": ["1", "2", "SYNOPSIS", "4", "17"],
        "tables": ["TEST_PRODUCT"],
        "qa_rules": ["IDENTITY", "LEGACY"],
    },
    "product": {
        "sections": ["1", "2", "SYNOPSIS", "4", "6", "17"],
        "tables": ["TEST_PRODUCT"],
        "qa_rules": ["IDENTITY", "LEGACY"],
    },
    "reference_product": {
        "sections": ["1", "3", "SYNOPSIS", "4", "17", "18"],
        "tables": ["REFERENCE_PRODUCT"],
        "qa_rules": ["IDENTITY", "REFERENCES"],
    },
    "design.type": {
        "sections": ["SYNOPSIS", "4", "4.1", "9", "17"],
        "tables": [],
        "qa_rules": ["DESIGN", "STATISTICS"],
    },
    "design": {
        "sections": ["SYNOPSIS", "4", "4.1", "9", "17"],
        "tables": [],
        "qa_rules": ["DESIGN", "STATISTICS"],
    },
    "subjects.planned_randomized_n": {
        "sections": ["SYNOPSIS", "4", "9", "9.2", "16"],
        "tables": ["SYNOPSIS_N"],
        "qa_rules": ["SUBJECTS", "STATISTICS"],
    },
    "subjects.randomized_n": {
        "sections": ["SYNOPSIS", "4", "9", "9.2", "16"],
        "tables": ["SYNOPSIS_N"],
        "qa_rules": ["SUBJECTS", "STATISTICS"],
    },
    "subjects": {
        "sections": ["SYNOPSIS", "4", "9", "9.2", "16"],
        "tables": ["SYNOPSIS_N"],
        "qa_rules": ["SUBJECTS", "STATISTICS"],
    },
    "sampling.points": {
        "sections": ["SYNOPSIS", "4", "6", "6.1", "16"],
        "tables": ["BLOOD_SAMPLING", "SCHEDULE_OF_ASSESSMENTS"],
        "qa_rules": ["SAMPLING"],
    },
    "sampling": {
        "sections": ["SYNOPSIS", "4", "6", "6.1", "16"],
        "tables": ["BLOOD_SAMPLING", "SCHEDULE_OF_ASSESSMENTS"],
        "qa_rules": ["SAMPLING"],
    },
    "pk.tmax": {
        "sections": ["SYNOPSIS", "4", "6", "7", "9"],
        "tables": ["PK_PARAMETERS", "BLOOD_SAMPLING"],
        "qa_rules": ["PK", "SAMPLING"],
    },
    "tmax": {
        "sections": ["SYNOPSIS", "4", "6", "7", "9"],
        "tables": ["PK_PARAMETERS", "BLOOD_SAMPLING"],
        "qa_rules": ["PK", "SAMPLING"],
    },
}


@dataclass
class ContentChangeImpact:
    changed_field: str
    old_value: Any
    new_value: Any
    affected_sections: list[str] = field(default_factory=list)
    affected_blocks: list[str] = field(default_factory=list)
    affected_tables: list[str] = field(default_factory=list)
    affected_references: list[str] = field(default_factory=list)
    affected_qa_rules: list[str] = field(default_factory=list)
    rebuild_required: bool = True
    validation_revalidate: list[str] = field(default_factory=list)
    graph_version: str = "CONTENT.IMPACT.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_field(field_path: str) -> str:
    f = (field_path or "").strip()
    if f in FIELD_CONTENT_MAP:
        return f
    # Try alias via validation graph
    node = NODE_ALIASES.get(f, f)
    if f.startswith("product.") and "product.dosage" in FIELD_CONTENT_MAP:
        if f.endswith("dosage") or f.endswith("dose"):
            return "product.dosage"
    if f in ("dose", "dosage"):
        return "product.dosage"
    if node == "subjects" and f not in FIELD_CONTENT_MAP:
        return "subjects"
    if node == "sampling":
        return "sampling"
    if node == "design":
        return "design"
    if node == "pk":
        return "tmax"
    # Prefix match longest key
    candidates = [k for k in FIELD_CONTENT_MAP if f.startswith(k) or k.startswith(f)]
    if candidates:
        return sorted(candidates, key=len, reverse=True)[0]
    return f


def compute_content_change_impact(
    *,
    changed_field: str,
    old_value: Any = None,
    new_value: Any = None,
    assembled_before: dict | None = None,
    assembled_after: dict | None = None,
) -> ContentChangeImpact:
    """Build ContentChangeImpact for a single canonical field change."""
    key = _normalize_field(changed_field)
    mapping = FIELD_CONTENT_MAP.get(key, {"sections": [], "tables": [], "qa_rules": []})
    sections = list(mapping.get("sections") or [])
    tables = list(mapping.get("tables") or [])
    qa_rules = list(mapping.get("qa_rules") or [])

    # Validation-graph dependents (existing, not duplicated)
    val = validation_change_impact(key.split(".")[0] if "." in key else key)
    revalidate = list(val.get("revalidate") or [])

    affected_blocks: list[str] = []
    affected_refs: list[str] = []
    if assembled_before and assembled_after:
        before_texts = _section_text_map(assembled_before)
        after_texts = _section_text_map(assembled_after)
        for code in sorted(set(before_texts) | set(after_texts)):
            if before_texts.get(code) != after_texts.get(code):
                if code not in sections:
                    sections.append(code)
                for bid in _changed_block_ids(assembled_before, assembled_after, code):
                    affected_blocks.append(bid)
        # Detect old value lingering
        if old_value is not None and str(old_value):
            blob = _all_text(assembled_after)
            if str(old_value) in blob and str(old_value) != str(new_value):
                affected_blocks.append("STALE_SCAN:old_value_still_present")

    return ContentChangeImpact(
        changed_field=changed_field,
        old_value=old_value,
        new_value=new_value,
        affected_sections=sorted(set(sections)),
        affected_blocks=sorted(set(affected_blocks)),
        affected_tables=sorted(set(tables)),
        affected_references=sorted(set(affected_refs)),
        affected_qa_rules=sorted(set(qa_rules)),
        rebuild_required=True,
        validation_revalidate=revalidate,
    )


def detect_stale_content(
    *,
    assembled: dict,
    canonical_values: dict[str, Any],
) -> list[dict[str, Any]]:
    """Find dynamic text that still shows superseded canonical values.

    Returns findings with code CONTENT.STALE_VALUE. Does not mutate content.
    """
    findings: list[dict[str, Any]] = []
    blob_by_section = _section_text_map(assembled)
    for field_path, expected in (canonical_values or {}).items():
        if expected is None or expected == "":
            continue
        # Optional: old_value key pattern field -> (old, new)
        if isinstance(expected, dict) and "new" in expected:
            old_v = expected.get("old")
            new_v = expected.get("new")
            if old_v is None or new_v is None:
                continue
            for sec, text in blob_by_section.items():
                if str(old_v) in text and str(new_v) not in text:
                    findings.append(
                        {
                            "code": "CONTENT.STALE_VALUE",
                            "severity": "ERROR",
                            "blocking": True,
                            "field": field_path,
                            "section": sec,
                            "message": f"Stale value {old_v!r} present; expected {new_v!r}",
                            "old_value": old_v,
                            "new_value": new_v,
                        }
                    )
                elif str(old_v) in text and str(new_v) in text:
                    # both present — still flag stale occurrence
                    findings.append(
                        {
                            "code": "CONTENT.STALE_VALUE",
                            "severity": "WARNING",
                            "blocking": False,
                            "field": field_path,
                            "section": sec,
                            "message": f"Old value {old_v!r} still appears alongside {new_v!r}",
                            "old_value": old_v,
                            "new_value": new_v,
                        }
                    )
        else:
            # Presence check only for mismatch when provided as {field: value} vs draft marker
            pass
    return findings


def _section_text_map(assembled: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for s in assembled.get("sections") or []:
        code = str(s.get("section_code") or "")
        parts: list[str] = []
        for b in s.get("content_blocks") or []:
            if b.get("text"):
                parts.append(str(b["text"]))
            if b.get("display_text"):
                parts.append(str(b["display_text"]))
            for it in b.get("items") or []:
                parts.append(str(it))
        out[code] = "\n".join(parts)
    return out


def _all_text(assembled: dict) -> str:
    return "\n".join(_section_text_map(assembled).values())


def _changed_block_ids(before: dict, after: dict, section_code: str) -> list[str]:
    def blocks(a: dict) -> dict[str, str]:
        for s in a.get("sections") or []:
            if str(s.get("section_code")) != section_code:
                continue
            m: dict[str, str] = {}
            for b in s.get("content_blocks") or []:
                key = str(b.get("block_code") or b.get("table_key") or id(b))
                m[key] = str(b.get("text") or b.get("display_text") or "")
            return m
        return {}

    b0, b1 = blocks(before), blocks(after)
    changed = []
    for k in sorted(set(b0) | set(b1)):
        if b0.get(k) != b1.get(k):
            changed.append(f"{section_code}:{k}")
    return changed
