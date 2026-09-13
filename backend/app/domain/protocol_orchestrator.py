"""The protocol orchestrator — Phase 30.

One entry point from uploaded documents to a protocol. It interprets the
package, fills what the regulation prescribes, runs every engine whose inputs
are present, checks that the numbers agree with each other, and assembles the
document.

The orchestrator never approves anything on its own initiative. When the writer
asks for a final protocol, their name is carried through to the existing review
machinery and recorded — the same audit trail as pressing Approve by hand,
minus the hunt for the button.

A missing input never stops the pipeline. Steps that consume it report
themselves as not computed, and the draft says so in the text.
"""

from __future__ import annotations

from typing import Any

from app.domain import sample_size_review, statistics_review
from app.domain.decision_store import get_context
from app.domain.exceptions import ValidationError
from app.domain.protocol_defaults import DEFAULTS
from app.domain.protocol_input_sheet import (
    build_input_sheet,
    fill_regulatory_defaults,
    refresh_context_from_package,
)
from app.domain.sample_size_engine import calculate_sample_size_authoritative
from app.domain.sample_size_store import list_calculations
from app.domain.statistics_engine import recompute_statistics_plan
from app.domain.statistics_store import latest_plan as latest_statistics_plan
from app.domain.study_workspace import (
    append_audit,
    find_study_package,
    put_protocol_draft_version,
)

AI_ACTORS: frozenset[str] = frozenset({"AI", "MOCKAI", "SYSTEM_AI", "WORKFLOW", "SYSTEM"})


def _require_human(actor: str) -> str:
    name = str(actor or "").strip()
    if not name or name.upper() in AI_ACTORS:
        raise ValidationError(
            "Требуется имя эксперта — платформа не утверждает протокол от своего имени",
            field="actor",
        )
    return name


def interpret(
    db: Any,
    study_id: str,
    *,
    actor: str,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Read the uploaded documents and fill what the regulation already fixes."""
    package = find_study_package(study_id, package_id)
    if package is None or not package.documents:
        raise ValidationError(
            "Нет загруженных документов — загрузите файлы исследования",
            field="documents",
        )

    refresh_context_from_package(study_id, package)
    defaults = fill_regulatory_defaults(study_id, package_id=package.package_id)

    append_audit(
        study_id,
        event="PACKAGE_INTERPRETED",
        who=actor,
        what=package.package_id,
        reason="Интерпретация загруженных документов",
        new_value={
            "candidates": len(package.candidates),
            "regulatory_defaults": defaults["applied_fields"],
        },
    )

    sheet = build_input_sheet(study_id, package_id=package.package_id)
    return {
        "study_id": study_id,
        "package_id": package.package_id,
        "documents": len(package.documents),
        "extracted_values": len(package.candidates),
        "regulatory_defaults_applied": defaults["applied_fields"],
        "sheet": sheet,
        "study_mutated": False,
    }


def _statistics_context(study_id: str, package_id: str | None) -> dict[str, Any]:
    ctx = get_context(study_id, package_id=package_id)
    facts = dict(getattr(ctx, "structured_facts", {}) or {})
    return {
        "structured_facts": facts,
        "fact_sources": dict(getattr(ctx, "fact_sources", {}) or {}),
        "design": "STANDARD_2X2_CROSSOVER" if facts.get("design.crossover") else None,
        "pk_parameter_list": list(facts.get("pk.parameters") or []),
    }


def compute_engines(
    study_id: str,
    *,
    actor: str,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Run the engines on whatever the sheet already holds.

    Regulatory constants come from the defaults registry with their real
    provenance, so nothing is attributed to an expert who never typed it.
    """
    from app.domain.protocol_defaults import sample_size_defaults, statistics_plan_defaults

    ctx_dict = _statistics_context(study_id, package_id)
    facts = ctx_dict["structured_facts"]

    sample_size: dict[str, Any] = {"status": "NOT_COMPUTED", "blocking": [], "n": None}
    try:
        primary = list(facts.get("pk.primary_parameters") or DEFAULTS["pk.primary_parameters"].value)
        record = calculate_sample_size_authoritative(
            study_id=study_id,
            design="STANDARD_2X2_CROSSOVER",
            parameters=[p for p in primary if p in {"Cmax", "AUC", "AUC0-t", "AUC0-inf"}] or ["Cmax"],
            context=ctx_dict,
            created_by=actor,
            **sample_size_defaults(),
        )
        sample_size = {
            "status": record.status,
            "blocking": list(record.blocking_reasons or []),
            "n": record.randomized_n,
            "required_n": record.required_n,
            "calculation_id": record.id,
        }
    except Exception as exc:  # engine failure must not hide the rest of the sheet
        sample_size = {"status": "ERROR", "blocking": [str(exc)], "n": None}

    statistics: dict[str, Any] = {"status": "NOT_COMPUTED", "blocking": []}
    try:
        plan = recompute_statistics_plan(
            study_id=study_id,
            context=ctx_dict,
            created_by=actor,
            **statistics_plan_defaults(),
        )
        statistics = {
            "status": plan.status,
            "blocking": list(plan.blocking_reasons or []),
            "plan_id": plan.id,
        }
    except Exception as exc:
        statistics = {"status": "ERROR", "blocking": [str(exc)]}

    return {"sample_size": sample_size, "statistics": statistics}


def review_coherence(
    study_id: str,
    *,
    package_id: str | None = None,
) -> list[dict[str, Any]]:
    """Check that the numbers agree with each other and with the rules.

    This is what keeps a generated protocol from reading like a form-fill: it
    catches a washout shorter than the rule allows, a subject count that does
    not match the calculation, fed conditions with no meal described.
    """
    ctx = get_context(study_id, package_id=package_id)
    facts = dict(getattr(ctx, "structured_facts", {}) or {})
    findings: list[dict[str, Any]] = []

    def note(code: str, message: str, severity: str = "WARNING") -> None:
        findings.append({"code": code, "message": message, "severity": severity})

    half_life = facts.get("pk.expected_t_half") or facts.get("pk.t_half")
    washout_days = facts.get("washout.duration")
    if half_life and washout_days:
        try:
            required_hours = float(half_life) * float(DEFAULTS["washout.min_half_lives"].value)
            actual_hours = float(washout_days) * 24.0
            if actual_hours < required_hours:
                note(
                    "WASHOUT_SHORTER_THAN_RULE",
                    f"Период отмывки {washout_days} сут короче требуемых "
                    f"{required_hours / 24:.1f} сут (5 × t½ = {half_life} ч).",
                )
        except (TypeError, ValueError):
            pass

    calcs = list_calculations(study_id)
    latest = calcs[-1] if calcs else None
    protocol_n = facts.get("subjects.randomized_n")
    if latest and latest.randomized_n and protocol_n:
        try:
            planned, calculated = int(protocol_n), int(latest.randomized_n)
            if planned < calculated:
                note(
                    "SUBJECTS_BELOW_CALCULATION",
                    f"В документах {planned} субъектов, расчёт требует {calculated}. "
                    "Протокол должен объяснить разницу.",
                )
            elif planned > calculated:
                note(
                    "SUBJECTS_ABOVE_CALCULATION",
                    f"В документах {planned} субъектов при расчётных {calculated}. "
                    "Запас допустим, но в протоколе его нужно обосновать.",
                    severity="INFO",
                )
        except (TypeError, ValueError):
            pass

    condition = str(facts.get("food.condition") or "").upper()
    if condition in {"FED", "BOTH"} and not facts.get("food.calorie_target"):
        note(
            "FED_WITHOUT_MEAL_COMPOSITION",
            "Заявлен приём после еды, но состав стандартного завтрака не задан.",
        )

    if half_life and facts.get("sampling.times"):
        note(
            "SAMPLING_COVERAGE_UNVERIFIED",
            "Схема отбора проб задана вручную — проверьте покрытие терминальной фазы "
            "(не менее 3 × t½).",
            severity="INFO",
        )

    findings.extend(_regulatory_divergences(facts))

    plan = latest_statistics_plan(study_id)
    if plan and plan.blocking_reasons:
        note(
            "STATISTICS_INCOMPLETE",
            "Статистический план рассчитан не полностью — часть вводных ещё не задана.",
        )

    return findings


# Regulated values stated in a document are compared against the rule itself,
# so a synopsis carrying a 95% interval does not quietly reach the protocol.
_COMPARABLE_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("statistics.confidence_interval", "90"),
    ("statistics.acceptance_interval", "80"),
    ("statistics.transformation", "LOG"),
)


def _regulatory_divergences(facts: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path, expected_token in _COMPARABLE_DEFAULTS:
        stated = facts.get(path)
        if stated is None:
            continue
        text = str(stated).upper().replace(",", ".")
        if expected_token.upper() in text:
            continue
        spec = DEFAULTS.get(path)
        out.append(
            {
                "code": "DIVERGES_FROM_REGULATION",
                "severity": "WARNING",
                "message": (
                    f"В документах «{spec.title if spec else path}» указано «{stated}», "
                    f"что расходится с нормативом. {spec.citation if spec else ''}".strip()
                ),
            }
        )
    return out


def run(
    db: Any,
    study_id: str,
    *,
    actor: str,
    package_id: str | None = None,
    finalize: bool = False,
) -> dict[str, Any]:
    """Full pass: interpret → compute → check → draft.

    `finalize` carries the writer's decision to approve the computed plans. It
    only takes effect when every required row of the sheet is filled.
    """
    name = _require_human(actor)
    interpreted = interpret(db, study_id, actor=name, package_id=package_id)
    pkg_id = interpreted["package_id"]

    engines = compute_engines(study_id, actor=name, package_id=pkg_id)
    sheet = build_input_sheet(study_id, package_id=pkg_id)
    findings = review_coherence(study_id, package_id=pkg_id)

    approvals: list[dict[str, Any]] = []
    if finalize and sheet["can_finalize"]:
        approvals = _approve_computed_plans(study_id, engines, actor=name)

    draft = put_protocol_draft_version(
        study_id,
        status="READY_FOR_FINAL" if (finalize and sheet["can_finalize"]) else "PROTOCOL_DRAFT",
        created_by=name,
        based_on={
            "snapshot": None,
            "decisions": [],
            "evidence": pkg_id,
            "statistics": engines["statistics"].get("plan_id"),
            "sample_size": engines["sample_size"].get("calculation_id"),
        },
        sections_summary=["assembled_by_orchestrator"],
    )

    append_audit(
        study_id,
        event="ORCHESTRATOR_RUN",
        who=name,
        what=draft["protocol_id"],
        reason="Сборка протокола оркестратором",
        new_value={
            "required_ready": sheet["counts"]["required_ready"],
            "required": sheet["counts"]["required"],
            "finalized": bool(approvals),
        },
    )

    return {
        "study_id": study_id,
        "package_id": pkg_id,
        "sheet": sheet,
        "engines": engines,
        "coherence": findings,
        "approvals": approvals,
        "protocol_draft": draft,
        "can_draft": True,
        "can_finalize": sheet["can_finalize"],
        "study_mutated": False,
    }


def _approve_computed_plans(
    study_id: str,
    engines: dict[str, Any],
    *,
    actor: str,
) -> list[dict[str, Any]]:
    """Record the writer's approval of the computed plans, as themselves."""
    out: list[dict[str, Any]] = []

    plan = latest_statistics_plan(study_id)
    if plan and plan.status != "APPROVED":
        try:
            statistics_review.approve_plan(
                plan.id,
                reviewer=actor,
                comment="Утверждено при формировании финального протокола",
            )
            out.append({"what": "statistics", "id": plan.id, "status": "APPROVED"})
        except ValidationError as exc:
            out.append({"what": "statistics", "id": plan.id, "error": str(exc)})

    calcs = list_calculations(study_id)
    latest = calcs[-1] if calcs else None
    if latest and latest.status not in {"ACCEPTED", "REJECTED"}:
        try:
            sample_size_review.approve_calculation(
                latest.id,
                reviewer=actor,
                decision="ACCEPT_CALCULATION",
                comment="Утверждено при формировании финального протокола",
            )
            out.append({"what": "sample_size", "id": latest.id, "status": "ACCEPTED"})
        except ValidationError as exc:
            out.append({"what": "sample_size", "id": latest.id, "error": str(exc)})

    return out
