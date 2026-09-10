"""Phase 29 — unified knowledge-gap surface.

A missing input gates only the steps that consume it. Nothing is invented, and
no value reaches an engine before an expert verifies or enters it.
"""

from __future__ import annotations

import pytest

from app.domain.decision_engine import recompute_from_package
from app.domain.decision_store import (
    clear_decision_store,
    get_context,
    list_decisions,
    put_context,
    put_decisions,
)
from app.domain.research_evidence_store import clear_research_evidence_store
from app.domain.sample_size_engine import calculate_sample_size_authoritative
from app.domain.study_input_pipeline import load_real_fixture_package
from app.domain.workspace_gaps import (
    EXPERT_DECISION,
    MANUAL,
    RESEARCH,
    collect_study_gaps,
    resolve_gap_manually,
)

STUDY = "GAPS-TEST-STUDY"


@pytest.fixture(autouse=True)
def _clean():
    clear_decision_store()
    clear_research_evidence_store()
    yield
    clear_decision_store()
    clear_research_evidence_store()


@pytest.fixture
def study():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.study_id = STUDY
    ctx, decisions = recompute_from_package(pkg, study_id=STUDY)
    put_decisions(STUDY, decisions, package_id=pkg.package_id)
    put_context(STUDY, ctx, package_id=pkg.package_id)
    return pkg


def _gap(panel, code):
    return next((g for g in panel["gaps"] if g["code"] == code), None)


def test_untouched_study_reports_no_gaps():
    panel = collect_study_gaps("STUDY-WITHOUT-DOCUMENTS")
    assert panel["gaps"] == []
    assert panel["counts"]["total"] == 0


def test_panel_lists_missing_inputs_without_freezing_protocol(study):
    panel = collect_study_gaps(STUDY)
    assert panel["protocol_frozen"] is False
    assert panel["counts"]["total"] >= 1

    tmax = _gap(panel, "MISSING_TMAX_FOR_SAMPLING")
    assert tmax is not None
    assert tmax["status"] == "OPEN"
    assert tmax["blocks"] == ["Sampling"]
    assert RESEARCH in tmax["resolution"] and MANUAL in tmax["resolution"]
    assert tmax["sources_hint"]


def test_every_gap_names_a_way_to_close_it(study):
    for gap in collect_study_gaps(STUDY)["gaps"]:
        assert gap["resolution"], gap["code"]
        assert gap["title"] and gap["why"]
        assert gap["blocks"], gap["code"]


def test_manual_tmax_entry_unblocks_only_sampling(study):
    result = resolve_gap_manually(
        STUDY,
        "MISSING_TMAX_FOR_SAMPLING",
        value="2–4",
        rationale="SmPC оригинального препарата: Tmax 2–4 ч",
        actor="writer@example.com",
    )
    assert result["auto_approved"] is False
    assert "SAMPLING" in result["recomputed_domains"]

    ctx = get_context(STUDY)
    assert ctx.tmax == "2–4"
    assert ctx.fact_statuses["pk.expected_tmax"] == "VERIFIED"
    assert ctx.fact_sources["pk.expected_tmax"] == "EXPERT_INPUT"

    sampling = next(d for d in list_decisions(STUDY) if d.domain == "SAMPLING")
    codes = {str(g.get("code")) for g in sampling.knowledge_gaps}
    assert "MISSING_TMAX_FOR_SAMPLING" not in codes

    assert _gap(collect_study_gaps(STUDY), "MISSING_TMAX_FOR_SAMPLING") is None


def test_manual_entry_requires_rationale(study):
    with pytest.raises(ValueError, match="Обоснование"):
        resolve_gap_manually(
            STUDY,
            "MISSING_TMAX_FOR_SAMPLING",
            value="2–4",
            rationale="  ",
            actor="writer",
        )


def test_half_life_manual_entry_must_be_numeric(study):
    with pytest.raises(ValueError, match="числом"):
        resolve_gap_manually(
            STUDY,
            "MISSING_HALF_LIFE_FOR_WASHOUT",
            value="около девяти часов",
            rationale="из литературы",
            actor="writer",
        )


def test_cvintra_needs_pk_parameter_then_feeds_sample_size(study):
    with pytest.raises(ValueError, match="PK-параметр"):
        resolve_gap_manually(
            STUDY,
            "MISSING_CVINTRA",
            value=28,
            rationale="Публикация по BE",
            actor="writer",
        )

    resolve_gap_manually(
        STUDY,
        "MISSING_CVINTRA",
        value=28,
        rationale="Within-subject CV Cmax 28% из публикации BE",
        actor="writer",
        pk_parameter="Cmax",
    )

    rec = calculate_sample_size_authoritative(
        study_id=STUDY,
        design="STANDARD_2X2_CROSSOVER",
        parameters=["Cmax"],
        expected_ratio=0.95,
        expected_ratio_source="EXPERT_INPUT",
        power=0.8,
        power_source="EXPERT_INPUT",
        alpha=0.05,
        alpha_source="EXPERT_INPUT",
        be_lower=0.8,
        be_upper=1.25,
        be_limits_source="EXPLICIT_CONFIGURATION",
        dropout_percent=10.0,
        dropout_source="EXPERT_INPUT",
        inflation_method="DIVIDE_BY_RETAINMENT_RATE",
    )
    assert "MISSING_VERIFIED_CVINTRA" not in rec.blocking_reasons
    assert "CV_PROPOSED_NOT_ALLOWED" not in rec.blocking_reasons


def test_only_a_stated_meal_composition_becomes_a_proposal(study):
    """A source that just says "high-calorie breakfast" gives the engine nothing."""
    from app.domain.research_evidence_engine import create_tasks_from_gaps, run_research_task, verify_claim
    from app.domain.research_provider import ProviderHit, ResearchProvider
    from app.domain.workspace_gaps import apply_verified_evidence

    class _Provider(ResearchProvider):
        kind = "WEB"

        def __init__(self, text: str) -> None:
            self.text = text

        def search(self, query, *, query_type=None):
            return [
                ProviderHit(
                    title="Fed BE study conditions",
                    locator="https://example.test/meal",
                    source_type="PUBLICATION",
                    text=self.text,
                )
            ]

    def _run(text: str):
        task = create_tasks_from_gaps(
            STUDY, [{"code": "MISSING_MEAL_COMPOSITION", "title": "meal"}]
        )[0]
        run_research_task(task.id, provider=_Provider(text), register_sources=False)
        return _gap(collect_study_gaps(STUDY), "MISSING_MEAL_COMPOSITION")

    vague = _run("Subjects received a high-calorie breakfast before dosing.")
    assert vague is not None
    assert vague["proposals"] == []

    stated = _run(
        "Subjects received a high-calorie breakfast of approximately 950 kcal with 55% fat."
    )
    assert stated["status"] == "PROPOSED"
    proposal = next(p for p in stated["proposals"] if p["value"] == 950)

    verify_claim(
        proposal["claim_id"],
        reviewer="writer@example.com",
        applicability="DIRECT",
        applicability_reason="Условия применимы к этому исследованию",
    )
    applied = apply_verified_evidence(STUDY)
    assert "food.calorie_target" in applied["applied_fields"]
    assert get_context(STUDY).structured_facts["food.calorie_target"] == 950
    assert _gap(collect_study_gaps(STUDY), "MISSING_MEAL_COMPOSITION") is None


def test_statistics_gaps_are_expert_decisions_not_manual_values(study):
    for code in ("MISSING_PRIMARY_BE_SELECTION", "MISSING_ANALYSIS_POPULATION_RULE"):
        with pytest.raises(ValueError, match="Решения"):
            resolve_gap_manually(
                STUDY,
                code,
                value="PER_PROTOCOL",
                rationale="решил так",
                actor="writer",
            )


def test_statistics_gaps_surface_after_plan_exists(study):
    from app.domain.statistics_engine import recompute_statistics_plan

    ctx = get_context(STUDY)
    recompute_statistics_plan(
        study_id=STUDY,
        context=ctx.to_dict(),
        design="STANDARD_2X2_CROSSOVER",
        parameters=["Cmax", "AUC0-72"],
    )
    panel = collect_study_gaps(STUDY)
    population = _gap(panel, "MISSING_ANALYSIS_POPULATION_RULE")
    assert population is not None
    assert population["resolution"] == [EXPERT_DECISION]
    assert population["blocks"] == ["Statistics"]
