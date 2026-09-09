"""Phase 15.4 — CVintra eligibility for authoritative sample-size calculation."""

from __future__ import annotations

from typing import Any

from app.domain.research_evidence_models import CVintraEvidence, ResearchClaim
from app.domain.research_usability import apply_usability
from app.domain.sample_size_engine_classes import (
    ELIGIBLE_APPLICABILITY,
    INELIGIBLE_APPLICABILITY,
    SAMPLE_SIZE_PK_PARAMETERS,
)


def _as_cvintra(claim: ResearchClaim | dict[str, Any] | CVintraEvidence) -> dict[str, Any] | None:
    if isinstance(claim, CVintraEvidence):
        return claim.to_dict()
    if isinstance(claim, ResearchClaim):
        apply_usability(claim, decision_domain="STATISTICS")
        if claim.cvintra:
            return dict(claim.cvintra)
        # Measurement-shaped CV
        m = claim.measurement or {}
        if str(m.get("parameter") or claim.field_path or "").upper() in {
            "CVINTRA",
            "CV_INTRA",
            "CV",
        } or claim.field_path in {"cv_intra", "cvintra", "statistics.cvintra"}:
            return {
                "CV_value": claim.value if claim.value is not None else m.get("value"),
                "CV_unit": claim.unit or m.get("unit") or "%",
                "PK_parameter": m.get("PK_parameter") or m.get("parameter_context") or m.get("pk_parameter"),
                "variability_type": m.get("variability_type") or "UNKNOWN",
                "verification_status": claim.verification_status,
                "applicability": claim.applicability,
                "usability": claim.usability,
                "source_claim_id": claim.id,
            }
        return None
    if isinstance(claim, dict):
        if "cvintra" in claim and isinstance(claim["cvintra"], dict):
            return dict(claim["cvintra"])
        return claim
    return None


def evaluate_cvintra_eligibility(
    claim: ResearchClaim | dict[str, Any] | CVintraEvidence,
    *,
    required_parameter: str | None = None,
) -> tuple[bool, list[str]]:
    """Return (eligible, blocker_codes). Never auto-selects among candidates."""
    blockers: list[str] = []

    verification = None
    applicability = None
    usability = None
    if isinstance(claim, ResearchClaim):
        apply_usability(claim, decision_domain="STATISTICS")
        verification = claim.verification_status
        applicability = claim.applicability
        usability = claim.usability
    elif isinstance(claim, CVintraEvidence):
        verification = claim.verification_status
        applicability = claim.applicability
        usability = claim.usability
    elif isinstance(claim, dict):
        verification = claim.get("verification_status")
        applicability = claim.get("applicability")
        usability = claim.get("usability")

    cv = _as_cvintra(claim)
    if cv is None:
        return False, ["MISSING_VERIFIED_CVINTRA"]

    verification = verification or cv.get("verification_status")
    applicability = applicability or cv.get("applicability")
    usability = usability or cv.get("usability")

    if verification == "PROPOSED":
        blockers.append("CV_PROPOSED_NOT_ALLOWED")
    elif verification == "REJECTED":
        blockers.append("CV_REJECTED_NOT_ALLOWED")
    elif verification != "VERIFIED":
        blockers.append("MISSING_VERIFIED_CVINTRA")

    if applicability in INELIGIBLE_APPLICABILITY:
        blockers.append("CV_LOW_APPLICABILITY")
    elif applicability not in ELIGIBLE_APPLICABILITY:
        blockers.append("CV_NOT_ELIGIBLE")

    if usability and usability != "USABLE_FOR_DECISION":
        blockers.append("CV_NOT_USABLE")

    vtype = str(cv.get("variability_type") or "UNKNOWN")
    if vtype == "BETWEEN_SUBJECT":
        blockers.append("CV_BETWEEN_SUBJECT_NOT_ALLOWED")
    elif vtype == "UNKNOWN":
        blockers.append("CV_UNKNOWN_TYPE_NOT_ALLOWED")
    elif vtype != "WITHIN_SUBJECT":
        blockers.append("CV_NOT_ELIGIBLE")

    pk = cv.get("PK_parameter")
    if pk is None or str(pk).strip() == "" or str(pk) == "OTHER":
        blockers.append("CV_MISSING_PK_PARAMETER")
    elif str(pk) not in SAMPLE_SIZE_PK_PARAMETERS:
        blockers.append("CV_MISSING_PK_PARAMETER")
    elif required_parameter and str(pk) != required_parameter:
        # Do not convert AUC CV into Cmax CV
        code = f"MISSING_CVINTRA_{required_parameter.upper().replace('0-', '').replace('-', '_')}"
        if required_parameter == "Cmax":
            blockers.append("MISSING_CVINTRA_CMAX")
        elif required_parameter.startswith("AUC"):
            blockers.append("MISSING_CVINTRA_AUC")
        else:
            blockers.append(code)

    try:
        val = float(cv.get("CV_value"))
        if val <= 0:
            blockers.append("INVALID_NUMERIC_RANGE")
    except (TypeError, ValueError):
        blockers.append("INVALID_NUMERIC_RANGE")

    return (len(blockers) == 0), blockers


def list_eligible_cvintra_for_parameter(
    claims: list[ResearchClaim],
    parameter: str,
) -> tuple[list[ResearchClaim], list[str]]:
    """Eligible CVintra claims for a PK parameter. Multiple → expert selection required."""
    eligible: list[ResearchClaim] = []
    all_blockers: list[str] = []
    for c in claims:
        ok, blockers = evaluate_cvintra_eligibility(c, required_parameter=parameter)
        if ok:
            eligible.append(c)
        else:
            all_blockers.extend(blockers)
    if len(eligible) > 1:
        values = []
        for c in eligible:
            cv = _as_cvintra(c) or {}
            try:
                values.append(float(cv.get("CV_value")))
            except (TypeError, ValueError):
                values.append(None)
        if len(set(values)) > 1:
            return eligible, ["MULTIPLE_CONFLICTING_CVINTRA", "MULTIPLE_ELIGIBLE_INPUTS_REQUIRES_EXPERT_SELECTION"]
        return eligible, ["MULTIPLE_ELIGIBLE_INPUTS_REQUIRES_EXPERT_SELECTION"]
    if not eligible:
        if parameter == "Cmax":
            return [], ["MISSING_CVINTRA_CMAX", "MISSING_VERIFIED_CVINTRA"]
        if str(parameter).startswith("AUC"):
            return [], ["MISSING_CVINTRA_AUC", "MISSING_VERIFIED_CVINTRA"]
        return [], ["MISSING_VERIFIED_CVINTRA"]
    return eligible, []


def extract_cv_numeric(claim: ResearchClaim | dict[str, Any] | CVintraEvidence) -> tuple[float, str, str]:
    """Return (cv_percent, unit, pk_parameter). Caller must have checked eligibility."""
    cv = _as_cvintra(claim)
    if not cv:
        raise ValueError("No CVintra payload")
    val = float(cv["CV_value"])
    unit = str(cv.get("CV_unit") or "%")
    pk = str(cv["PK_parameter"])
    return val, unit, pk
