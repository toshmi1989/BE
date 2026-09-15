"""Build Protocol Assembly `ctx` from Workspace stores (not Legacy Project ORM).

Content authority: Canonical snapshot facts + VERIFIED evidence + APPROVED decisions /
ACCEPTED sample size / APPROVED statistics. Never Golden DOCX, never Legacy Project rows.
"""

from __future__ import annotations

from typing import Any

from app.domain.decision_store import get_context, list_decisions
from app.domain.display_value_registry import resolve_display
from app.domain.protocol_template_registry import study_is_bosutinib_sample
from app.domain.sample_size_store import latest_accepted_calculation
from app.domain.statistics_store import latest_approved_plan
from app.domain.study_workspace import aggregate_conflicts, find_study_package


def _fact(facts: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in facts and facts[k] not in (None, "", []):
            return facts[k]
    return default


def _candidate_map(package: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if package is None:
        return out
    for c in package.candidates or []:
        d = c.to_dict() if hasattr(c, "to_dict") else dict(c)
        fp = str(d.get("field_path") or "")
        if not fp:
            continue
        status = str(d.get("status") or d.get("verification_status") or "").upper()
        # Prefer verified / selected; otherwise keep first
        if fp not in out or status in {"VERIFIED", "SELECTED", "APPROVED"}:
            out[fp] = d.get("value")
    return out


def _approved_domains(study_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for d in list_decisions(study_id):
        if str(d.status).upper() != "APPROVED":
            continue
        out[str(d.domain)] = {
            "selected_option": d.selected_option,
            "recommendation": d.recommendation.to_dict() if d.recommendation else None,
            "id": d.id,
        }
    return out


def build_workspace_assembly_context(
    study_id: str,
    *,
    package_id: str | None = None,
    snapshot_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the dict shape expected by `assemble_protocol` / `render_protocol_docx`."""
    pkg = find_study_package(study_id, package_id)
    ctx_obj = get_context(study_id, package_id=package_id) or get_context(study_id)
    facts = dict(getattr(ctx_obj, "structured_facts", None) or {})
    fact_sources = dict(getattr(ctx_obj, "fact_sources", None) or {})
    cand = _candidate_map(pkg)
    # Snapshot candidates overlay when present (immutable package cut)
    if snapshot_payload:
        for c in snapshot_payload.get("candidates") or []:
            if not isinstance(c, dict):
                continue
            fp = str(c.get("field_path") or "")
            if fp and c.get("value") is not None:
                cand.setdefault(fp, c.get("value"))

    def pick(*keys: str, default: Any = None) -> Any:
        for k in keys:
            if k in facts and facts[k] not in (None, "", []):
                return facts[k]
            if k in cand and cand[k] not in (None, "", []):
                return cand[k]
        return default

    protocol_number = pick(
        "study.protocol_number",
        "protocol.number",
        "protocol_number",
        default=study_id,
    )
    title = pick("study.title", "protocol.title", default=f"Протокол БЭ {protocol_number}")

    test_name = pick(
        "test_product.name",
        "test_product.trade_name",
        "product.trade_name",
        "product.name",
        # UPDCB package carries INN/substance identity when trade name is absent
        "test_product.active_substance",
        "bioanalysis.analyte",
    )
    test_inn = pick(
        "test_product.inn",
        "product.inn",
        "analyte.name",
        "bioanalysis.analyte",
        "test_product.active_substance",
        "reference_product.active_substance",
    )
    test_dose = pick("test_product.dose", "product.dosage", "test_product.dosage")
    ref_name = pick(
        "reference_product.name",
        "reference_product.trade_name",
    )
    ref_inn = pick(
        "reference_product.inn",
        "reference_product.active_substance",
        default=test_inn,
    )
    ref_dose = pick("reference_product.dose", "reference_product.dosage")

    design_type = pick("design.type", "design.crossover")
    if design_type is True or str(design_type).lower() in {"true", "1", "crossover"}:
        design_type = "CROSSOVER_2X2"
    if not design_type:
        design_type = "CROSSOVER_2X2"
    food_cond = pick("food.condition", "design.food_condition", default="FED")
    if str(food_cond).upper() in {"FED", "FASTING", "FASTING_AND_FED"}:
        food_code = str(food_cond).upper()
    else:
        food_code = "FED"

    periods = pick("design.periods", default=2)
    try:
        periods = int(periods)
    except (TypeError, ValueError):
        periods = 2

    evaluable = pick("subjects.evaluable_n", "subjects.target_evaluable_n")
    randomized = pick("subjects.randomized_n", "subjects.planned_randomized_n")
    screened = pick("subjects.screened_n", "subjects.planned_screened_n")

    ss = latest_accepted_calculation(study_id)
    if ss is not None:
        evaluable = evaluable or ss.required_n or ss.randomized_n
        randomized = randomized or ss.randomized_n
        sample_size = {
            "id": ss.id,
            "evaluable_n": ss.required_n or ss.randomized_n,
            "randomized_n": ss.randomized_n,
            "dropout_pct": ss.dropout_percent,
            "cv_used": ss.cv_value,
            "parameter": ss.controlling_parameter or ss.parameter,
            "power": ss.power or ss.target_power,
            "alpha": ss.alpha,
            "expected_ratio": ss.expected_ratio,
            "status": ss.status,
            "method": ss.method,
        }
        cv_selection = {
            "selected_cv": ss.cv_value,
            "parameter": ss.controlling_parameter or ss.parameter,
            "selection_method": "ACCEPTED_CALCULATION",
            "source_claim_id": None,
        }
    else:
        sample_size = {}
        cv_selection = {}

    st = latest_approved_plan(study_id)
    pk_parameters: list[dict[str, Any]] = []
    analytes: list[dict[str, Any]] = []
    statistical_config: dict[str, Any] = {}
    if st is not None:
        primary = [p.parameter for p in st.parameters if p.role == "PRIMARY_BE"]
        secondary = [p.parameter for p in st.parameters if p.role == "SECONDARY_PK"]
        for p in st.parameters:
            pk_parameters.append(
                {
                    "parameter_code": p.parameter,
                    "role": p.role,
                    "transformation": p.transformation,
                    "model": p.model,
                }
            )
        statistical_config = {
            "id": st.id,
            "status": st.status,
            "version": st.version,
            "analysis_population": st.analysis_population,
            "confidence_level": st.confidence_level,
            "model": st.model,
            "primary_parameters": primary,
            "secondary_parameters": secondary,
            "acceptance_interval": (
                {
                    "lower": st.acceptance_interval.lower_bound,
                    "upper": st.acceptance_interval.upper_bound,
                }
                if st.acceptance_interval
                else None
            ),
        }
    else:
        raw_pk = pick("pk.parameters", "pk.primary_parameters", default=[])
        if isinstance(raw_pk, str):
            raw_pk = [x.strip() for x in raw_pk.split(",") if x.strip()]
        for code in raw_pk or []:
            pk_parameters.append({"parameter_code": str(code)})

    analyte_name = test_inn or pick("analyte.name", "pk.analyte")
    if analyte_name:
        tmax = pick("pk.expected_tmax", "pk.Tmax", default=getattr(ctx_obj, "tmax", None))
        thalf = pick("pk.expected_t_half", "pk.t_half", default=getattr(ctx_obj, "half_life", None))
        analytes = [
            {
                "id": "analyte-1",
                "name": str(analyte_name),
                "type": "PARENT",
                "tmax_min": tmax,
                "tmax_max": tmax,
                "tmax_unit": "h",
                "half_life_min": thalf,
                "half_life_max": thalf,
            }
        ]

    washout_val = pick("washout.duration", "washout.days", "washout.selected_value")
    washout = (
        {"selected_value": washout_val, "unit": pick("washout.unit", default="day")}
        if washout_val is not None
        else {}
    )
    obs = pick("observation.duration", "sampling.observation_h")
    observation = (
        {"selected_duration": obs, "selected_unit": "h"} if obs is not None else {}
    )

    sampling_raw = pick("sampling.schedule", "sampling.points")
    points: list[dict[str, Any]] = []
    if isinstance(sampling_raw, list):
        for p in sampling_raw:
            if isinstance(p, dict):
                points.append(p)
            else:
                try:
                    points.append({"time_h": float(p), "reason": ""})
                except (TypeError, ValueError):
                    pass
    sampling = {"points": points} if points else {}

    approved = _approved_domains(study_id)
    product = {
        "trade_name": test_name,
        "inn": test_inn,
        "dosage": str(test_dose) if test_dose is not None else None,
        "dosage_form": pick(
            "test_product.dosage_form",
            "product.dosage_form",
            "test_product.form",
        ),
        "manufacturer": pick("test_product.manufacturer", "product.manufacturer"),
        "composition": pick("test_product.composition", "product.composition"),
        "route": pick("test_product.route", "product.route"),
        "storage_conditions": pick(
            "test_product.storage",
            "test_product.storage_conditions",
            "product.storage_conditions",
        ),
        "manufacturer_country": pick(
            "test_product.manufacturer_country",
            "product.manufacturer_country",
        ),
        "registration_number": pick(
            "test_product.registration_number",
            "product.registration_number",
        ),
        "shelf_life": pick("test_product.shelf_life", "product.shelf_life"),
        "batch": pick("test_product.batch", "product.batch"),
        "source_ids": [],
    }
    reference_product = {
        "trade_name": ref_name,
        "inn": ref_inn,
        "dosage": str(ref_dose) if ref_dose is not None else None,
        "dosage_form": pick(
            "reference_product.dosage_form",
            "reference.dosage_form",
        ),
        "manufacturer": pick(
            "reference_product.manufacturer",
            "reference.manufacturer",
        ),
        "composition": pick(
            "reference_product.composition",
            "reference.composition",
        ),
        "route": pick("reference_product.route", "reference.route"),
        "storage_conditions": pick(
            "reference_product.storage",
            "reference_product.storage_conditions",
        ),
        "manufacturer_country": pick(
            "reference_product.manufacturer_country",
            "reference.manufacturer_country",
        ),
        "registration_number": pick(
            "reference_product.registration_number",
            "reference.registration_number",
        ),
        "shelf_life": pick("reference_product.shelf_life", "reference.shelf_life"),
        "batch": pick("reference_product.batch", "reference.batch"),
        "purchased_status": pick(
            "reference_product.purchased_status",
            default="UNKNOWN",
        ),
        "source_ids": [],
    }

    # Dose conflict must stay visible — do not pick a side
    conflicts = aggregate_conflicts(study_id, package_id=package_id)
    open_dose = [
        c
        for c in conflicts
        if c.get("status") == "OPEN"
        and c.get("field") == "reference_product.dose"
        and c.get("severity") == "CRITICAL"
    ]
    if open_dose:
        reference_product["dosage"] = None
        reference_product["dose_conflict"] = True
        reference_product["conflict_values"] = [
            open_dose[0].get("value_a"),
            open_dose[0].get("value_b"),
        ]

    sponsor_name = pick("sponsor.name", "sponsor.legal_name")
    sponsor = {"name": sponsor_name, "legal_name": sponsor_name} if sponsor_name else {}

    ctx: dict[str, Any] = {
        "project_id": study_id,
        "study_id": study_id,
        "workspace": True,
        "study": {
            "protocol_number": str(protocol_number),
            "title": str(title),
            "version": pick("study.version", default="1.0"),
            "version_date": pick("study.version_date", "protocol.date"),
        },
        "product": product,
        "reference_product": reference_product,
        "design": {
            "type": design_type,
            "periods": periods,
            "sequences": [["T", "R"], ["R", "T"]],
            "treatments": ["T", "R"],
            "food_condition": food_code,
            "source_ids": [],
            "display": resolve_display(str(design_type), context="design_long"),
        },
        "food": {
            "condition": food_code,
            "meal_type": pick("food.meal_type", default="HIGH_CALORIE"),
            "calorie_target": pick("food.calorie_target"),
            "display": resolve_display(food_code, context="food"),
        },
        "subjects": {
            "target_evaluable_n": evaluable,
            "planned_randomized_n": randomized,
            "planned_screened_n": screened,
        },
        "eligibility": {"inclusion": [], "non_inclusion": [], "exclusion": []},
        "bioanalysis_plan": pick("bioanalysis", "bioanalysis_plan", default={}) or {},
        "safety_plan": pick("safety", "safety_plan", default={}) or {},
        "analytes": analytes,
        "pk_parameters": pk_parameters,
        "washout": washout,
        "observation": observation,
        "sampling": sampling,
        "sample_size": sample_size,
        "cv_selection": cv_selection,
        "cv_studies": [],
        "sources": [],
        "blood_volume": {},
        "statistical_config": statistical_config,
        "evidence_summary": {"count": 0, "workspace": True},
        "sponsor": sponsor,
        "organizations": [],
        "persons": [],
        "approved_decisions": approved,
        "fact_sources": fact_sources,
        "structured_facts": facts,
        "is_bosutinib_template_sample": study_is_bosutinib_sample(product),
    }
    return ctx


def workspace_docx_blockers(ctx: dict[str, Any], *, study_id: str) -> list[dict[str, str]]:
    """Required-content gates before calling the template renderer."""
    blockers: list[dict[str, str]] = []
    study = ctx.get("study") or {}
    product = ctx.get("product") or {}
    if not study.get("protocol_number"):
        blockers.append(
            {
                "code": "MISSING_PROTOCOL_NUMBER",
                "field": "study.protocol_number",
                "section": "1.1 / header",
                "reason": "Нет номера протокола в canonical/workspace facts",
            }
        )
    if not (product.get("trade_name") or product.get("inn")):
        blockers.append(
            {
                "code": "MISSING_TEST_PRODUCT",
                "field": "test_product",
                "section": "T05 / header",
                "reason": "Нет исследуемого препарата — нельзя оставить Бозутиниб из шаблона",
            }
        )
    ref = ctx.get("reference_product") or {}
    if ref.get("dose_conflict"):
        blockers.append(
            {
                "code": "UNRESOLVED_REFERENCE_DOSE_CONFLICT",
                "field": "reference_product.dose",
                "section": "T06 / dosing",
                "reason": "Конфликт дозы препарата сравнения не разрешён экспертом",
            }
        )
    conflicts = aggregate_conflicts(study_id)
    if any(c.get("status") == "OPEN" and c.get("severity") == "CRITICAL" for c in conflicts):
        if not any(b["code"] == "UNRESOLVED_REFERENCE_DOSE_CONFLICT" for b in blockers):
            blockers.append(
                {
                    "code": "UNRESOLVED_CRITICAL_CONFLICT",
                    "field": "conflicts",
                    "section": "preflight",
                    "reason": "Открыт критический конфликт входных данных",
                }
            )
    return blockers
