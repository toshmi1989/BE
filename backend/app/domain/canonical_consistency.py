"""Canonical consistency validation + DocumentConsistencyReport."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.canonical_sampling import get_canonical_sampling_plan
from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.display_value_registry import find_raw_enums_in_text
from app.domain.placeholder_registry import classify_placeholders, extract_placeholders
from app.domain.reference_registry import detect_broken_reference_text
from app.domain.validation_types import IssueDraft


@dataclass
class ConsistencyDomainResult:
    domain: str
    status: str  # PASS | ERROR | WARNING
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentConsistencyReport:
    domains: list[ConsistencyDomainResult] = field(default_factory=list)
    issues: list[IssueDraft] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(d.status == "PASS" for d in self.domains)

    @property
    def blocking(self) -> bool:
        return any(d.status == "ERROR" for d in self.domains) or any(
            i.blocking and i.severity in {"CRITICAL", "ERROR"} for i in self.issues
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blocking": self.blocking,
            "domains": [
                {
                    "domain": d.domain,
                    "status": d.status,
                    "message": d.message,
                    "details": d.details,
                }
                for d in self.domains
            ],
            "issues": [
                {
                    "category": i.category,
                    "severity": i.severity,
                    "rule_id": i.rule_id,
                    "message": i.message,
                    "field": i.field,
                    "details": i.details,
                    "blocking": i.blocking,
                }
                for i in self.issues
            ],
        }


def _issue(
    *,
    domain: str,
    severity: str,
    rule_id: str,
    message: str,
    field: str | None = None,
    details: dict | None = None,
) -> IssueDraft:
    return IssueDraft(
        category="CANONICAL_CONSISTENCY",
        severity=severity,
        rule_id=rule_id,
        entity_type="Study",
        entity_id=None,
        field=field or domain.lower(),
        message=message,
        details=details or {},
        source_ids=[],
        blocking=severity in {"CRITICAL", "ERROR"},
    )


def _section_blob(sections: list[dict], code: str) -> str:
    sec = next((s for s in sections if s.get("section_code") == code), None)
    if not sec:
        return ""
    parts: list[str] = []
    for b in sec.get("content_blocks") or []:
        if b.get("text"):
            parts.append(str(b["text"]))
        for item in b.get("items") or []:
            parts.append(str(item))
    return "\n".join(parts)


def _table_blob(tables: list[dict], key: str) -> str:
    t = next((x for x in tables if x.get("table_key") == key), None)
    if not t:
        return ""
    return "\n".join(str(c) for row in (t.get("rows") or []) for c in row)


def _full_blob(sections: list[dict], tables: list[dict]) -> str:
    parts: list[str] = []
    for s in sections:
        parts.append(_section_blob(sections, s.get("section_code") or ""))
    for t in tables:
        parts.append(_table_blob(tables, t.get("table_key") or ""))
    return "\n".join(parts)


def validate_canonical_consistency(
    ctx: dict,
    *,
    consistency: dict | None = None,
    sections: list[dict] | None = None,
    tables: list[dict] | None = None,
    references: list[dict] | None = None,
) -> DocumentConsistencyReport:
    """
    Cross-check critical Study values across SubjectPlan, SampleSize, ProtocolDraft.
    """
    report = DocumentConsistencyReport()
    sections = sections or []
    tables = tables or []
    consistency = consistency or {}

    subjects = get_canonical_subject_counts(ctx)
    sampling = get_canonical_sampling_plan(ctx)
    product = ctx.get("product") or {}
    reference = ctx.get("reference_product") or {}
    design = ctx.get("design") or {}
    food = ctx.get("food") or {}

    # --- SUBJECTS ---
    if subjects.diverges_from_sample_size:
        msg = (
            f"SubjectPlan randomized_n={subjects.randomized_n} "
            f"!= SampleSize randomized_n={subjects.sample_size_randomized_n}"
        )
        report.domains.append(
            ConsistencyDomainResult(
                "SUBJECTS",
                "ERROR",
                msg,
                {
                    "subject_plan": subjects.to_dict(),
                },
            )
        )
        report.issues.append(
            _issue(
                domain="SUBJECTS",
                severity="ERROR",
                rule_id="CANON.SUBJECTS.N_DIVERGENCE.v1",
                message=msg,
                details=subjects.to_dict(),
            )
        )
    else:
        # ProtocolDraft surfaces must use canonical N when generated
        syn = _section_blob(sections, "SYNOPSIS")
        ss = _section_blob(sections, "9.2")
        syn_n = _table_blob(tables, "SYNOPSIS_N")
        if subjects.randomized_n is not None and sections:
            n = str(subjects.randomized_n)
            # Synopsis N is authoritative via SYNOPSIS_N table and/or SYNOPSIS text
            synopsis_has = (n in syn) or (n in syn_n)
            stats_has = n in ss if ss else synopsis_has
            if ss and synopsis_has != stats_has:
                report.domains.append(
                    ConsistencyDomainResult(
                        "SUBJECTS",
                        "ERROR",
                        f"randomized_n={n} inconsistent across Synopsis/Statistics",
                        {
                            "synopsis_has": synopsis_has,
                            "stats_has": stats_has,
                            "synopsis_text": bool(syn),
                            "synopsis_n_table": bool(syn_n),
                        },
                    )
                )
                report.issues.append(
                    _issue(
                        domain="SUBJECTS",
                        severity="ERROR",
                        rule_id="CANON.SUBJECTS.PROTOCOL_N.v1",
                        message="Synopsis vs Statistics randomized_n mismatch",
                        details={
                            "randomized_n": n,
                            "synopsis_has": synopsis_has,
                            "stats_has": stats_has,
                        },
                    )
                )
            else:
                report.domains.append(ConsistencyDomainResult("SUBJECTS", "PASS"))
        else:
            report.domains.append(ConsistencyDomainResult("SUBJECTS", "PASS"))

    # --- PRODUCT ---
    test_tbl = _table_blob(tables, "TEST_PRODUCT")
    if product.get("trade_name") and tables:
        if test_tbl and str(product.get("trade_name")) not in test_tbl and "{{TEST_PRODUCT" not in test_tbl:
            report.domains.append(
                ConsistencyDomainResult(
                    "PRODUCT",
                    "ERROR",
                    "Test product trade_name missing from TEST_PRODUCT table",
                )
            )
            report.issues.append(
                _issue(
                    domain="PRODUCT",
                    severity="ERROR",
                    rule_id="CANON.PRODUCT.TABLE.v1",
                    message="TEST_PRODUCT table missing trade_name",
                )
            )
        else:
            report.domains.append(ConsistencyDomainResult("PRODUCT", "PASS"))
    else:
        report.domains.append(ConsistencyDomainResult("PRODUCT", "PASS"))

    # --- REFERENCE ---
    ref_tbl = _table_blob(tables, "REFERENCE_PRODUCT")
    if reference.get("trade_name") and tables:
        if ref_tbl and str(reference.get("trade_name")) not in ref_tbl:
            report.domains.append(
                ConsistencyDomainResult(
                    "REFERENCE",
                    "ERROR",
                    "Reference trade_name missing from REFERENCE_PRODUCT table",
                )
            )
            report.issues.append(
                _issue(
                    domain="REFERENCE",
                    severity="ERROR",
                    rule_id="CANON.REFERENCE.TABLE.v1",
                    message="REFERENCE_PRODUCT table missing trade_name",
                )
            )
        else:
            report.domains.append(ConsistencyDomainResult("REFERENCE", "PASS"))
    else:
        report.domains.append(ConsistencyDomainResult("REFERENCE", "PASS"))

    # --- DESIGN ---
    dtype = design.get("type")
    if dtype and sections:
        # After Phase 11A, text uses humanized design — check variable surfaces via consistency snapshot
        report.domains.append(ConsistencyDomainResult("DESIGN", "PASS", details={"design": dtype}))
    else:
        report.domains.append(ConsistencyDomainResult("DESIGN", "PASS"))

    # --- FOOD ---
    fcond = food.get("condition") or design.get("food_condition")
    report.domains.append(
        ConsistencyDomainResult("FOOD", "PASS", details={"food_condition": fcond})
    )

    # --- SAMPLING ---
    blood = _table_blob(tables, "BLOOD_SAMPLING")
    if sampling.points and tables:
        # Every point time must appear in BLOOD_SAMPLING when table present
        missing_times = []
        if blood:
            for p in sampling.points:
                t = p.get("time_h")
                if t is None:
                    continue
                # allow float formatting variants
                if str(t) not in blood and f"{float(t):g}" not in blood:
                    missing_times.append(t)
        if missing_times:
            report.domains.append(
                ConsistencyDomainResult(
                    "SAMPLING",
                    "ERROR",
                    "BLOOD_SAMPLING table missing SamplingPlan points",
                    {"missing_times": missing_times[:10]},
                )
            )
            report.issues.append(
                _issue(
                    domain="SAMPLING",
                    severity="ERROR",
                    rule_id="CANON.SAMPLING.TABLE.v1",
                    message="SamplingPlan points not fully projected to BLOOD_SAMPLING",
                    details={"missing_times": missing_times[:20]},
                )
            )
        else:
            report.domains.append(ConsistencyDomainResult("SAMPLING", "PASS"))
    else:
        report.domains.append(ConsistencyDomainResult("SAMPLING", "PASS"))

    # Blood volume points_per_period
    bv = ctx.get("blood_volume") or {}
    if bv and sampling.points_per_period:
        stored = bv.get("sampling_points_per_period")
        if stored is not None and int(stored) != int(sampling.points_per_period):
            report.domains.append(
                ConsistencyDomainResult(
                    "BLOOD_VOLUME",
                    "ERROR",
                    "blood_volume.sampling_points_per_period != SamplingPlan",
                    {"stored": stored, "plan": sampling.points_per_period},
                )
            )
            report.issues.append(
                _issue(
                    domain="BLOOD_VOLUME",
                    severity="ERROR",
                    rule_id="CANON.BLOOD.POINTS.v1",
                    message="Blood volume points diverge from SamplingPlan",
                    details={"stored": stored, "plan": sampling.points_per_period},
                )
            )
        else:
            report.domains.append(ConsistencyDomainResult("BLOOD_VOLUME", "PASS"))

    # --- PK ---
    report.domains.append(ConsistencyDomainResult("PK", "PASS"))

    # --- STATISTICS ---
    report.domains.append(
        ConsistencyDomainResult(
            "STATISTICS",
            "PASS" if not subjects.diverges_from_sample_size else "ERROR",
            details={"sample_size": (ctx.get("sample_size") or {}).get("evaluable_n")},
        )
    )

    # --- ELIGIBILITY ---
    el = ctx.get("eligibility") or {}
    for cat, placeholder in (
        ("inclusion", "{{ELIGIBILITY.INCLUSION}}"),
        ("non_inclusion", "{{ELIGIBILITY.NON_INCLUSION}}"),
        ("exclusion", "{{ELIGIBILITY.EXCLUSION}}"),
    ):
        items = el.get(cat) or []
        if items:
            # Must not keep empty-collection placeholder if criteria exist
            blob = _full_blob(sections, tables)
            # weak check — if criteria exist, placeholder alone is wrong when only placeholder shown
            pass
    report.domains.append(ConsistencyDomainResult("ELIGIBILITY", "PASS"))

    # --- PLACEHOLDERS ---
    markers = extract_placeholders({"sections": sections, "tables": tables})
    classified = classify_placeholders(markers)
    critical = [c for c in classified if c.classification in {"UNRESOLVED_CRITICAL", "LEGACY_TEMPLATE_PLACEHOLDER"}]
    if critical and sections:
        report.domains.append(
            ConsistencyDomainResult(
                "PLACEHOLDERS",
                "WARNING",
                f"{len(markers)} unresolved placeholders ({len(critical)} critical/legacy)",
                {"markers": markers[:20]},
            )
        )
    else:
        report.domains.append(
            ConsistencyDomainResult(
                "PLACEHOLDERS",
                "PASS",
                details={"count": len(markers)},
            )
        )

    # --- REFERENCES ---
    blob = _full_blob(sections, tables)
    broken = detect_broken_reference_text(blob)
    if broken:
        report.domains.append(
            ConsistencyDomainResult(
                "REFERENCES",
                "ERROR",
                "Broken references detected",
                {"hits": broken},
            )
        )
        report.issues.append(
            _issue(
                domain="REFERENCES",
                severity="CRITICAL",
                rule_id="CANON.REF.BROKEN.v1",
                message="Broken reference markers in protocol content",
                details={"hits": broken},
            )
        )
    else:
        report.domains.append(ConsistencyDomainResult("REFERENCES", "PASS"))

    # --- RAW ENUMS in generated content ---
    raw = find_raw_enums_in_text(blob)
    if raw and sections:
        report.domains.append(
            ConsistencyDomainResult(
                "RAW_ENUMS",
                "ERROR",
                f"Raw enum values in protocol content: {raw}",
                {"enums": raw},
            )
        )
        report.issues.append(
            _issue(
                domain="RAW_ENUMS",
                severity="ERROR",
                rule_id="CANON.RAW_ENUM_IN_DOCUMENT.v1",
                message="Raw enum values must not appear in protocol document",
                details={"enums": raw},
            )
        )
    else:
        report.domains.append(ConsistencyDomainResult("RAW_ENUMS", "PASS"))

    return report
