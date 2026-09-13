"""Phase 30 — the input sheet and the orchestrator that has to reach the end.

The behaviour these tests protect is the one the platform kept getting wrong: a
missing value must never send the writer around a circle of screens, and a
value they already supplied must never be asked for twice.
"""

from __future__ import annotations

import pytest

from app.domain import protocol_orchestrator as orch
from app.domain.exceptions import ValidationError
from app.domain.protocol_defaults import (
    CONVENTION,
    DEFAULTS,
    REGULATORY,
    sample_size_defaults,
    statistics_plan_defaults,
)
from app.domain.protocol_input_sheet import (
    CONFLICT,
    FROM_DOCUMENT,
    FROM_EXPERT,
    FROM_REGULATION,
    MISSING,
    SHEET_BY_KEY,
    build_input_sheet,
    fill_row,
    resolve_conflict_row,
)
from app.domain.study_input_pipeline import load_real_fixture_package
from app.domain.study_input_store import put_package

STUDY = "UPDCB-02-BE-2026"
WRITER = "Мед. писатель Иванова"

# Everything the golden package cannot supply on its own
MANUAL_FILLS: tuple[tuple[str, str, dict], ...] = (
    ("study.title", "Исследование биоэквивалентности упадацитиниба 15 мг", {}),
    ("test_product.name", "Упадацитиниб-ПРОМОМЕД", {}),
    ("pk.expected_tmax", "3", {}),
    ("pk.expected_t_half", "10", {}),
    ("cv_intra", "22", {"pk_parameter": "Cmax"}),
)


@pytest.fixture()
def study() -> str:
    from app.domain.workspace_authority import invalidate_study_cache

    # The in-memory stores are process-global; one test must not inherit another's
    invalidate_study_cache(STUDY)
    package = load_real_fixture_package()
    package.study_id = STUDY
    put_package(package)
    orch.run(None, STUDY, actor=WRITER)
    return STUDY


def _row(study_id: str, key: str) -> dict:
    sheet = build_input_sheet(study_id)
    return next(r for r in sheet["rows"] if r["key"] == key)


def _complete(study_id: str) -> None:
    for key, value, extra in MANUAL_FILLS:
        fill_row(study_id, key, value=value, actor=WRITER, rationale="Проверка", **extra)
    sheet = build_input_sheet(study_id)
    for row in sheet["rows"]:
        if row["status"] == CONFLICT and row["conflict_choices"]:
            resolve_conflict_row(
                study_id,
                row["key"],
                value=row["conflict_choices"][0]["value"],
                actor=WRITER,
                rationale="Подтверждено по документации препарата сравнения",
            )


# --- the sheet reads what the documents gave --------------------------------


def test_sheet_lists_every_input_once(study: str):
    sheet = build_input_sheet(study)
    keys = [r["key"] for r in sheet["rows"]]
    assert len(keys) == len(set(keys)), "строка ведомости не должна повторяться"
    assert sheet["counts"]["total"] == len(SHEET_BY_KEY)
    assert {g["id"] for g in sheet["groups"]} == {r["group"] for r in sheet["rows"]}


def test_document_values_are_ready_without_extra_confirmation(study: str):
    """A value from the writer's own file is supplied, not pending review."""
    row = _row(study, "sponsor.name")
    assert row["status"] == FROM_DOCUMENT
    assert row["ready"] is True
    assert build_input_sheet(study)["counts"]["needs_confirm"] == 0


def test_presence_flag_is_not_a_quantity(study: str):
    """Extraction records Tmax as a bare True; that must not look like a value."""
    row = _row(study, "pk.expected_tmax")
    assert row["status"] == MISSING
    assert row["value"] is None


def test_regulated_values_come_from_the_rules_with_a_citation(study: str):
    row = _row(study, "statistics.analysis_population")
    assert row["status"] == FROM_REGULATION
    assert row["ready"] is True
    assert "ЕАЭС" in str(row["source"])


def test_drug_specific_values_have_no_default(study: str):
    """No regulation states CVintra or Tmax, so nothing may invent them."""
    for key in ("cv_intra", "pk.expected_tmax", "pk.expected_t_half"):
        assert key not in DEFAULTS
        assert _row(study, key)["status"] == MISSING


# --- filling a row ----------------------------------------------------------


def test_expert_value_is_attributed_to_the_expert(study: str):
    fill_row(study, "pk.expected_tmax", value="3", actor=WRITER, rationale="ОХЛП")
    row = _row(study, "pk.expected_tmax")
    assert row["status"] == FROM_EXPERT
    assert row["ready"] is True
    assert float(row["value"]) == 3.0


def test_reinterpreting_documents_keeps_expert_input(study: str):
    """Re-reading the package must not wipe what a person typed."""
    fill_row(study, "cv_intra", value="22", actor=WRITER, rationale="Публикация", pk_parameter="Cmax")
    orch.run(None, study, actor=WRITER)
    assert _row(study, "cv_intra")["ready"] is True


def test_derived_row_cannot_be_typed(study: str):
    with pytest.raises(ValueError, match="рассчитывается"):
        fill_row(study, "sample_size.randomized_n", value="40", actor=WRITER)


def test_unknown_row_is_rejected(study: str):
    with pytest.raises(ValueError, match="Неизвестная строка"):
        fill_row(study, "not.a.field", value="x", actor=WRITER)


# --- conflicts are settled in the row itself --------------------------------


def test_conflicting_documents_offer_both_values(study: str):
    row = _row(study, "reference_product.dose")
    assert row["status"] == CONFLICT
    assert len(row["conflict_choices"]) == 2


def test_conflict_resolution_requires_a_reason(study: str):
    row = _row(study, "reference_product.dose")
    with pytest.raises(ValueError, match="Обоснование"):
        resolve_conflict_row(
            study,
            "reference_product.dose",
            value=row["conflict_choices"][0]["value"],
            actor=WRITER,
            rationale="",
        )


def test_conflict_choice_must_exist_in_a_document(study: str):
    with pytest.raises(ValueError, match="не встречается"):
        resolve_conflict_row(
            study,
            "reference_product.dose",
            value="999 mg",
            actor=WRITER,
            rationale="Выдуманное значение",
        )


def test_resolved_conflict_clears_the_row(study: str):
    row = _row(study, "reference_product.dose")
    chosen = row["conflict_choices"][0]["value"]
    resolve_conflict_row(
        study,
        "reference_product.dose",
        value=chosen,
        actor=WRITER,
        rationale="Подтверждено по ОХЛП",
    )
    after = _row(study, "reference_product.dose")
    assert after["status"] != CONFLICT
    assert after["ready"] is True


# --- the pipeline always reaches an end ------------------------------------


def test_a_draft_is_available_even_with_an_empty_sheet(study: str):
    out = orch.run(None, study, actor=WRITER)
    assert out["can_draft"] is True
    assert out["can_finalize"] is False
    assert out["protocol_draft"]["protocol_id"]


def test_missing_values_are_named_instead_of_blocking_everything(study: str):
    sheet = build_input_sheet(study)
    assert sheet["blocking"], "незаполненные обязательные строки должны быть перечислены"
    titles = {b["title"] for b in sheet["blocking"]}
    assert "Внутрииндивидуальная вариабельность (CVintra)" in titles
    # ...while unrelated groups stay usable
    assert _row(study, "sponsor.name")["ready"] is True


def test_completing_the_sheet_finalizes_without_visiting_other_screens(study: str):
    """The whole point: fill the sheet, press once, get a final protocol."""
    _complete(study)
    out = orch.run(None, study, actor=WRITER, finalize=True)

    assert out["can_finalize"] is True
    assert out["sheet"]["blocking"] == []
    assert out["engines"]["sample_size"]["status"] == "CALCULATED"
    assert out["engines"]["sample_size"]["n"]
    approved = {a["what"]: a.get("status") for a in out["approvals"]}
    assert approved.get("statistics") == "APPROVED"
    assert approved.get("sample_size") == "ACCEPTED"
    assert out["protocol_draft"]["status"] == "READY_FOR_FINAL"


def test_sample_size_appears_once_cvintra_is_known(study: str):
    assert _row(study, "sample_size.randomized_n")["status"] == MISSING
    _complete(study)
    orch.run(None, study, actor=WRITER)
    row = _row(study, "sample_size.randomized_n")
    assert row["ready"] is True
    assert int(row["value"]) > 0


def test_platform_never_finalizes_in_its_own_name(study: str):
    for actor in ("", "AI", "SYSTEM"):
        with pytest.raises(ValidationError, match="эксперт"):
            orch.run(None, study, actor=actor)


# --- quality checks the orchestrator runs ----------------------------------


def test_orchestrator_reports_subject_count_against_the_calculation(study: str):
    _complete(study)
    out = orch.run(None, study, actor=WRITER)  # the calculation must exist to compare
    codes = {f["code"] for f in out["coherence"]}
    assert {"SUBJECTS_ABOVE_CALCULATION", "SUBJECTS_BELOW_CALCULATION"} & codes


def test_orchestrator_flags_a_document_that_contradicts_the_rules():
    facts = {"statistics.confidence_interval": "95%"}
    findings = orch._regulatory_divergences(facts)
    assert findings and findings[0]["code"] == "DIVERGES_FROM_REGULATION"
    assert "95%" in findings[0]["message"]


def test_engine_arguments_use_the_ratio_scale_the_engines_expect():
    """80–125% is stored as a ratio; percent is wording only."""
    assert statistics_plan_defaults()["acceptance_interval"] == (0.80, 1.25)
    ss = sample_size_defaults()
    assert (ss["be_lower"], ss["be_upper"]) == (0.80, 1.25)
    assert ss["alpha"] == pytest.approx(0.05)


def test_regulatory_and_convention_defaults_are_distinguishable():
    kinds = {spec.kind for spec in DEFAULTS.values()}
    assert kinds == {REGULATORY, CONVENTION}
    # A planning assumption must not be presented as law
    assert DEFAULTS["sample_size.expected_ratio"].kind == CONVENTION
    assert DEFAULTS["statistics.acceptance_interval"].kind == REGULATORY
    assert all(spec.citation for spec in DEFAULTS.values())
