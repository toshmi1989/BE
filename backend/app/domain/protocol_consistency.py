"""Protocol consistency checks — Synopsis ↔ sections critical values."""

from __future__ import annotations

from typing import Any

from app.domain.validation_types import IssueDraft


def validate_protocol_consistency(
    *,
    consistency: dict,
    sections: list[dict],
    tables: list[dict],
) -> list[IssueDraft]:
    """Critical values must match across synopsis and body sections."""
    issues: list[IssueDraft] = []

    def _block(field: str, message: str, details: dict | None = None) -> None:
        issues.append(
            IssueDraft(
                category="PROTOCOL_CONSISTENCY",
                severity="CRITICAL",
                rule_id="PROTOCOL.CONSISTENCY",
                entity_type="ProtocolDraft",
                entity_id=None,
                field=field,
                message=message,
                details=details or {},
                source_ids=[],
                blocking=True,
            )
        )

    # Collect rendered text for scanning
    blob_parts: list[str] = []
    for s in sections:
        for b in s.get("content_blocks") or []:
            if b.get("text"):
                blob_parts.append(str(b["text"]))
            for item in b.get("items") or []:
                blob_parts.append(str(item))
    for t in tables:
        for row in t.get("rows") or []:
            blob_parts.extend(str(c) for c in row)
    blob = "\n".join(blob_parts)

    design = consistency.get("design")
    if design and design not in blob and design != "CUSTOM":
        # Design may appear as humanized text; require presence in synopsis OR design section
        from app.domain.display_value_registry import resolve_display

        human = resolve_display(design, context="design_short", fallback=design)
        human_full = resolve_display(design, context="design", fallback=design)
        syn = next((s for s in sections if s.get("section_code") == "SYNOPSIS"), None)
        syn_text = " ".join(
            str(b.get("text") or "") for b in (syn or {}).get("content_blocks") or []
        )
        if (
            design not in syn_text
            and human not in syn_text
            and human_full not in syn_text
            and design not in blob
            and human not in blob
        ):
            _block("design", f"Design {design} missing from Synopsis", {"design": design})

    food = consistency.get("food_condition")
    if food:
        from app.domain.display_value_registry import resolve_display

        food_human = resolve_display(food, context="food", fallback=food)
        syn = next((s for s in sections if s.get("section_code") == "SYNOPSIS"), None)
        syn_text = " ".join(
            str(b.get("text") or "") for b in (syn or {}).get("content_blocks") or []
        )
        food_sec = next((s for s in sections if s.get("section_code") == "6.2.1"), None)
        food_text = " ".join(
            str(b.get("text") or "") for b in (food_sec or {}).get("content_blocks") or []
        )
        if (
            food not in syn_text
            and food not in food_text
            and food_human not in syn_text
            and food_human not in food_text
        ):
            _block(
                "food_condition",
                f"Food condition {food} inconsistent across Synopsis/Treatment",
            )

    evaluable = consistency.get("evaluable_n")
    if evaluable is not None:
        n_str = str(evaluable)
        syn = next((s for s in sections if s.get("section_code") == "SYNOPSIS"), None)
        ss = next((s for s in sections if s.get("section_code") == "9.2"), None)
        syn_text = " ".join(
            str(b.get("text") or "") for b in (syn or {}).get("content_blocks") or []
        )
        ss_text = " ".join(str(b.get("text") or "") for b in (ss or {}).get("content_blocks") or [])
        table_n = next((t for t in tables if t.get("table_key") == "SYNOPSIS_N"), None)
        table_blob = " ".join(
            str(c) for row in (table_n or {}).get("rows") or [] for c in row
        )
        if n_str not in syn_text and n_str not in ss_text and n_str not in table_blob:
            _block(
                "evaluable_n",
                "Evaluable N missing from Synopsis/Statistics consistency set",
                {"evaluable_n": evaluable},
            )

    # Sampling ↔ PK: if sampling points exist, sampling section must not be empty generated
    samp_points = consistency.get("sampling_points") or []
    if samp_points:
        samp_sec = next((s for s in sections if s.get("section_code") == "4.4.2"), None)
        if samp_sec and samp_sec.get("generation_status") == "SKIPPED":
            _block("sampling", "Sampling points exist but section 4.4.2 was skipped")

    analytes = consistency.get("analytes") or []
    if analytes:
        pk_sec = next((s for s in sections if s.get("section_code") == "4.1"), None)
        if pk_sec and pk_sec.get("generation_status") in {"SKIPPED", "FAILED"}:
            _block("analytes", "Analytes present but PK section not generated")

    return issues


def scan_forbidden_placeholders(text: str) -> list[str]:
    """Detect invented placeholder tokens (ХХ / XXX / примерно)."""
    low = (text or "").lower()
    found: list[str] = []
    for tok in ("хх", "xxx", "примерно", "approx.", " tbd", "???"):
        if tok in low:
            found.append(tok.strip())
    return found


def find_unresolved_markers(obj: Any) -> list[str]:
    import re

    markers: list[str] = []
    pattern = re.compile(r"\{\{[A-Z0-9_.]+\}\}")

    def walk(x: Any) -> None:
        if isinstance(x, str):
            markers.extend(pattern.findall(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)
    return sorted(set(markers))
