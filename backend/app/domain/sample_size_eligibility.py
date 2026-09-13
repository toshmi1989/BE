"""Phase 15.4 — CVintra eligibility for authoritative sample-size calculation."""

from __future__ import annotations

from typing import Any

from app.domain.research_evidence_models import CVintraEvidence, ResearchClaim
from app.domain.research_usability import compute_usability
from app.domain.sample_size_engine_classes import (
    ELIGIBLE_APPLICABILITY,
    INELIGIBLE_APPLICABILITY,
    SAMPLE_SIZE_PK_PARAMETERS,
)


def _as_cvintra(claim: ResearchClaim | dict[str, Any] | CVintraEvidence) -> dict[str, Any] | None:
    if isinstance(claim, CVintraEvidence):
        return claim.to_dict()
    if isinstance(claim, ResearchClaim):
        # Read the claim as stored. Rewriting usability here for STATISTICS
        # used to mark a DESIGN-scoped CVintra unusable and send the writer
        # back to type the same number again.
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
        verification = claim.verification_status
        applicability = claim.applicability
        usability = claim.usability or compute_usability(claim)
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


# Blockers that mean "no usable CVintra". Value is the parameter they ask for.
CV_EVIDENCE_BLOCKERS: dict[str, str | None] = {
    "MISSING_VERIFIED_CVINTRA": None,
    "MISSING_CVINTRA": None,
    "MISSING_CVINTRA_CMAX": "Cmax",
    "MISSING_CVINTRA_AUC": "AUC",
    "CV_PROPOSED_NOT_ALLOWED": None,
    "CV_NOT_USABLE": None,
    "CV_NOT_ELIGIBLE": None,
    "CV_LOW_APPLICABILITY": None,
    "CV_REJECTED_NOT_ALLOWED": None,
    "CV_UNKNOWN_TYPE_NOT_ALLOWED": None,
    "CV_BETWEEN_SUBJECT_NOT_ALLOWED": None,
    "CV_MISSING_PK_PARAMETER": None,
}

# Said once the evidence exists but the engine has not run on it yet
CALCULATION_NOT_RUN = "CALCULATION_NOT_RUN"
CALCULATION_REQUIRES_RERUN = "CALCULATION_REQUIRES_RERUN"


def eligible_cv_parameters(claims: list[ResearchClaim]) -> set[str]:
    """PK parameters that now have CVintra the engine is allowed to use."""
    parameters: set[str] = set()
    for claim in claims:
        cv = _as_cvintra(claim)
        if not cv:
            continue
        parameter = str(cv.get("PK_parameter") or "")
        if not parameter:
            continue
        ok, _blockers = evaluate_cvintra_eligibility(claim, required_parameter=parameter)
        if ok:
            parameters.add(parameter)
    return parameters


def _satisfied_by(parameter_asked: str | None, available: set[str]) -> bool:
    if not available:
        return False
    if parameter_asked is None:
        return True
    if parameter_asked == "AUC":
        # AUC0-t and AUC0-inf both answer a request for AUC variability
        return any(p.startswith("AUC") for p in available)
    return parameter_asked in available


def current_evidence_blockers(
    stored_reasons: list[Any],
    claims: list[ResearchClaim],
    *,
    has_calculation: bool,
) -> list[str]:
    """Stored blockers re-read against the evidence that exists right now.

    A calculation keeps the blockers it had when it ran. Replaying them after the
    expert supplied the value sends the writer back to a gap that is already
    closed, so a satisfied "no CVintra" blocker is replaced by the step that
    actually remains: running the calculation again on the new evidence.
    """
    available = eligible_cv_parameters(claims)
    kept: list[str] = []
    satisfied = False
    for raw in stored_reasons or []:
        code = str(raw)
        if code in CV_EVIDENCE_BLOCKERS and _satisfied_by(CV_EVIDENCE_BLOCKERS[code], available):
            satisfied = True
            continue
        if code not in kept:
            kept.append(code)
    if satisfied:
        remaining = CALCULATION_REQUIRES_RERUN if has_calculation else CALCULATION_NOT_RUN
        if remaining not in kept:
            kept.append(remaining)
    return kept


def extract_cv_numeric(claim: ResearchClaim | dict[str, Any] | CVintraEvidence) -> tuple[float, str, str]:
    """Return (cv_percent, unit, pk_parameter). Caller must have checked eligibility."""
    cv = _as_cvintra(claim)
    if not cv:
        raise ValueError("No CVintra payload")
    val = float(cv["CV_value"])
    unit = str(cv.get("CV_unit") or "%")
    pk = str(cv["PK_parameter"])
    return val, unit, pk
