"""Phase 15.4 — Deterministic Sample Size Engine (orchestration).

AI must not perform authoritative arithmetic. Study is never mutated here.
"""

from __future__ import annotations

from typing import Any

from app.domain.exceptions import ValidationError
from app.domain.research_evidence_models import ResearchClaim
from app.domain.research_evidence_store import list_claims
from app.domain.sample_size_eligibility import (
    evaluate_cvintra_eligibility,
    extract_cv_numeric,
    list_eligible_cvintra_for_parameter,
)
from app.domain.sample_size_engine_classes import (
    CALCULATION_VERSION,
    CANONICAL_METHOD_ID,
    SAMPLE_SIZE_ENGINE_VERSION,
    SAMPLE_SIZE_PK_PARAMETERS,
    SUPPORTED_DESIGNS,
    UNSUPPORTED_DESIGNS,
)
from app.domain.sample_size_explanation import build_explanation
from app.domain.sample_size_fingerprint import fingerprint_from_inputs
from app.domain.sample_size_math import run_standard_2x2
from app.domain.sample_size_models import (
    ProvenancedInput,
    SampleSizeCalculationRecord,
    SampleSizeDiscrepancy,
    SampleSizeScenario,
)
from app.domain.sample_size_recommendation import build_recommendation
from app.domain.sample_size_store import (
    list_calculations,
    next_version_number,
    put_calculation,
)


def _require_provenanced(
    name: str,
    value: Any,
    source_kind: str | None,
    *,
    source_claim_id: str | None = None,
    source_label: str | None = None,
) -> ProvenancedInput | str:
    if value is None:
        return f"MISSING_{name.upper()}" if name != "expected_ratio" else "MISSING_EXPECTED_RATIO"
    if not source_kind:
        return "MISSING_PROVENANCE"
    return ProvenancedInput(
        name=name,
        value=value,
        source_kind=source_kind,
        source_claim_id=source_claim_id,
        source_label=source_label,
    )


def resolve_current_protocol_n(
    *,
    current_protocol_n: int | None,
    current_protocol_n_source: str | None,
    context: dict[str, Any] | None,
) -> tuple[int | None, str | None]:
    if current_protocol_n is not None:
        return current_protocol_n, current_protocol_n_source or "EXPLICIT_CONFIGURATION"
    if context:
        n = context.get("randomized_n")
        if n is None and isinstance(context.get("structured_facts"), dict):
            n = context["structured_facts"].get("subjects.randomized_n")
        if n is not None:
            src = None
            if isinstance(context.get("fact_sources"), dict):
                src = context["fact_sources"].get("subjects.randomized_n")
            return int(n), src or "SYNOPSIS"
    return None, None


def calculate_sample_size_authoritative(
    *,
    study_id: str,
    design: str | None,
    parameter: str | None = None,
    parameters: list[str] | None = None,
    # Explicit numeric (no silent defaults)
    expected_ratio: float | None = None,
    expected_ratio_source: str | None = None,
    alpha: float | None = None,
    alpha_source: str | None = None,
    power: float | None = None,
    power_source: str | None = None,
    dropout_percent: float | None = None,
    dropout_source: str | None = None,
    inflation_method: str | None = None,
    be_lower: float | None = None,
    be_upper: float | None = None,
    be_limits_source: str | None = None,
    # CV selection
    cv_claim_id: str | None = None,
    cv_claim_ids_by_parameter: dict[str, str] | None = None,
    claims: list[ResearchClaim] | None = None,
    # Current protocol fact
    current_protocol_n: int | None = None,
    current_protocol_n_source: str | None = None,
    context: dict[str, Any] | None = None,
    controlling_parameter: str | None = None,
    decision_id: str | None = None,
    created_by: str | None = None,
    ai_authoritative: bool = False,
) -> SampleSizeCalculationRecord:
    """Gate → calculate → scenarios → discrepancy. Never mutates Study."""
    if ai_authoritative:
        raise ValidationError(
            "AI cannot perform authoritative sample-size calculation",
            field="ai",
        )

    blockers: list[str] = []
    inputs: list[ProvenancedInput] = []
    warnings: list[str] = []

    if not design:
        blockers.append("MISSING_DESIGN")
    elif design in UNSUPPORTED_DESIGNS or (
        design not in SUPPORTED_DESIGNS and design not in {"CROSSOVER_2X2"}
    ):
        blockers.append("METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW")
    elif design == "CROSSOVER_2X2":
        design = "STANDARD_2X2_CROSSOVER"

    params = list(parameters or [])
    if parameter and parameter not in params:
        params.append(parameter)
    if not params:
        blockers.append("MISSING_PARAMETER")
    for p in params:
        if p not in SAMPLE_SIZE_PK_PARAMETERS:
            blockers.append("MISSING_PARAMETER")

    # Explicit inputs — no silent defaults
    mapping = [
        ("expected_ratio", expected_ratio, expected_ratio_source, "MISSING_EXPECTED_RATIO"),
        ("alpha", alpha, alpha_source, "MISSING_ALPHA"),
        ("power", power, power_source, "MISSING_POWER"),
    ]
    for name, val, src, miss in mapping:
        pin = _require_provenanced(name, val, src)
        if isinstance(pin, str):
            blockers.append(miss if val is None else "MISSING_PROVENANCE")
        else:
            inputs.append(pin)

    if be_lower is None or be_upper is None:
        blockers.append("MISSING_BE_LIMITS")
    else:
        pin = _require_provenanced(
            "be_limits",
            {"be_lower": be_lower, "be_upper": be_upper},
            be_limits_source,
        )
        if isinstance(pin, str):
            blockers.append("MISSING_PROVENANCE")
        else:
            inputs.append(pin)

    # Dropout: if inflation requested without dropout → block; if neither → allow NONE
    if inflation_method and inflation_method != "NONE" and dropout_percent is None:
        blockers.append("MISSING_DROPOUT_ASSUMPTION")
    if dropout_percent is not None:
        pin = _require_provenanced("dropout_percent", dropout_percent, dropout_source)
        if isinstance(pin, str):
            blockers.append("MISSING_DROPOUT_ASSUMPTION" if dropout_percent is None else "MISSING_PROVENANCE")
        else:
            inputs.append(pin)
        if not inflation_method:
            blockers.append("MISSING_DROPOUT_ASSUMPTION")  # method must be explicit with dropout
        else:
            inputs.append(
                ProvenancedInput(
                    name="inflation_method",
                    value=inflation_method,
                    source_kind=dropout_source or "EXPLICIT_CONFIGURATION",
                )
            )
    elif inflation_method is None:
        inflation_method = "NONE"
        inputs.append(
            ProvenancedInput(
                name="inflation_method",
                value="NONE",
                source_kind="EXPLICIT_CONFIGURATION",
                notes="No dropout inflation requested",
            )
        )

    cur_n, cur_src = resolve_current_protocol_n(
        current_protocol_n=current_protocol_n,
        current_protocol_n_source=current_protocol_n_source,
        context=context,
    )
    if cur_n is not None:
        sk = cur_src if cur_src in {
            "SYNOPSIS",
            "EXPLICIT_CONFIGURATION",
            "EXPERT_INPUT",
            "VERIFIED_STUDY_FACT",
        } else "VERIFIED_STUDY_FACT"
        inputs.append(
            ProvenancedInput(
                name="current_protocol_n",
                value=cur_n,
                source_kind=sk,
                source_label=cur_src or "CURRENT_STUDY_FACT",
                notes="CURRENT_STUDY_FACT — not calculated_required_n",
            )
        )

    study_claims = claims if claims is not None else list_claims(study_id=study_id)
    scenarios: list[SampleSizeScenario] = []
    selected_claim_by_param: dict[str, ResearchClaim] = {}

    # CV gating per parameter
    if "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW" not in blockers and design in set(SUPPORTED_DESIGNS):
        for p in params:
            chosen: ResearchClaim | None = None
            pick_id = None
            if cv_claim_ids_by_parameter and p in cv_claim_ids_by_parameter:
                pick_id = cv_claim_ids_by_parameter[p]
            elif cv_claim_id and len(params) == 1:
                pick_id = cv_claim_id

            if pick_id:
                chosen = next((c for c in study_claims if c.id == pick_id or c.claim_id == pick_id), None)
                if chosen is None:
                    blockers.append("MISSING_VERIFIED_CVINTRA")
                else:
                    ok, cv_blockers = evaluate_cvintra_eligibility(chosen, required_parameter=p)
                    if not ok:
                        blockers.extend(cv_blockers)
                    else:
                        selected_claim_by_param[p] = chosen
            else:
                eligible, multi = list_eligible_cvintra_for_parameter(study_claims, p)
                if multi:
                    blockers.extend(multi)
                elif not eligible:
                    blockers.extend(
                        ["MISSING_VERIFIED_CVINTRA"]
                        + (["MISSING_CVINTRA_CMAX"] if p == "Cmax" else [])
                        + (["MISSING_CVINTRA_AUC"] if str(p).startswith("AUC") else [])
                    )
                else:
                    selected_claim_by_param[p] = eligible[0]

    # Deduplicate blockers while preserving order
    seen: set[str] = set()
    uniq_blockers: list[str] = []
    for b in blockers:
        if b not in seen:
            seen.add(b)
            uniq_blockers.append(b)
    blockers = uniq_blockers

    primary_param = params[0] if params else None
    required_n = randomized_n = None
    raw_n = achieved = None
    method = formula = software = algo = None
    cv_value = None
    cv_unit = "%"
    status = "BLOCKED"
    discrepancy = None
    fingerprint = None
    controlling_requires_expert = len(params) > 1 and not controlling_parameter

    # Gate: only numeric blockers that prevent math (CV multi-select still blocks)
    hard_block = [
        b
        for b in blockers
        if b
        not in {
            "REQUIRES_EXPERT_SELECTION",
        }
    ]
    can_calc = (
        not hard_block
        and design == "STANDARD_2X2_CROSSOVER"
        and expected_ratio is not None
        and alpha is not None
        and power is not None
        and be_lower is not None
        and be_upper is not None
        and primary_param is not None
        and set(params).issubset(set(selected_claim_by_param))
    )

    if can_calc:
        try:
            for p in params:
                claim = selected_claim_by_param[p]
                cv_val, cv_u, pk = extract_cv_numeric(claim)
                inputs.append(
                    ProvenancedInput(
                        name="cv_value",
                        value=cv_val,
                        source_kind="EVIDENCE_MEASUREMENT",
                        source_claim_id=claim.id,
                        source_label=f"Verified literature evidence ({pk})",
                        notes=f"parameter={pk}; unit={cv_u}",
                    )
                )
                out = run_standard_2x2(
                    design=design,
                    parameter=p,
                    cv_percent=cv_val,
                    expected_ratio=float(expected_ratio),
                    alpha=float(alpha),
                    power=float(power),
                    be_lower=float(be_lower),
                    be_upper=float(be_upper),
                    dropout_percent=dropout_percent,
                    inflation_method=inflation_method,
                )
                sc = SampleSizeScenario(
                    parameter=p,
                    required_n=out["required_n"],
                    randomized_n=out["randomized_n"],
                    raw_n=out["raw_n"],
                    achieved_power=out["achieved_power"],
                    target_power=float(power),
                    cv_value=cv_val,
                    cv_unit=cv_u,
                    cv_source_claim_id=claim.id,
                    status="CALCULATED" if out["required_n"] is not None else "BLOCKED",
                )
                scenarios.append(sc)
                warnings.extend(out.get("warnings") or [])
                method = out["method"]
                formula = out["formula"]
                software = out["software_version"]
                algo = out["algorithm_version"]

            if len(scenarios) > 1 and not controlling_parameter:
                blockers.append("REQUIRES_EXPERT_SELECTION")
                status = "PENDING_REVIEW"
                controlling_requires_expert = True
                primary = scenarios[0]
            elif controlling_parameter:
                match = next((s for s in scenarios if s.parameter == controlling_parameter), None)
                if match is None:
                    blockers.append("REQUIRES_EXPERT_SELECTION")
                    primary = scenarios[0]
                    controlling_requires_expert = True
                else:
                    primary = match
                    controlling_requires_expert = False
            else:
                primary = scenarios[0]
                controlling_requires_expert = False

            required_n = primary.required_n
            randomized_n = primary.randomized_n
            raw_n = primary.raw_n
            achieved = primary.achieved_power
            cv_value = primary.cv_value
            cv_unit = primary.cv_unit
            primary_param = primary.parameter

            fingerprint = fingerprint_from_inputs(
                design=design,
                parameter=primary_param,
                cv_value=cv_value,
                expected_ratio=float(expected_ratio),
                alpha=float(alpha),
                power=float(power),
                dropout_percent=dropout_percent,
                method=method or CANONICAL_METHOD_ID,
                calculation_version=CALCULATION_VERSION,
                be_lower=float(be_lower),
                be_upper=float(be_upper),
                inflation_method=inflation_method,
            )

            if "REQUIRES_EXPERT_SELECTION" in blockers:
                status = "PENDING_REVIEW"
            else:
                status = "CALCULATED"

            if cur_n is not None and randomized_n is not None and int(cur_n) != int(randomized_n):
                discrepancy = SampleSizeDiscrepancy(
                    current_protocol_n=int(cur_n),
                    calculated_randomized_n=int(randomized_n),
                    current_source=cur_src or "SYNOPSIS",
                )
        except ValidationError as e:
            blockers.append("INVALID_NUMERIC_RANGE")
            warnings.append(str(e))
            status = "BLOCKED"
            controlling_requires_expert = True
    else:
        status = "BLOCKED"
        multi_codes = {
            "MULTIPLE_ELIGIBLE_INPUTS_REQUIRES_EXPERT_SELECTION",
            "MULTIPLE_CONFLICTING_CVINTRA",
        }
        if (
            "MISSING_VERIFIED_CVINTRA" not in blockers
            and not selected_claim_by_param
            and not multi_codes.intersection(blockers)
        ):
            blockers.append("MISSING_VERIFIED_CVINTRA")

    # Re-unique blockers
    seen2: set[str] = set()
    deduped: list[str] = []
    for b in blockers:
        if b not in seen2:
            seen2.add(b)
            deduped.append(b)
    blockers = deduped

    recommendation = build_recommendation(
        current_protocol_n=cur_n,
        calculated_randomized_n=randomized_n,
        blocked=status == "BLOCKED",
    )

    # Versioning: new record always
    version_number = next_version_number(study_id)
    supersedes = None
    prev = list_calculations(study_id)
    if prev:
        supersedes = prev[-1].id
        # mark previous as superseded in-place for workflow (history preserved)
        prev[-1].status = "SUPERSEDED" if prev[-1].status == "CALCULATED" else prev[-1].status

    rec = SampleSizeCalculationRecord(
        study_id=study_id,
        decision_id=decision_id,
        design=design or "UNKNOWN",
        parameter=primary_param,
        cv_value=cv_value,
        cv_unit=cv_unit,
        expected_ratio=expected_ratio,
        alpha=alpha,
        power=power,
        target_power=power,
        achieved_power=achieved,
        dropout_percent=dropout_percent,
        inflation_method=inflation_method,
        required_n=required_n,
        randomized_n=randomized_n,
        raw_n=raw_n,
        rounding_rule="CEIL_EVEN_2X2",
        method=method,
        calculation_version=CALCULATION_VERSION,
        engine_version=SAMPLE_SIZE_ENGINE_VERSION,
        algorithm_version=algo,
        status=status,
        fingerprint=fingerprint,
        version_number=version_number,
        supersedes_id=supersedes,
        inputs=inputs,
        scenarios=scenarios,
        controlling_parameter=controlling_parameter if not controlling_requires_expert else None,
        controlling_requires_expert=controlling_requires_expert if len(scenarios) > 1 else False,
        recommendation=recommendation,
        discrepancy=discrepancy,
        blocking_reasons=blockers,
        warnings=warnings,
        current_protocol_n=cur_n,
        current_protocol_n_source=cur_src,
        be_lower=be_lower,
        be_upper=be_upper,
        formula=formula,
        software_version=software,
        study_mutated=False,
        created_by=created_by,
        eligible_for_protocol_use=False,
    )
    rec.explanation = build_explanation(rec)
    put_calculation(rec)
    return rec


def ui_sample_size_panel(study_id: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Decision Center Sample Size section contract — calculated ≠ approved."""
    calcs = list_calculations(study_id)
    latest = calcs[-1] if calcs else None
    cur_n, cur_src = resolve_current_protocol_n(
        current_protocol_n=None,
        current_protocol_n_source=None,
        context=context,
    )
    if latest and latest.current_protocol_n is not None:
        cur_n = latest.current_protocol_n
        cur_src = latest.current_protocol_n_source

    evidence_rows = []
    for c in list_claims(study_id=study_id):
        if not c.cvintra and not (
            c.field_path and "cv" in str(c.field_path).lower()
        ):
            continue
        ok, blockers = evaluate_cvintra_eligibility(c)
        cv = c.cvintra or {}
        evidence_rows.append(
            {
                "claim_id": c.id,
                "parameter": cv.get("PK_parameter"),
                "cv_value": cv.get("CV_value", c.value),
                "verification_status": c.verification_status,
                "applicability": c.applicability,
                "eligible": ok,
                "blockers": blockers,
                "source_id": c.source_id,
            }
        )

    return {
        "section": "SAMPLE_SIZE",
        "study_id": study_id,
        "current_protocol_value": cur_n,
        "current_protocol_source": cur_src or "SYNOPSIS",
        "current_is_calculated": False,
        "available_evidence": evidence_rows,
        "scenarios": [s.to_dict() for s in (latest.scenarios if latest else [])],
        "controlling_parameter": (
            latest.controlling_parameter
            if latest and latest.controlling_parameter
            else "REQUIRES_EXPERT_DECISION"
        ),
        "calculated_n": latest.randomized_n if latest else None,
        "required_n": latest.required_n if latest else None,
        "discrepancy": latest.discrepancy.to_dict() if latest and latest.discrepancy else None,
        "status": latest.status if latest else "NO_CALCULATION",
        "blocking_reasons": latest.blocking_reasons if latest else ["MISSING_VERIFIED_CVINTRA"],
        "calculated_shown_as_approved": False,
        "study_mutated": False,
        "actions": ["Review calculation", "Select controlling scenario"],
        "latest_calculation_id": latest.id if latest else None,
    }
