"""Full-document Protocol QA — Phase 12B.4.

Aggregates section QA + document-wide scans. Does not weaken FINAL gates.
Does not force FINAL PASS.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.domain.canonical_sampling import get_canonical_sampling_plan
from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.content_generation_qa import (
    ContentGenFinding,
    run_content_generation_qa,
    run_sections_5_8_qa,
    run_sections_9_15_qa,
)
from app.domain.display_value_registry import find_raw_enums_in_text
from app.domain.protocol_qa import run_protocol_qa
from app.domain.reference_registry import detect_broken_reference_text

_TODO_TBD_RE = re.compile(r"(?i)(?<![A-Z0-9_])(TODO|TBD)(?![A-Z0-9_])")
_FORBIDDEN_REF_PHRASES = (
    "Error: Reference source not found",
    "Error! Reference source not found",
)
_RANDOMIZED_N_RE = re.compile(
    # Number after рандомиз/randomized only - avoid evaluable N sitting just before the word
    r"(?i)(?:рандомиз\w*|randomized)\D{0,40}?\b(\d{1,4})\b"
)


@dataclass
class ProtocolDocumentQAReport:
    run_id: str
    study_id: str | None
    generated_at: str
    sections_total: int = 0
    blocks_total: int = 0
    blocks_resolved: int = 0
    blocks_unresolved: int = 0
    blocks_proposed: int = 0
    critical_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    legacy_count: int = 0
    placeholder_count: int = 0
    reference_errors: int = 0
    table_errors: int = 0
    cross_reference_errors: int = 0
    canonical_mismatches: int = 0
    gate: str = "READY"  # READY|BLOCKED (DRAFT always allowed)
    readiness: str = "READY_WITH_WARNINGS"
    findings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finding_to_dict(f: Any) -> dict[str, Any]:
    if isinstance(f, dict):
        return dict(f)
    if hasattr(f, "to_dict"):
        return f.to_dict()
    return {
        "code": getattr(f, "code", None),
        "severity": getattr(f, "severity", None),
        "blocking": getattr(f, "blocking", False),
        "message": getattr(f, "message", str(f)),
    }


def _mk(
    code: str,
    severity: str,
    blocking: bool,
    message: str,
    *,
    section: str | None = None,
    expected: str | None = None,
    actual: str | None = None,
    details: dict | None = None,
) -> dict[str, Any]:
    return ContentGenFinding(
        code,
        severity,
        blocking,
        message,
        section=section,
        expected=expected,
        actual=actual,
        details=details or {},
    ).to_dict()


def _sections_blob(sections: list[dict]) -> str:
    parts: list[str] = []
    for s in sections:
        for b in s.get("content_blocks") or []:
            if b.get("text"):
                parts.append(str(b["text"]))
            for it in b.get("items") or []:
                parts.append(str(it))
            if b.get("display_text"):
                parts.append(str(b["display_text"]))
    return "\n".join(parts)


def _dedupe_findings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        key = (r.get("code"), r.get("section"), r.get("message"), r.get("actual"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def run_full_document_qa(
    *,
    assembled: dict,
    ctx: dict,
    canonical: dict | None = None,
    mode: str = "DRAFT",
    legacy_hints: dict | None = None,
) -> ProtocolDocumentQAReport:
    """Run aggregated full-document QA. DRAFT always allowed; FINAL never forced PASS."""
    mode = (mode or "DRAFT").upper()
    sections = list(assembled.get("sections") or [])
    canonical = dict(canonical or {})
    ctx = ctx or {}
    legacy_hints = legacy_hints or {}

    study = ctx.get("study") or {}
    study_id = str(study.get("id") or ctx.get("project_id") or assembled.get("study_id") or "") or None

    report = ProtocolDocumentQAReport(
        run_id=str(uuid.uuid4()),
        study_id=study_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        sections_total=len(sections),
    )

    blocks_total = 0
    for s in sections:
        for b in s.get("content_blocks") or []:
            blocks_total += 1
            st = str(b.get("resolution_status") or "").upper()
            if st == "RESOLVED":
                report.blocks_resolved += 1
            elif st == "PROPOSED":
                report.blocks_proposed += 1
            elif st == "UNRESOLVED" or b.get("unresolved"):
                report.blocks_unresolved += 1
    report.blocks_total = blocks_total

    raw_findings: list[dict[str, Any]] = []

    # Existing section QA (import carefully — no cycles from those modules back here)
    for fn in (run_content_generation_qa, run_sections_5_8_qa, run_sections_9_15_qa):
        kwargs: dict[str, Any] = {
            "sections": sections,
            "canonical": canonical,
            "mode": mode,
            "legacy_hints": legacy_hints,
        }
        if fn is not run_content_generation_qa:
            kwargs["ctx"] = ctx
        for f in fn(**kwargs):
            raw_findings.append(_finding_to_dict(f))

    blob = _sections_blob(sections)

    # Identity displayed vs canonical via protocol_qa
    displayed = {
        "design": canonical.get("design"),
        "sampling_fingerprint": canonical.get("sampling_fingerprint"),
        "washout": canonical.get("washout"),
        "auc_metric": canonical.get("auc_metric"),
        "sponsor": canonical.get("sponsor"),
        "study_title": canonical.get("study_title"),
        "protocol_number": canonical.get("protocol_number"),
        "trade_name": canonical.get("trade_name") or canonical.get("product"),
        "dosage": canonical.get("dosage"),
        "dosage_form": canonical.get("dosage_form"),
        "randomized_n": canonical.get("randomized_n"),
    }
    # Prefer consistency snapshot identity when present
    snap = assembled.get("consistency_snapshot") or {}
    if isinstance(snap, dict):
        for k in list(displayed.keys()):
            if snap.get(k) is not None:
                displayed[k] = snap.get(k)

    for f in run_protocol_qa(
        canonical=canonical,
        displayed=displayed,
        document_text=blob or None,
        previous_identity=legacy_hints.get("previous_identity")
        if isinstance(legacy_hints.get("previous_identity"), dict)
        else None,
    ):
        d = _finding_to_dict(f)
        # Normalize severity field presence
        if "severity" not in d and d.get("risk_level"):
            d["severity"] = d["risk_level"]
        raw_findings.append(d)

    # Forbidden placeholder / broken reference phrases
    for phrase in _FORBIDDEN_REF_PHRASES:
        if phrase.lower() in blob.lower():
            raw_findings.append(
                _mk(
                    "QA.DOC.FORBIDDEN_PLACEHOLDER",
                    "CRITICAL",
                    True,
                    f"Forbidden placeholder phrase: {phrase}",
                    actual=phrase,
                )
            )
            report.placeholder_count += 1

    for hit in detect_broken_reference_text(blob):
        raw_findings.append(
            _mk(
                "QA.DOC.BROKEN_REFERENCE_TEXT",
                "CRITICAL",
                True,
                "Broken reference text detected",
                actual=str(hit),
            )
        )
        report.reference_errors += 1

    # Bare TODO/TBD as content
    if _TODO_TBD_RE.search(blob):
        raw_findings.append(
            _mk(
                "QA.DOC.TODO_TBD",
                "ERROR",
                True,
                "Bare TODO/TBD found in document content",
            )
        )
        report.placeholder_count += 1

    # Raw enums
    raw_enums = find_raw_enums_in_text(blob)
    if raw_enums:
        raw_findings.append(
            _mk(
                "CONTENT.RAW_ENUM_LEAK",
                "ERROR",
                True,
                f"Raw enum leak in full document: {sorted(set(raw_enums))}",
                actual=str(sorted(set(raw_enums))),
            )
        )

    # Legacy hints appearing in text
    for key, val in legacy_hints.items():
        if key in {"previous_identity", "canonical"}:
            continue
        if isinstance(val, dict):
            template_val = val.get("template")
            if template_val is not None and str(template_val) and str(template_val) in blob:
                raw_findings.append(
                    _mk(
                        "LEGACY_SUSPECTED",
                        "WARNING",
                        False,
                        f"Legacy template value suspected for {key}",
                        expected=str(val.get("canonical")) if val.get("canonical") is not None else None,
                        actual=str(template_val),
                    )
                )
                report.legacy_count += 1
        elif val is not None and str(val) and str(val) in blob:
            # Only flag when value looks study-specific (len > 2) to avoid digit noise
            if len(str(val)) > 2:
                raw_findings.append(
                    _mk(
                        "LEGACY_SUSPECTED",
                        "WARNING",
                        False,
                        f"Legacy hint value appears in document: {key}",
                        actual=str(val),
                    )
                )
                report.legacy_count += 1

    # N consistency vs canonical SubjectPlan
    counts = get_canonical_subject_counts(ctx)
    canon_n = counts.randomized_n
    if canon_n is None and canonical.get("randomized_n") is not None:
        try:
            canon_n = int(canonical["randomized_n"])
        except (TypeError, ValueError):
            canon_n = None
    if canon_n is not None:
        for m in _RANDOMIZED_N_RE.finditer(blob):
            num_s = m.group(1)
            if not num_s:
                continue
            n = int(num_s)
            if n == int(canon_n) or n in {0, 1, 2}:
                continue
            # CONTENT.LEGACY_VALUE style when legacy hint matches, else canonical mismatch
            legacy_n = legacy_hints.get("randomized_n")
            if isinstance(legacy_n, dict):
                legacy_n = legacy_n.get("template")
            if legacy_n is not None and str(legacy_n) == str(n):
                raw_findings.append(
                    _mk(
                        "CONTENT.LEGACY_VALUE",
                        "ERROR",
                        True,
                        f"Legacy N {n} vs canonical {canon_n}",
                        expected=str(canon_n),
                        actual=str(n),
                    )
                )
                report.legacy_count += 1
            raw_findings.append(
                _mk(
                    "CONTENT.CANONICAL_MISMATCH",
                    "ERROR",
                    True,
                    "Subject N mismatch vs canonical",
                    expected=str(canon_n),
                    actual=str(n),
                )
            )
            report.canonical_mismatches += 1

    # Sampling consistency when times are mentioned
    plan = get_canonical_sampling_plan(ctx)
    canon_times = []
    for p in plan.points or []:
        th = p.get("time_h")
        if th is not None:
            canon_times.append(float(th))
    if canon_times:
        # If document mentions sampling hours, flag times not in canonical set
        mentioned = set(float(x) for x in re.findall(r"(?i)(?:^|[^\d])(\d+(?:[.,]\d+)?)\s*ч", blob))
        # Also plain hour patterns near "отбор" / sampling
        if "отбор" in blob.lower() or "sampling" in blob.lower() or "проб" in blob.lower():
            foreign = [t for t in mentioned if t not in set(canon_times) and t not in {0.0}]
            # Only flag if document also cites at least one canonical time (active sampling text)
            if foreign and any(t in mentioned for t in canon_times):
                raw_findings.append(
                    _mk(
                        "QA.SAMPLING.INCONSISTENT_TIMES",
                        "ERROR",
                        True,
                        "Sampling times mentioned that are absent from canonical plan",
                        expected=str(canon_times),
                        actual=str(sorted(foreign)),
                    )
                )
                report.canonical_mismatches += 1

    # AUC0-x vs AUC0-72 must not be equated
    if "AUC0-x" in blob and "AUC0-72" in blob:
        if re.search(r"AUC0-x\s*=\s*AUC0-72|AUC0-last\s*=\s*AUC0-72|AUC0-72\s*=\s*AUC0-x", blob):
            raw_findings.append(
                _mk(
                    "QA.PK.AUC_METRIC_MISMATCH",
                    "ERROR",
                    True,
                    "AUC0-x incorrectly equated to AUC0-72",
                )
            )
            report.canonical_mismatches += 1

    # Table / cross-ref from assembled build_report
    br = assembled.get("build_report") or {}
    for issue in br.get("blocking_issues") or []:
        code = str(issue.get("code") or "")
        if code == "BROKEN_REFERENCE":
            raw_findings.append(
                _mk(
                    "QA.REF.BROKEN",
                    "CRITICAL",
                    True,
                    str(issue.get("message") or "Broken reference"),
                    actual=str(issue.get("field")),
                )
            )
            report.cross_reference_errors += 1
            report.reference_errors += 1

    ref_reg = br.get("reference_registry") or {}
    for r in ref_reg.get("references") or []:
        if r.get("resolved") is False:
            raw_findings.append(
                _mk(
                    "QA.CROSSREF.UNRESOLVED",
                    "CRITICAL",
                    True,
                    r.get("error") or "Unresolved cross-reference",
                    actual=str(r.get("target_id")),
                )
            )
            report.cross_reference_errors += 1

    # Unresolved table refs: TABLE blocks whose table_key missing from registry numbers
    table_reg = br.get("table_registry") or {}
    numbered = {
        str(t.get("table_key") or t.get("key"))
        for t in (table_reg.get("tables") or table_reg.get("entries") or [])
        if t.get("table_key") or t.get("key")
    }
    # Fallback: tables on assembled
    if not numbered:
        numbered = {str(t.get("table_key")) for t in (assembled.get("tables") or []) if t.get("table_key")}
    for s in sections:
        for b in s.get("content_blocks") or []:
            if b.get("type") == "TABLE":
                tk = b.get("table_key")
                if tk and numbered and str(tk) not in numbered and b.get("table_number") is None:
                    raw_findings.append(
                        _mk(
                            "QA.TABLE.UNRESOLVED",
                            "ERROR",
                            True,
                            f"Unresolved table reference: {tk}",
                            section=s.get("section_code"),
                            actual=str(tk),
                        )
                    )
                    report.table_errors += 1

    findings = _dedupe_findings(raw_findings)
    report.findings = findings

    for f in findings:
        sev = str(f.get("severity") or "").upper()
        code = str(f.get("code") or "")
        if sev == "CRITICAL" or (f.get("blocking") and sev == "CRITICAL"):
            report.critical_count += 1
        elif sev == "ERROR":
            report.error_count += 1
        elif sev == "WARNING":
            report.warning_count += 1
        if "LEGACY" in code.upper() or code == "LEGACY_SUSPECTED":
            if sev != "WARNING":  # already counted in scan; avoid double-count for non-scan
                pass
        if "PLACEHOLDER" in code.upper() or "TODO" in code.upper():
            pass
        if "CANONICAL_MISMATCH" in code.upper() or code.endswith("MISMATCH"):
            if "CANONICAL" in code.upper():
                pass

    blocking = [f for f in findings if f.get("blocking") or str(f.get("severity") or "").upper() == "CRITICAL"]

    # Gate: DRAFT always allowed for report; REVIEW/FINAL → BLOCKED if critical/blocking
    if mode == "DRAFT":
        report.gate = "READY"
    else:
        report.gate = "BLOCKED" if blocking else "READY"

    if blocking:
        report.readiness = "BLOCKED"
    elif report.warning_count or report.blocks_unresolved or report.blocks_proposed:
        report.readiness = "READY_WITH_WARNINGS"
    else:
        report.readiness = "READY"

    # Never force FINAL PASS
    if mode == "FINAL" and blocking:
        report.gate = "BLOCKED"

    return report
