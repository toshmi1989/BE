"""Previous protocol diff + Protocol QA — Phase 12A.1."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProtocolDiffItem:
    section: str
    table: str | None
    paragraph_or_field: str
    previous_value: str | None
    current_value: str | None
    diff_type: str
    risk_level: str
    reason: str
    review_status: str = "OPEN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LEGACY_FIELD_KEYS = (
    "sponsor",
    "sponsor_name",
    "product",
    "trade_name",
    "dose",
    "dosage",
    "dosage_form",
    "protocol_number",
    "randomized_n",
    "evaluable_n",
    "tmax",
    "half_life",
    "investigator",
    "organization",
)


def compare_identity_maps(
    *,
    previous: dict[str, Any],
    current: dict[str, Any],
) -> list[ProtocolDiffItem]:
    """Structural identity/legacy comparison — never auto-deletes legacy values."""
    items: list[ProtocolDiffItem] = []
    keys = sorted(set(previous) | set(current) | set(LEGACY_FIELD_KEYS))
    for key in keys:
        if key not in previous and key not in current:
            continue
        pv = previous.get(key)
        cv = current.get(key)
        if pv is None and cv is None:
            continue
        if pv is None and cv is not None:
            items.append(
                ProtocolDiffItem(
                    section="IDENTITY",
                    table=None,
                    paragraph_or_field=key,
                    previous_value=None,
                    current_value=str(cv),
                    diff_type="VALUE_ADDED",
                    risk_level="LOW",
                    reason="Field added in current study",
                )
            )
        elif pv is not None and cv is None:
            items.append(
                ProtocolDiffItem(
                    section="IDENTITY",
                    table=None,
                    paragraph_or_field=key,
                    previous_value=str(pv),
                    current_value=None,
                    diff_type="VALUE_REMOVED",
                    risk_level="MEDIUM",
                    reason="Field removed vs previous protocol",
                )
            )
        elif str(pv) == str(cv):
            items.append(
                ProtocolDiffItem(
                    section="IDENTITY",
                    table=None,
                    paragraph_or_field=key,
                    previous_value=str(pv),
                    current_value=str(cv),
                    diff_type="VALUE_UNCHANGED",
                    risk_level="LOW",
                    reason="Unchanged",
                )
            )
        else:
            risk = "HIGH" if key in {"sponsor", "sponsor_name", "trade_name", "dosage", "protocol_number"} else "MEDIUM"
            items.append(
                ProtocolDiffItem(
                    section="IDENTITY",
                    table=None,
                    paragraph_or_field=key,
                    previous_value=str(pv),
                    current_value=str(cv),
                    diff_type="VALUE_CHANGED",
                    risk_level=risk,
                    reason="Value differs from previous protocol — review required",
                )
            )
            items.append(
                ProtocolDiffItem(
                    section="LEGACY",
                    table=None,
                    paragraph_or_field=key,
                    previous_value=str(pv),
                    current_value=str(cv),
                    diff_type="LEGACY_SUSPECTED",
                    risk_level="CRITICAL" if key in {"sponsor", "sponsor_name"} else "HIGH",
                    reason="Legacy value suspected — WARNING/REVIEW REQUIRED, not auto-deleted",
                )
            )
    return items


@dataclass
class QAFinding:
    code: str
    severity: str
    category: str
    message: str
    location: str | None = None
    expected: str | None = None
    actual: str | None = None
    related_canonical_field: str | None = None
    related_source: str | None = None
    blocking: bool = False
    remediation: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


UNRESOLVED_RE = re.compile(r"\{\{[A-Z0-9_.]+\}\}")


def run_protocol_qa(
    *,
    canonical: dict[str, Any],
    displayed: dict[str, Any] | None = None,
    document_text: str | None = None,
    previous_identity: dict[str, Any] | None = None,
) -> list[QAFinding]:
    """Foundation QA checks — no invented critical medical error list."""
    displayed = displayed or {}
    findings: list[QAFinding] = []

    def mismatch(code: str, category: str, field: str, expected: Any, actual: Any) -> None:
        if expected is None or actual is None:
            return
        if str(expected) != str(actual):
            findings.append(
                QAFinding(
                    code=code,
                    severity="ERROR",
                    category=category,
                    message=f"Canonical {field} mismatch",
                    expected=str(expected),
                    actual=str(actual),
                    related_canonical_field=field,
                    blocking=True,
                    remediation="Align displayed value with Canonical Study Snapshot",
                )
            )

    mismatch("QA-DESIGN-01", "DESIGN", "design", canonical.get("design"), displayed.get("design"))
    mismatch(
        "QA-SAMPLING-01",
        "SAMPLING",
        "sampling_fingerprint",
        canonical.get("sampling_fingerprint"),
        displayed.get("sampling_fingerprint"),
    )
    mismatch(
        "QA-WASHOUT-01",
        "WASHOUT",
        "washout",
        canonical.get("washout"),
        displayed.get("washout"),
    )
    mismatch(
        "QA-PK-01",
        "PK",
        "auc_metric",
        canonical.get("auc_metric"),
        displayed.get("auc_metric"),
    )

    if document_text:
        unresolved = sorted(set(UNRESOLVED_RE.findall(document_text)))
        if unresolved:
            findings.append(
                QAFinding(
                    code="QA-DOC-01",
                    severity="CRITICAL",
                    category="DOCUMENT",
                    message=f"Unresolved placeholders: {len(unresolved)}",
                    actual=str(unresolved[:10]),
                    blocking=True,
                    remediation="Resolve placeholders before REVIEW/FINAL",
                    details={"count": len(unresolved)},
                )
            )
        from app.domain.display_value_registry import find_raw_enums_in_text
        from app.domain.reference_registry import detect_broken_reference_text

        raw = find_raw_enums_in_text(document_text)
        if raw:
            findings.append(
                QAFinding(
                    code="QA-DOC-03",
                    severity="ERROR",
                    category="DOCUMENT",
                    message="Raw enum leakage in document text",
                    actual=str(raw),
                    blocking=True,
                    remediation="Use DisplayValueRegistry",
                )
            )
        broken = detect_broken_reference_text(document_text)
        if broken:
            findings.append(
                QAFinding(
                    code="QA-DOC-02",
                    severity="CRITICAL",
                    category="DOCUMENT",
                    message="Broken references",
                    actual=str(broken),
                    blocking=True,
                )
            )

    if previous_identity:
        for item in compare_identity_maps(previous=previous_identity, current=displayed or canonical):
            if item.diff_type == "LEGACY_SUSPECTED":
                findings.append(
                    QAFinding(
                        code="QA-LEGACY-01" if "sponsor" in item.paragraph_or_field else "QA-LEGACY-02",
                        severity="WARNING",
                        category="LEGACY",
                        message=item.reason,
                        expected=item.previous_value,
                        actual=item.current_value,
                        location=item.paragraph_or_field,
                        blocking=False,
                        remediation="Review legacy carry-over; do not silently delete",
                    )
                )

    return findings
