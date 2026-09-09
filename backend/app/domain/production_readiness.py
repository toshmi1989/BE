"""ProductionReadinessReport — Phase 12C aggregation.

Assembles existing QA / completeness / gate / AI results. Does not weaken gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ProductionReadinessReport:
    run_id: str
    generated_at: str
    package_id: str | None = None
    package_classification: str = "TECHNICAL_FIXTURE"
    medical_validation_claimed: bool = False

    input_completeness: dict[str, Any] = field(default_factory=dict)
    ingestion: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    canonical_state: dict[str, Any] = field(default_factory=dict)
    expert_decisions: dict[str, Any] = field(default_factory=dict)
    content_resolution: dict[str, Any] = field(default_factory=dict)
    document_qa: dict[str, Any] = field(default_factory=dict)
    docx: dict[str, Any] = field(default_factory=dict)
    legacy_scan: dict[str, Any] = field(default_factory=dict)
    reference_integrity: dict[str, Any] = field(default_factory=dict)
    gate: dict[str, Any] = field(default_factory=dict)
    ai_off: dict[str, Any] = field(default_factory=dict)
    ai_on: dict[str, Any] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    regulatory_evidence_coverage: dict[str, Any] = field(default_factory=dict)
    known_limitations: list[str] = field(default_factory=list)
    production_blockers: list[str] = field(default_factory=list)
    recommendation: str = "NOT READY"  # PRODUCTION-READY | READY-WITH-BLOCKERS | NOT READY

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_production_readiness_report(
    *,
    package_id: str | None = None,
    classification: str = "TECHNICAL_FIXTURE",
    manifest_summary: dict | None = None,
    ingestion_summary: dict | None = None,
    evidence_summary: dict | None = None,
    canonical_summary: dict | None = None,
    expert_summary: dict | None = None,
    content_summary: dict | None = None,
    qa_report: Any = None,
    docx_summary: dict | None = None,
    legacy_summary: dict | None = None,
    reference_summary: dict | None = None,
    gate_results: dict | None = None,
    ai_off_result: dict | None = None,
    ai_on_result: dict | None = None,
    performance: dict | None = None,
    regulatory_evidence_coverage: dict | None = None,
    known_limitations: list[str] | None = None,
    production_blockers: list[str] | None = None,
) -> ProductionReadinessReport:
    import uuid

    qa_dict: dict[str, Any] = {}
    if qa_report is not None:
        if hasattr(qa_report, "to_dict"):
            qa_dict = qa_report.to_dict()
        elif isinstance(qa_report, dict):
            qa_dict = qa_report
        else:
            qa_dict = {
                "gate": getattr(qa_report, "gate", None),
                "readiness": getattr(qa_report, "readiness", None),
                "critical_count": getattr(qa_report, "critical_count", None),
                "error_count": getattr(qa_report, "error_count", None),
                "warning_count": getattr(qa_report, "warning_count", None),
                "table_errors": getattr(qa_report, "table_errors", None),
                "reference_errors": getattr(qa_report, "reference_errors", None),
            }

    blockers = list(production_blockers or [])
    gates = dict(gate_results or {})
    if gates.get("FINAL") == "BLOCKED" and not any("FINAL" in str(b).upper() and "BLOCK" in str(b).upper() for b in blockers):
        blockers.append("FINAL gate BLOCKED — critical unresolved content or validation")
    # Deduplicate while preserving order
    seen_b: set[str] = set()
    deduped: list[str] = []
    for b in blockers:
        if b not in seen_b:
            seen_b.add(b)
            deduped.append(b)
    blockers = deduped
    cov = dict(regulatory_evidence_coverage or {})
    if cov.get("package_status") in {"MISSING", "PARTIAL"}:
        msg = f"Regulatory evidence package: {cov.get('package_status')}"
        if msg not in blockers:
            blockers.append(msg)
        if int(cov.get("sources_missing") or 0) > 0:
            m2 = f"Missing regulatory sources: {cov.get('sources_missing')}"
            if m2 not in blockers:
                blockers.append(m2)
    if classification == "TECHNICAL_FIXTURE":
        lim = list(known_limitations or [])
        note = "Package is TECHNICAL_FIXTURE_ONLY — not medical validation"
        if note not in lim:
            lim.insert(0, note)
    else:
        lim = list(known_limitations or [])

    # Recommendation
    final_gate = gates.get("FINAL")
    review_gate = gates.get("REVIEW")
    if classification == "TECHNICAL_FIXTURE":
        if blockers or final_gate == "BLOCKED":
            rec = "READY-WITH-BLOCKERS"
        else:
            rec = "READY-WITH-BLOCKERS"  # technical fixture never PRODUCTION-READY medical claim
        if "TECHNICAL_FIXTURE cannot claim PRODUCTION-READY medical status" not in lim:
            lim.append("TECHNICAL_FIXTURE cannot claim PRODUCTION-READY medical status")
    else:
        if blockers or final_gate == "BLOCKED":
            rec = "READY-WITH-BLOCKERS" if review_gate == "READY" else "NOT READY"
        else:
            rec = "PRODUCTION-READY"

    return ProductionReadinessReport(
        run_id=str(uuid.uuid4()),
        generated_at=datetime.now(timezone.utc).isoformat(),
        package_id=package_id,
        package_classification=classification,
        medical_validation_claimed=False if classification == "TECHNICAL_FIXTURE" else True,
        input_completeness=dict(manifest_summary or {}),
        ingestion=dict(ingestion_summary or {}),
        evidence=dict(evidence_summary or {}),
        canonical_state=dict(canonical_summary or {}),
        expert_decisions=dict(expert_summary or {}),
        content_resolution=dict(content_summary or {}),
        document_qa=qa_dict,
        docx=dict(docx_summary or {}),
        legacy_scan=dict(legacy_summary or {}),
        reference_integrity=dict(reference_summary or {}),
        gate=gates,
        ai_off=dict(ai_off_result or {}),
        ai_on=dict(ai_on_result or {"status": "NOT_AVAILABLE"}),
        performance=dict(performance or {}),
        regulatory_evidence_coverage=dict(regulatory_evidence_coverage or {}),
        known_limitations=lim,
        production_blockers=blockers,
        recommendation=rec,
    )
