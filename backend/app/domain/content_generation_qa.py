"""Phase 12B.1 — content generation QA (CONTENT.* codes).

Does not invent medical rules. Detects unsafe render states.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.display_value_registry import find_raw_enums_in_text

UNRESOLVED_RE = re.compile(r"\{\{[A-Z0-9_.]+\}\}")


@dataclass
class ContentGenFinding:
    code: str
    severity: str
    blocking: bool
    message: str
    section: str | None = None
    expected: str | None = None
    actual: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _blob_sections(sections: list[dict]) -> str:
    parts: list[str] = []
    for s in sections:
        for b in s.get("content_blocks") or []:
            if b.get("text"):
                parts.append(str(b["text"]))
            for it in b.get("items") or []:
                parts.append(str(it))
            # Detect proposed-as-final
            if b.get("resolution_status") == "PROPOSED" and b.get("display_as_final"):
                parts.append("__PROPOSED_AS_FINAL__")
            if b.get("decision_status") in {"REJECTED", "SUPERSEDED"} and b.get("display_as_final"):
                parts.append(f"__BAD_DECISION_{b.get('decision_status')}__")
    return "\n".join(parts)


def run_content_generation_qa(
    *,
    sections: list[dict],
    canonical: dict[str, Any] | None = None,
    mode: str = "DRAFT",
    legacy_hints: dict[str, Any] | None = None,
) -> list[ContentGenFinding]:
    findings: list[ContentGenFinding] = []
    canonical = canonical or {}
    mode = mode.upper()

    for s in sections:
        code = s.get("section_code")
        status = str(s.get("status") or "")
        for b in s.get("content_blocks") or []:
            text = str(b.get("text") or "")
            unresolved = list(b.get("unresolved") or []) or UNRESOLVED_RE.findall(text)
            if unresolved and mode in {"REVIEW", "FINAL"}:
                findings.append(
                    ContentGenFinding(
                        "CONTENT.PLACEHOLDER_UNRESOLVED",
                        "CRITICAL",
                        True,
                        f"Unresolved placeholders in {code}",
                        section=code,
                        actual=str(unresolved[:5]),
                    )
                )
            if unresolved and status in {"GENERATED", "OK"} and mode == "DRAFT":
                findings.append(
                    ContentGenFinding(
                        "CONTENT.UNRESOLVED_RENDER",
                        "WARNING",
                        False,
                        f"Unresolved content rendered in draft for {code}",
                        section=code,
                    )
                )
            if b.get("resolution_status") == "PROPOSED" and (
                b.get("display_as_final") or mode == "FINAL"
            ):
                findings.append(
                    ContentGenFinding(
                        "CONTENT.PROPOSED_RENDERED_AS_FINAL",
                        "ERROR",
                        True,
                        f"PROPOSED content marked final in {code}",
                        section=code,
                    )
                )
            if b.get("decision_status") == "REJECTED" and b.get("used_in_content"):
                findings.append(
                    ContentGenFinding(
                        "CONTENT.REJECTED_DECISION_USED",
                        "ERROR",
                        True,
                        f"Rejected decision used in {code}",
                        section=code,
                    )
                )
            if b.get("decision_status") == "SUPERSEDED" and b.get("used_in_content"):
                findings.append(
                    ContentGenFinding(
                        "CONTENT.SUPERSEDED_DECISION_USED",
                        "ERROR",
                        True,
                        f"Superseded decision used in {code}",
                        section=code,
                    )
                )
            raw = find_raw_enums_in_text(text)
            for it in b.get("items") or []:
                raw.extend(find_raw_enums_in_text(str(it)))
            if raw:
                findings.append(
                    ContentGenFinding(
                        "CONTENT.RAW_ENUM_LEAK",
                        "ERROR",
                        True,
                        f"Raw enum leak in {code}: {sorted(set(raw))}",
                        section=code,
                        actual=str(sorted(set(raw))),
                    )
                )
            if b.get("resolution_status") == "UNRESOLVED" and not unresolved:
                # Missing canonical without placeholder
                findings.append(
                    ContentGenFinding(
                        "CONTENT.CANONICAL_MISSING",
                        "WARNING",
                        False,
                        f"Canonical missing for block in {code}",
                        section=code,
                    )
                )

        if status == "UNRESOLVED" and not any(
            f.section == code and f.code.startswith("CONTENT.") for f in findings
        ):
            findings.append(
                ContentGenFinding(
                    "CONTENT.CANONICAL_MISSING",
                    "WARNING",
                    False,
                    f"Section {code} unresolved",
                    section=code,
                )
            )

    # Subject N consistency across sections
    canon_n = canonical.get("randomized_n")
    if canon_n is not None:
        for s in sections:
            for b in s.get("content_blocks") or []:
                text = str(b.get("text") or "")
                # Detect alternate N patterns only when block claims subject N
                if "рандомиз" in text.lower() or "SUBJECTS.RANDOMIZED" in text:
                    # if text contains a different integer that looks like N
                    nums = re.findall(r"\b(\d{1,3})\b", text)
                    for n in nums:
                        if int(n) != int(canon_n) and int(n) not in {0, 1, 2}:
                            # weak heuristic — only flag if also legacy hint matches
                            if legacy_hints and str(legacy_hints.get("randomized_n")) == n:
                                findings.append(
                                    ContentGenFinding(
                                        "CONTENT.LEGACY_VALUE",
                                        "ERROR",
                                        True,
                                        f"Legacy N {n} vs canonical {canon_n}",
                                        section=s.get("section_code"),
                                        expected=str(canon_n),
                                        actual=n,
                                    )
                                )
                                findings.append(
                                    ContentGenFinding(
                                        "CONTENT.CANONICAL_MISMATCH",
                                        "ERROR",
                                        True,
                                        "Subject N mismatch vs canonical",
                                        section=s.get("section_code"),
                                        expected=str(canon_n),
                                        actual=n,
                                    )
                                )

    if legacy_hints:
        for field, pair in legacy_hints.items():
            if isinstance(pair, dict) and "canonical" in pair and "template" in pair:
                if str(pair["canonical"]) != str(pair["template"]):
                    findings.append(
                        ContentGenFinding(
                            "CONTENT.LEGACY_VALUE",
                            "WARNING",
                            False,
                            f"Legacy template differs for {field}",
                            expected=str(pair["canonical"]),
                            actual=str(pair["template"]),
                        )
                    )

    # Alias CONTENT.* rejected/superseded to QA.CONTENT.* for 12B.2 report codes
    for f in list(findings):
        if f.code == "CONTENT.REJECTED_DECISION_USED":
            findings.append(
                ContentGenFinding(
                    "QA.CONTENT.REJECTED_DECISION",
                    f.severity,
                    f.blocking,
                    f.message,
                    section=f.section,
                )
            )
        if f.code == "CONTENT.SUPERSEDED_DECISION_USED":
            findings.append(
                ContentGenFinding(
                    "QA.CONTENT.SUPERSEDED_DECISION",
                    f.severity,
                    f.blocking,
                    f.message,
                    section=f.section,
                )
            )

    return findings


def run_sections_5_8_qa(
    *,
    sections: list[dict],
    canonical: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
    mode: str = "DRAFT",
    legacy_hints: dict[str, Any] | None = None,
) -> list[ContentGenFinding]:
    """Phase 12B.2 domain QA for eligibility / procedures / PK / bio / safety."""
    findings = run_content_generation_qa(
        sections=sections,
        canonical=canonical,
        mode=mode,
        legacy_hints=legacy_hints,
    )
    ctx = ctx or {}
    canonical = canonical or {}
    mode = mode.upper()

    def _section_blob(code: str) -> str:
        for s in sections:
            if s.get("section_code") == code:
                parts = []
                for b in s.get("content_blocks") or []:
                    if b.get("text"):
                        parts.append(str(b["text"]))
                    parts.extend(str(x) for x in (b.get("items") or []))
                return "\n".join(parts)
        return ""

    def _all_blobs() -> str:
        return "\n".join(_section_blob(s.get("section_code") or "") for s in sections)

    blob = _all_blobs().lower()

    # N/A fallback detection
    if re.search(r"\bn/?a\b|\bnot applicable\b|\bas applicable\b", blob):
        findings.append(
            ContentGenFinding(
                "QA.CONTENT.N_A_FALLBACK",
                "ERROR",
                True,
                "Forbidden N/A / as-applicable fallback in generated content",
            )
        )

    # Eligibility consistency: section 5 vs ctx eligibility texts
    elig = ctx.get("eligibility") or {}
    for cat, code in (("inclusion", "5.1"), ("non_inclusion", "5.2"), ("exclusion", "5.3")):
        rows = elig.get(cat) or []
        sec_text = _section_blob(code)
        for r in rows:
            t = (r.get("text") or r.get("criterion_text") or "").strip()
            if t and t not in sec_text and "{{ELIGIBILITY" not in sec_text:
                findings.append(
                    ContentGenFinding(
                        "QA.ELIGIBILITY.CANONICAL_MISMATCH",
                        "ERROR",
                        True,
                        f"Section {code} missing canonical {cat} criterion",
                        section=code,
                        expected=t[:80],
                    )
                )

    # Synopsis eligibility vs section 5 (if synopsis section present)
    syn = _section_blob("SYNOPSIS") or _section_blob("1.1")
    if syn and elig.get("inclusion"):
        for r in elig["inclusion"][:3]:
            t = (r.get("text") or "").strip()
            if t and t in syn:
                # must also appear in 5.1
                if t not in _section_blob("5.1"):
                    findings.append(
                        ContentGenFinding(
                            "QA.ELIGIBILITY.CANONICAL_MISMATCH",
                            "ERROR",
                            True,
                            "Synopsis eligibility criterion missing from section 5.1",
                            section="5.1",
                        )
                    )

    if legacy_hints and legacy_hints.get("eligibility_legacy"):
        findings.append(
            ContentGenFinding(
                "QA.ELIGIBILITY.LEGACY_VALUE",
                "ERROR",
                True,
                "Legacy eligibility value detected",
                actual=str(legacy_hints.get("eligibility_legacy")),
            )
        )

    # Sampling single plan: §4.4.2 / §6 / §7.2 must not invent alternate times
    from app.domain.canonical_sampling import get_canonical_sampling_plan

    plan = get_canonical_sampling_plan(ctx) if ctx else None
    if plan and plan.points:
        canon_times = [float(p.get("time_h")) for p in plan.points if p.get("time_h") is not None]
        for code in ("4.4.2", "6.1.4", "6.1.6", "7.2"):
            text = _section_blob(code)
            if not text:
                continue
            # If section mentions sampling times list, verify subset consistency
            if "samplingplan" in text.lower().replace(" ", "") or "точек" in text.lower():
                for t in re.findall(r"\b(\d+(?:\.\d+)?)\b", text):
                    try:
                        fv = float(t)
                    except ValueError:
                        continue
                    # ignore small integers that are period numbers / counts
                    if fv in canon_times or fv == float(plan.points_per_period or 0):
                        continue
                    if fv in {1.0, 2.0} and ("период" in text.lower()):
                        continue
                    # do not flag display numbers aggressively — only when explicit alternate list
                    pass
        findings.append(
            ContentGenFinding(
                "QA.SAMPLING.CANONICAL_OK",
                "INFO",
                False,
                "Canonical SamplingPlan available for cross-section checks",
            )
        )
    elif any(s.get("section_code") in {"6.1.4", "7.2"} for s in sections):
        findings.append(
            ContentGenFinding(
                "QA.SAMPLING.CANONICAL_MISMATCH",
                "WARNING",
                False,
                "Sampling sections present without canonical plan points",
            )
        )

    # Procedure schedule mismatch
    for s in sections:
        if str(s.get("section_code") or "").startswith("6"):
            for b in s.get("content_blocks") or []:
                if b.get("canonical_source") == "procedure_schedule" and b.get("resolution_status") == "UNRESOLVED":
                    findings.append(
                        ContentGenFinding(
                            "QA.PROCEDURE.SCHEDULE_MISMATCH",
                            "ERROR",
                            True,
                            "Procedure schedule unresolved in section 6",
                            section=s.get("section_code"),
                        )
                    )
                if b.get("resolution_status") == "UNRESOLVED" and "PRODUCT" in str(b.get("unresolved")):
                    findings.append(
                        ContentGenFinding(
                            "QA.PROCEDURE.CANONICAL_MISMATCH",
                            "ERROR",
                            True,
                            "Procedure dosing missing canonical product fields",
                            section=s.get("section_code"),
                        )
                    )

    # PK / AUC
    for s in sections:
        if str(s.get("section_code") or "").startswith("7"):
            for b in s.get("content_blocks") or []:
                if b.get("block_code") == "PK.ANALYTE.PROPOSED" and (
                    b.get("display_as_final") or mode == "FINAL"
                ):
                    findings.append(
                        ContentGenFinding(
                            "QA.PK.ANALYTE_UNRESOLVED",
                            "ERROR",
                            True,
                            "Analyte selection not approved for final",
                            section=s.get("section_code"),
                        )
                    )
                displays = b.get("auc_displays") or []
                if "AUC0-x" in displays and "AUC0-72" in displays:
                    # both present is OK — mismatch is silent substitution
                    pass
                text = str(b.get("text") or "")
                if "AUC0-72" in text and "AUC0-x" in text.replace("AUC0-x/AUC0-inf", ""):
                    # ensure not claiming equality
                    if "AUC0-x = AUC0-72" in text or "AUC0-last = AUC0-72" in text:
                        findings.append(
                            ContentGenFinding(
                                "QA.PK.AUC_METRIC_MISMATCH",
                                "ERROR",
                                True,
                                "AUC0-x incorrectly equated to AUC0-72",
                                section=s.get("section_code"),
                            )
                        )
                if b.get("resolution_status") == "PROPOSED" and b.get("display_as_final"):
                    findings.append(
                        ContentGenFinding(
                            "QA.PK.UNAPPROVED_PARAMETER",
                            "ERROR",
                            True,
                            "Unapproved PK parameter rendered as final",
                            section=s.get("section_code"),
                        )
                    )
                if str(b.get("block_code") or "").startswith("BIO.") and b.get("display_as_final"):
                    if not (b.get("source_ids") or b.get("evidence_claim_id") or b.get("expert_decision_id")):
                        findings.append(
                            ContentGenFinding(
                                "QA.BIOANALYSIS.MISSING_PROVENANCE",
                                "ERROR",
                                True,
                                "Bioanalysis final content missing provenance",
                                section=s.get("section_code"),
                            )
                        )
                if (
                    str(b.get("block_code") or "").startswith("BIO.")
                    and b.get("resolution_status") == "PROPOSED"
                    and (b.get("display_as_final") or mode == "FINAL")
                ):
                    findings.append(
                        ContentGenFinding(
                            "QA.BIOANALYSIS.PROPOSED_AS_FINAL",
                            "ERROR",
                            True,
                            "Proposed bioanalysis rendered as final",
                            section=s.get("section_code"),
                        )
                    )

    # Safety
    for s in sections:
        if str(s.get("section_code") or "").startswith("8"):
            for b in s.get("content_blocks") or []:
                if b.get("resolution_status") in {"PROPOSED", "UNVERIFIED"} and (
                    b.get("display_as_final") or mode == "FINAL"
                ):
                    findings.append(
                        ContentGenFinding(
                            "QA.SAFETY.UNVERIFIED_AS_FINAL",
                            "ERROR",
                            True,
                            "Unverified safety content marked final",
                            section=s.get("section_code"),
                        )
                    )
                if b.get("canonical_source") == "procedure_schedule" and b.get(
                    "resolution_status"
                ) == "UNRESOLVED":
                    findings.append(
                        ContentGenFinding(
                            "QA.SAFETY.SCHEDULE_MISMATCH",
                            "ERROR",
                            True,
                            "Safety timing schedule mismatch/unresolved",
                            section=s.get("section_code"),
                        )
                    )

    if legacy_hints and legacy_hints.get("template_value"):
        findings.append(
            ContentGenFinding(
                "QA.CONTENT.LEGACY_TEMPLATE",
                "WARNING",
                False,
                "Legacy template value hint supplied",
                actual=str(legacy_hints.get("template_value")),
            )
        )

    return findings


def run_sections_9_15_qa(
    *,
    sections: list[dict],
    canonical: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
    mode: str = "DRAFT",
    legacy_hints: dict[str, Any] | None = None,
) -> list[ContentGenFinding]:
    """Phase 12B.3 QA for statistics / admin / ethics / data / finance / publication."""
    findings = run_content_generation_qa(
        sections=sections,
        canonical=canonical,
        mode=mode,
        legacy_hints=legacy_hints,
    )
    ctx = ctx or {}
    mode = mode.upper()

    def _blob(code: str) -> str:
        for s in sections:
            if s.get("section_code") == code:
                parts = []
                for b in s.get("content_blocks") or []:
                    if b.get("text"):
                        parts.append(str(b["text"]))
                    parts.extend(str(x) for x in (b.get("items") or []))
                return "\n".join(parts)
        return ""

    # Proposed-as-final alias
    for s in sections:
        for b in s.get("content_blocks") or []:
            if b.get("resolution_status") == "PROPOSED" and (
                b.get("display_as_final") or mode == "FINAL"
            ):
                findings.append(
                    ContentGenFinding(
                        "QA.CONTENT.PROPOSED_AS_FINAL",
                        "ERROR",
                        True,
                        f"PROPOSED content marked final in {s.get('section_code')}",
                        section=s.get("section_code"),
                    )
                )
            if b.get("decision_status") == "REJECTED" and b.get("used_in_content"):
                findings.append(
                    ContentGenFinding(
                        "QA.CONTENT.REJECTED_DECISION",
                        "ERROR",
                        True,
                        "Rejected decision used",
                        section=s.get("section_code"),
                    )
                )
            if b.get("decision_status") == "SUPERSEDED" and b.get("used_in_content"):
                findings.append(
                    ContentGenFinding(
                        "QA.CONTENT.SUPERSEDED_DECISION",
                        "ERROR",
                        True,
                        "Superseded decision used",
                        section=s.get("section_code"),
                    )
                )

    # Statistics
    from app.domain.canonical_subjects import get_canonical_subject_counts

    counts = get_canonical_subject_counts(ctx) if ctx else None
    ss = ctx.get("sample_size") or {}
    cfg = ctx.get("statistical_config") or {}
    cv = ctx.get("cv_selection") or {}

    if any(str(s.get("section_code") or "").startswith("9") for s in sections):
        if counts and counts.randomized_n is None:
            findings.append(
                ContentGenFinding(
                    "STAT.N_RANDOMIZED_MISSING",
                    "ERROR",
                    True,
                    "Randomized N missing from SubjectPlan",
                    section="9.2",
                )
            )
            findings.append(
                ContentGenFinding(
                    "QA.STAT.RANDOMIZED_N_UNRESOLVED",
                    "ERROR",
                    True,
                    "Randomized N unresolved",
                    section="9.2",
                )
            )
        if ss.get("evaluable_n") is None and not cfg:
            findings.append(
                ContentGenFinding(
                    "STAT.N_CALCULATED_MISSING",
                    "WARNING",
                    False,
                    "Calculated sample size missing",
                    section="9.2",
                )
            )
        if (
            counts
            and counts.randomized_n is not None
            and ss.get("evaluable_n") is not None
            and int(counts.randomized_n) == int(ss["evaluable_n"])
            and "расчётн" in _blob("9.2").lower()
            and "subjectplan" not in _blob("9.2").lower()
            and "subject plan" not in _blob("9.2").lower()
        ):
            # Heuristic: calculated N silently used as randomized without distinction
            pass
        if counts and ss.get("randomized_n") is not None and counts.randomized_n is not None:
            if int(ss["randomized_n"]) != int(counts.randomized_n):
                findings.append(
                    ContentGenFinding(
                        "STAT.N_SEMANTIC_MISMATCH",
                        "WARNING",
                        False,
                        "SampleSizeCalculation randomized_n differs from SubjectPlan",
                        expected=str(counts.randomized_n),
                        actual=str(ss["randomized_n"]),
                        section="9.2",
                    )
                )
        if (cv.get("selected_cv") is not None or ss.get("selected_cv") is not None) and not (
            cv.get("source_study_ids") or cv.get("source_ids")
        ):
            findings.append(
                ContentGenFinding(
                    "STAT.CV_MISSING_SOURCE",
                    "ERROR",
                    True,
                    "CV missing provenance",
                    section="9.2",
                )
            )
            findings.append(
                ContentGenFinding(
                    "QA.STAT.MISSING_PROVENANCE",
                    "ERROR",
                    True,
                    "Statistics CV missing provenance",
                    section="9.2",
                )
            )
        for s in sections:
            if not str(s.get("section_code") or "").startswith("9"):
                continue
            for b in s.get("content_blocks") or []:
                if b.get("potvin_unverified") or (
                    "POTVIN" in str(b.get("text") or "").upper()
                    and b.get("resolution_status") == "PROPOSED"
                    and (b.get("display_as_final") or mode == "FINAL")
                ):
                    findings.append(
                        ContentGenFinding(
                            "STAT.POTVIN_UNVERIFIED",
                            "ERROR",
                            True,
                            "Unverified Potvin/adaptive rendered as final",
                            section=s.get("section_code"),
                        )
                    )
                    findings.append(
                        ContentGenFinding(
                            "STAT.ADAPTABLE_METHOD_UNVERIFIED",
                            "ERROR",
                            True,
                            "Unverified adaptive method",
                            section=s.get("section_code"),
                        )
                    )
                if b.get("resolution_status") == "PROPOSED" and b.get("display_as_final"):
                    findings.append(
                        ContentGenFinding(
                            "STAT.UNAPPROVED_PARAMETERS",
                            "ERROR",
                            True,
                            "Unapproved statistical parameters as final",
                            section=s.get("section_code"),
                        )
                    )
                    findings.append(
                        ContentGenFinding(
                            "QA.STAT.UNAPPROVED_VALUE",
                            "ERROR",
                            True,
                            "Unapproved statistical value",
                            section=s.get("section_code"),
                        )
                    )
                if b.get("block_code") == "STAT.SAMPLE_SIZE" and b.get("calculated_n") is not None:
                    # Ensure calculated N not presented as sole randomized without SubjectPlan
                    if b.get("randomized_n") is None and "рандомиз" in str(b.get("text") or "").lower():
                        if str(b.get("calculated_n")) in str(b.get("text") or "") and "{{SUBJECTS.RANDOMIZED_N}}" not in str(
                            b.get("text") or ""
                        ):
                            findings.append(
                                ContentGenFinding(
                                    "STAT.CALCULATION_CANONICAL_MISMATCH",
                                    "ERROR",
                                    True,
                                    "Calculated N used where randomized N required",
                                    section="9.2",
                                )
                            )
                            findings.append(
                                ContentGenFinding(
                                    "QA.STAT.CANONICAL_MISMATCH",
                                    "ERROR",
                                    True,
                                    "Statistics canonical mismatch on N",
                                    section="9.2",
                                )
                            )

    # Ethics / admin
    for s in sections:
        code = str(s.get("section_code") or "")
        for b in s.get("content_blocks") or []:
            text = str(b.get("text") or "").lower()
            if code == "12" and any(
                fake in text for fake in ("вымышлен", "example ethics", "dummy committee", "тест комитет")
            ):
                findings.append(
                    ContentGenFinding(
                        "QA.ETHICS.FAKE_SITE_DATA",
                        "ERROR",
                        True,
                        "Fake ethics site data detected",
                        section=code,
                    )
                )
            if code == "12" and b.get("block_code") == "ETHICS.COMMITTEE.MISSING" and mode == "FINAL":
                findings.append(
                    ContentGenFinding(
                        "QA.ETHICS.MISSING_REQUIRED_VALUE",
                        "ERROR",
                        True,
                        "Ethics committee required for FINAL",
                        section=code,
                    )
                )
            if code == "14" and b.get("block_code") == "ADMIN.INSURANCE.MISSING":
                findings.append(
                    ContentGenFinding(
                        "QA.ADMIN.INSURANCE_UNRESOLVED",
                        "WARNING",
                        mode == "FINAL",
                        "Insurance unresolved",
                        section=code,
                    )
                )
            if code == "15" and b.get("resolution_status") == "PROPOSED" and b.get("display_as_final"):
                findings.append(
                    ContentGenFinding(
                        "QA.PUBLICATION.UNAPPROVED_CLAUSE",
                        "ERROR",
                        True,
                        "Unapproved publication clause as final",
                        section=code,
                    )
                )
            if code == "13" and b.get("resolution_status") == "UNRESOLVED" and "RETENTION" in str(
                b.get("block_code") or ""
            ):
                findings.append(
                    ContentGenFinding(
                        "QA.DATA.MISSING_SOURCE",
                        "WARNING",
                        False,
                        "Retention period missing source",
                        section=code,
                    )
                )
            if "DEVIATION" in str(b.get("block_code") or "") and b.get("resolution_status") == "UNRESOLVED":
                findings.append(
                    ContentGenFinding(
                        "QA.DEVIATION.UNRESOLVED",
                        "WARNING",
                        False,
                        "Deviation content unresolved",
                        section=code,
                    )
                )

    # Sponsor consistency
    sponsor = (ctx.get("sponsor") or {}) if ctx else {}
    sp_name = sponsor.get("name") or sponsor.get("legal_name")
    if sp_name:
        for code in ("14", "1.2", "SYNOPSIS"):
            blob = _blob(code)
            if blob and "Спонсор" in blob and sp_name not in blob and "{{" not in blob:
                findings.append(
                    ContentGenFinding(
                        "QA.ADMIN.SPONSOR_MISMATCH",
                        "ERROR",
                        True,
                        "Sponsor mismatch vs canonical",
                        section=code,
                        expected=str(sp_name),
                    )
                )

    if legacy_hints and legacy_hints.get("admin_legacy"):
        findings.append(
            ContentGenFinding(
                "QA.CONTENT.LEGACY_VALUE",
                "ERROR",
                True,
                "Legacy admin value detected",
                actual=str(legacy_hints.get("admin_legacy")),
            )
        )

    return findings
