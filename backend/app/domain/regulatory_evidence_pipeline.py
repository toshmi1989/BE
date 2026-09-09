"""Regulatory evidence pipeline orchestration — Phase 13.1.

Ingest → claims → conflicts → review queue → coverage.
Never mutates Study / Design / Sampling / PK / Safety / ReferenceProduct finals.
Never auto-verifies KnowledgeRules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain.document_ingest import extract_document
from app.domain.regulatory_claims import (
    EvidenceProvenance,
    RegulatoryEvidenceClaim,
    build_claim,
    detect_stale_evidence,
    link_claim_to_basis,
    ProposedRegulatoryBasis,
)
from app.domain.regulatory_conflicts import (
    ClassifiedEvidenceConflict,
    StudyEvidenceConflict,
    detect_study_evidence_conflict,
    detect_value_conflicts,
)
from app.domain.regulatory_coverage import RegulatoryCoverageReport, build_regulatory_coverage_report
from app.domain.regulatory_evidence_manifest import (
    DEFAULT_REGULATORY_ROOT,
    RegulatoryEvidenceManifest,
    detect_duplicate_sources,
    load_regulatory_manifest,
)
from app.domain.regulatory_evidence_tasks import (
    PRIORITY_RULE_WORKSPACE,
    REGULATORY_EVIDENCE_TASKS,
    gap_for_missing_task_source,
)
from app.domain.regulatory_interview import interview_claims_as_evidence, proposed_rules_remain_proposed
from app.domain.regulatory_review_queue import (
    RegulatoryReviewQueue,
    enqueue_claim_review,
    enqueue_rule_candidate,
)


@dataclass
class RegulatoryEvidencePipelineResult:
    manifest: dict[str, Any]
    ingested: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    study_conflicts: list[dict[str, Any]] = field(default_factory=list)
    review_queue: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    duplicates: list[dict[str, Any]] = field(default_factory=list)
    study_mutated: bool = False
    rules_auto_verified: int = 0
    package_status: str = "MISSING"

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "ingested": self.ingested,
            "claims": self.claims,
            "conflicts": self.conflicts,
            "study_conflicts": self.study_conflicts,
            "review_queue": self.review_queue,
            "coverage": self.coverage,
            "knowledge_gaps": self.knowledge_gaps,
            "duplicates": self.duplicates,
            "study_mutated": self.study_mutated,
            "rules_auto_verified": self.rules_auto_verified,
            "package_status": self.package_status,
        }


def run_regulatory_evidence_pipeline(
    *,
    root: Path | None = None,
    canonical_study: dict[str, Any] | None = None,
    include_interview: bool = True,
) -> RegulatoryEvidencePipelineResult:
    """Full evidence pipeline. Guarantees study_mutated=False."""
    base = Path(root) if root else DEFAULT_REGULATORY_ROOT
    manifest = load_regulatory_manifest(base)
    duplicates = detect_duplicate_sources(manifest.sources)

    ingested: list[dict[str, Any]] = []
    claims: list[RegulatoryEvidenceClaim] = []

    for src in manifest.sources:
        if src.ingestion_status != "OK" or not src.relative_path:
            continue
        if src.source_class == "EXPERT_INTERVIEW":
            continue
        path = base / src.relative_path
        try:
            result = extract_document(filename=path.name, content=path.read_bytes())
            ingested.append(
                {
                    "source_id": src.source_id,
                    "document_id": getattr(result, "document_id", None) or src.source_id,
                    "pages": len(getattr(result, "pages", None) or []),
                    "chunks": len(getattr(result, "chunks", None) or []),
                    "checksum": src.file_hash,
                    "source_version": src.source_version,
                    "status": "OK",
                }
            )
            # Create RAW_EXTRACT claim from first chunk/page if text present — UNVERIFIED
            text = None
            pages = getattr(result, "pages", None) or []
            if pages:
                text = getattr(pages[0], "text", None) or (pages[0].get("text") if isinstance(pages[0], dict) else None)
            if not text:
                chunks = getattr(result, "chunks", None) or []
                if chunks:
                    text = getattr(chunks[0], "text", None) or (
                        chunks[0].get("text") if isinstance(chunks[0], dict) else None
                    )
            if text:
                claims.append(
                    build_claim(
                        claim_id=f"CLM-{src.source_id}-RAW",
                        claim_kind="RAW_EXTRACT",
                        domain="REPORTING",
                        raw_extract=str(text)[:2000],
                        normalized_claim=None,
                        confidence="LOW",
                        verification_status="EXTRACTED",
                        source_class=src.source_class,
                        provenance=EvidenceProvenance(
                            source_id=src.source_id,
                            document_id=src.source_id,
                            source_version=src.source_version,
                            page=1,
                            quoted_text=str(text)[:2000],
                            extraction_method="DOCUMENT_INGEST",
                        ),
                    )
                )
        except Exception as exc:  # noqa: BLE001 — surface extraction failure
            ingested.append(
                {
                    "source_id": src.source_id,
                    "status": "FAILED",
                    "error": str(exc),
                }
            )

    if include_interview:
        claims.extend(interview_claims_as_evidence())

    claim_dicts = [c.to_dict() for c in claims]
    # Flatten provenance source_id for conflict detector
    for cd, c in zip(claim_dicts, claims):
        if c.provenance:
            cd["source_id"] = c.provenance.source_id
            cd["source_ids"] = [c.provenance.source_id]

    conflicts = detect_value_conflicts(claim_dicts)

    study_conflicts: list[StudyEvidenceConflict] = []
    if canonical_study:
        # Example check: product dose if a claim asserts different dose — illustrative only when claims exist
        product = canonical_study.get("product") or {}
        canon_dose = product.get("dosage") or product.get("dose")
        for c in claims:
            if c.field_name in {"dose", "dosage", "product.dose"} and c.normalized_claim:
                sec = detect_study_evidence_conflict(
                    study_field="product.dosage",
                    canonical_value=canon_dose,
                    source_value=c.normalized_claim,
                    source_ids=[c.provenance.source_id] if c.provenance else [],
                    claim_ids=[c.claim_id],
                    conflict_id=f"SEC-{c.claim_id}",
                )
                if sec:
                    study_conflicts.append(sec)

    queue = RegulatoryReviewQueue(queue_id=f"RQ-{uuid.uuid4().hex[:8]}")
    for c in claims:
        if c.verification_status in {"EXTRACTED", "UNVERIFIED", "REVIEW_REQUIRED"}:
            enqueue_claim_review(queue, item_id=f"REV-{c.claim_id}", claim_id=c.claim_id)
    for rule_code in PRIORITY_RULE_WORKSPACE:
        enqueue_rule_candidate(queue, item_id=f"REV-RULE-{rule_code}", rule_code=rule_code)

    gaps = list(manifest.knowledge_gaps)
    for task in REGULATORY_EVIDENCE_TASKS:
        if manifest.package_status in {"MISSING", "PARTIAL"}:
            # Official sources only — interview must not suppress regulatory gaps
            if task.requires_official_source and not manifest.present_regulatory_sources():
                gaps.append(gap_for_missing_task_source(task))

    # Dedup gaps
    seen: set[str] = set()
    uniq_gaps: list[dict[str, Any]] = []
    for g in gaps:
        code = str(g.get("code") or "")
        if code in seen:
            continue
        seen.add(code)
        uniq_gaps.append(g)

    coverage = build_regulatory_coverage_report(
        report_id=f"COV-{uuid.uuid4().hex[:8]}",
        package_status=manifest.package_status,
        sources=[s.to_dict() for s in manifest.sources],
        claims=claim_dicts,
        conflicts=[c.to_dict() for c in conflicts],
        review_items=queue.to_dict()["items"],
        knowledge_gaps=uniq_gaps,
        knowledge_rules=[{"rule_code": r, "status": "PROPOSED"} for r in PRIORITY_RULE_WORKSPACE],
    )

    assert proposed_rules_remain_proposed()

    return RegulatoryEvidencePipelineResult(
        manifest=manifest.to_dict(),
        ingested=ingested,
        claims=claim_dicts,
        conflicts=[c.to_dict() for c in conflicts],
        study_conflicts=[c.to_dict() for c in study_conflicts],
        review_queue=queue.to_dict(),
        coverage=coverage.to_dict(),
        knowledge_gaps=uniq_gaps,
        duplicates=duplicates,
        study_mutated=False,
        rules_auto_verified=0,
        package_status=manifest.package_status,
    )
