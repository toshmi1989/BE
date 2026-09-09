"""Analogue similarity dimensions — Phase 15.2. Transparent, no black-box score."""

from __future__ import annotations

from typing import Any

from app.domain.decision_applicability import assess_analogue_applicability
from app.domain.research_evidence_models import AnalogueStudyRecord


def compare_analogue_dimensions(
    *,
    candidate: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, str]:
    """Return MATCH/PARTIAL/MISMATCH/UNKNOWN per dimension. Never hide mismatches."""

    def dim(key: str, cand_key: str | None = None) -> str:
        ck = cand_key or key
        a = _norm(candidate.get(ck))
        b = _norm(current.get(ck) or current.get(key))
        if not a or not b:
            return "UNKNOWN"
        if a == b:
            return "MATCH"
        if a in b or b in a:
            return "PARTIAL"
        return "MISMATCH"

    return {
        "ACTIVE_SUBSTANCE": dim("active_substance"),
        "DOSAGE_FORM": dim("dosage_form"),
        "DOSE": dim("dose"),
        "POPULATION": dim("population"),
        "DESIGN": dim("design"),
        "CONDITION": dim("condition"),
        "ROUTE": dim("route"),
        "ANALYTE": dim("analyte"),
        "REGULATORY_CONTEXT": dim("regulatory_context"),
    }


def derive_analogue_applicability(
    dimensions: dict[str, str],
    *,
    reviewed: bool = False,
) -> tuple[str, str]:
    """Explicit transparent rule — never DIRECT from substance similarity alone."""
    if dimensions.get("ACTIVE_SUBSTANCE") == "MISMATCH":
        return "LOW", "Different active substance"
    if dimensions.get("ACTIVE_SUBSTANCE") == "UNKNOWN":
        return "UNKNOWN", "Active substance similarity not reviewed"
    # Same substance
    dose = dimensions.get("DOSE")
    form = dimensions.get("DOSAGE_FORM")
    pop = dimensions.get("POPULATION")
    if form == "MATCH" and dose == "MATCH" and pop == "MATCH":
        # Still not automatic DIRECT
        return "HIGH", "Same substance/form/dose/population — not automatically DIRECT"
    if form == "MATCH" and dose == "MISMATCH" and pop in {"MATCH", "PARTIAL"}:
        return "MODERATE", "Same substance/form/population, different dose"
    if form == "MATCH":
        return "MODERATE", "Same substance and dosage form; other dimensions incomplete or mismatched"
    if not reviewed:
        return "UNKNOWN", "Applicability dimensions incomplete — requires review"
    return "LOW", "Limited similarity"


def enrich_analogue_record(
    rec: AnalogueStudyRecord,
    *,
    current: dict[str, Any],
) -> AnalogueStudyRecord:
    dims = compare_analogue_dimensions(
        candidate={
            "active_substance": rec.active_substance,
            "dosage_form": rec.dosage_form,
            "dose": rec.dose,
            "population": rec.population,
            "design": rec.design,
            "condition": rec.condition,
            "analyte": rec.analyte,
        },
        current=current,
    )
    rec.match_dimensions = dims
    appl, reason = derive_analogue_applicability(dims)
    rec.applicability_status = appl
    # Cross-check with Phase 15.1 helper
    ea = assess_analogue_applicability(
        same_substance=dims["ACTIVE_SUBSTANCE"] == "MATCH",
        same_dosage_form=dims["DOSAGE_FORM"] == "MATCH",
        same_dose=dims["DOSE"] == "MATCH",
        same_population=dims["POPULATION"] == "MATCH",
        same_design=dims["DESIGN"] == "MATCH",
    )
    # Prefer explicit rule; keep consistent (never escalate to DIRECT)
    if ea.applicability == "DIRECT":
        rec.applicability_status = "HIGH"
    return rec


def _norm(v: Any) -> str:
    return str(v or "").strip().lower().replace("  ", " ")
