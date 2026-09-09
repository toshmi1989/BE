"""Phase 12A — technical content foundation (no medical rule finalization)."""

from __future__ import annotations

from app.domain.bioanalysis_plan import (
    BIOANALYSIS_FIELD_CLASSIFICATION,
    BioanalysisPlan,
    empty_bioanalysis_plan,
)
from app.domain.content_foundation_constants import PROCEDURE_CATEGORIES, PROCEDURE_STAGES
from app.domain.content_generator import (
    EXPERT_DEFERRED_SECTION_CODES,
    SAFE_KNOWN_SECTION_CODES,
    SafeKnownDataContentGenerator,
)
from app.domain.content_matrix import PROTOCOL_CONTENT_MATRIX, list_content_matrix, matrix_section_codes
from app.domain.content_provenance import (
    ContentProvenance,
    expert_required_provenance,
    merge_provenance_into_block,
)
from app.domain.display_value_registry import find_raw_enums_in_text
from app.domain.expert_rules import (
    EXPERT_RULE_CATALOG,
    ExpertRule,
    list_expert_rules,
    register_expert_rule_for_tests,
)
from app.domain.procedure_definition import ProcedureDefinition, validate_procedure_definition
from app.domain.procedure_schedule import (
    PROCEDURE_DEPENDENCY_GRAPH,
    compose_procedure_schedule,
)
from app.domain.protocol_assembly import assemble_protocol
from app.domain.protocol_sections import SECTION_TREE
from app.domain.safety_plan import (
    SafetyPlan,
    build_safety_procedure_view,
    empty_safety_plan,
)


def _study_ctx(**overrides):
    ctx = {
        "project_id": "p12a",
        "study": {"protocol_number": "BE-12A-001", "title": "Foundation"},
        "design": {"type": "CROSSOVER_2X2", "periods": 2, "sequences": [["T", "R"], ["R", "T"]]},
        "food": {"condition": "FED", "meal_type": "HIGH_CALORIE"},
        "subjects": {
            "target_evaluable_n": 24,
            "planned_randomized_n": 28,
            "planned_screened_n": 40,
        },
        "sample_size": {"evaluable_n": 24, "randomized_n": 28},
        "sampling": {
            "points": [
                {"time_h": 0.0, "reason": "BASELINE"},
                {"time_h": 2.0, "reason": "TMAX_CAPTURE"},
                {"time_h": 24.0, "reason": "FINAL"},
            ],
            "total_points_per_period": 3,
        },
        "observation": {"selected_duration": 24, "unit": "h"},
        "washout": {"selected_value": 7, "unit": "day", "requires_washout": True},
        "safety_plan": {
            "vital_signs": {"enabled": True},
            "AE": {"enabled": True},
            "physical_exam": {"enabled": False},
        },
        "product": {"trade_name": "T", "inn": "x", "dosage": "100 mg"},
        "reference_product": {"trade_name": "R", "inn": "x", "dosage": "100 mg"},
        "eligibility": {"inclusion": [{"number": 1, "text": "HV"}], "non_inclusion": [], "exclusion": []},
        "analytes": [{"id": "a1", "name": "x"}],
        "sources": [],
        "evidence_claims": [],
        "sponsor": {"name": "Sponsor Co"},
    }
    ctx.update(overrides)
    return ctx


def test_procedure_definition_valid() -> None:
    p = ProcedureDefinition(
        code="SAMP.P1.T0",
        name="Blood sampling t=0",
        category="SAMPLING",
        stage="PERIOD_1",
        period=1,
        relative_time_min=0.0,
    )
    assert p.id
    assert validate_procedure_definition(p) == []
    assert p.category in PROCEDURE_CATEGORIES
    assert p.stage in PROCEDURE_STAGES


def test_procedure_definition_rejects_bad_category() -> None:
    try:
        ProcedureDefinition(code="X", name="X", category="NOT_A_CAT", stage="SCREENING")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_procedure_schedule_deterministic_composition() -> None:
    ctx = _study_ctx()
    a = compose_procedure_schedule(ctx)
    b = compose_procedure_schedule(ctx)
    assert a.status == "PROPOSED"
    assert len(a.procedures) == len(b.procedures)
    codes_a = [p.code for p in a.procedures]
    codes_b = [p.code for p in b.procedures]
    assert codes_a == codes_b
    assert any(p.category == "SAMPLING" for p in a.procedures)
    assert any(p.category == "MEAL" for p in a.procedures)
    assert any(p.category == "WASHOUT" for p in a.procedures)
    assert any(p.category == "DOSING" for p in a.procedures)
    deps = {t["dependency"] for t in a.dependency_trace}
    assert "Design" in deps or "Sampling" in deps
    assert "Food" in deps
    assert "Sampling" in deps
    # No invented clinical battery for disabled physical_exam
    assert not any(p.code == "SAFETY.PHYS" for p in a.procedures)
    assert any(p.code == "SAFETY.VITALS" for p in a.procedures)


def test_procedure_schedule_fasting_omits_meal() -> None:
    sched = compose_procedure_schedule(_study_ctx(food={"condition": "FASTING"}))
    assert not any(p.category == "MEAL" for p in sched.procedures)


def test_procedure_dependency_graph_keys() -> None:
    for key in ("Design", "Food", "Sampling", "Observation", "Washout", "SafetyPlan", "SubjectPlan"):
        assert key in PROCEDURE_DEPENDENCY_GRAPH


def test_bioanalysis_plan_no_template_defaults() -> None:
    plan = empty_bioanalysis_plan()
    assert plan.matrix is None
    assert plan.lloq is None
    assert plan.analytical_method is None
    classification = plan.classify_fields()
    assert classification["matrix"] == "EXPERT_REQUIRED"
    assert classification["lloq"] == "EXPERT_REQUIRED"
    assert "matrix" in plan.unresolved_fields()
    assert BIOANALYSIS_FIELD_CLASSIFICATION["acceptance_criteria"] == "EXPERT_REQUIRED"


def test_bioanalysis_plan_user_value_classified() -> None:
    plan = BioanalysisPlan(matrix="plasma", field_sources={"matrix": "USER"})
    assert plan.classify_fields()["matrix"] == "USER"
    assert "matrix" not in plan.unresolved_fields()


def test_safety_plan_and_view() -> None:
    plan = empty_safety_plan()
    assert plan.status == "MISSING"
    assert "SAFE.T13" in plan.static_verified_refs
    ctx = _study_ctx()
    view = build_safety_procedure_view(ctx)
    assert isinstance(view.safety_plan, SafetyPlan)
    assert any(p.category in {"VITALS", "SAFETY"} for p in view.procedures)
    assert "vital_signs" in view.safety_plan.enabled_categories() or any(
        p.code == "SAFETY.VITALS" for p in view.procedures
    )


def test_provenance_merge() -> None:
    prov = ContentProvenance(
        origin="SOURCE_DERIVED",
        status="VERIFIED",
        source_ids=("s1",),
        rule_ids=("R1",),
    )
    block = merge_provenance_into_block({"type": "TEXT", "text": "ok", "source_ids": ["s0"]}, prov)
    assert block["origin"] == "SOURCE_DERIVED"
    assert block["status"] == "VERIFIED"
    assert "s1" in block["source_ids"] and "s0" in block["source_ids"]
    assert "R1" in block["rule_ids"]
    exp = expert_required_provenance()
    assert exp.origin == "EXPERT_REQUIRED"
    assert exp.status == "NEEDS_REVIEW"


def test_source_classification_catalog() -> None:
    assert set(BIOANALYSIS_FIELD_CLASSIFICATION.values()) <= {
        "SOURCE_DERIVED",
        "USER",
        "STATIC_VERIFIED",
        "EXPERT_REQUIRED",
        "UNRESOLVED",
    }


def test_expert_rule_framework_empty_and_status() -> None:
    assert list_expert_rules() == []
    assert EXPERT_RULE_CATALOG == ()
    rule = ExpertRule(
        rule_id="EXP.TEST.v1",
        name="Test placeholder",
        applies_to=("7.3.1",),
        verification_status="UNVERIFIED",
        notes="Must not drive generation",
    )
    assert not rule.is_usable_for_generation()
    verified = ExpertRule(
        rule_id="EXP.OK.v1",
        name="Verified later",
        applies_to=("8.5",),
        verification_status="VERIFIED",
    )
    assert verified.is_usable_for_generation()
    # register helper does not mutate production catalog
    extended = register_expert_rule_for_tests(rule)
    assert len(extended) == 1
    assert EXPERT_RULE_CATALOG == ()


def test_content_matrix_consistency() -> None:
    rows = list_content_matrix()
    assert len(rows) == len(PROTOCOL_CONTENT_MATRIX)
    codes = matrix_section_codes()
    required = {
        "2.2",
        "2.3",
        "2.4",
        "2.7",
        "2.8",
        "4.3",
        "4.4",
        "4.5",
        "4.6",
        "4.7",
        "4.8",
        "4.9",
        "7.3.1",
        "8.1",
        "8.5",
        "9.3",
        "9.7.4",
        "18",
    }
    assert required <= codes
    tree_codes = {s.section_code for s in SECTION_TREE}
    for code in codes:
        assert code in tree_codes, f"matrix section missing from SECTION_TREE: {code}"
    # No invented VERIFIED expert medical rules in matrix types without expert flag
    for r in PROTOCOL_CONTENT_MATRIX:
        if r.type == "EXPERT_REQUIRED":
            assert r.expert_required is True


def test_content_generator_safe_and_deferred() -> None:
    gen = SafeKnownDataContentGenerator()
    snap = {
        "protocol_number": "BE-12A-001",
        "design": "перекрёстный 2×2",
        "food": "после еды",
        "evaluable_n": 24,
        "randomized_n": 28,
    }
    safe = gen.generate("2.6", snap)
    assert safe.status in {"PROPOSED", "NEEDS_REVIEW"}
    assert safe.blocks
    text = safe.blocks[0].get("text") or ""
    assert "BE-12A-001" in text
    assert not find_raw_enums_in_text(text)

    deferred = gen.generate("7.3.1", snap)
    assert deferred.status == "NEEDS_REVIEW"
    assert deferred.blocks[0]["origin"] == "EXPERT_REQUIRED"
    assert "7.3.1" in EXPERT_DEFERRED_SECTION_CODES
    assert "2.6" in SAFE_KNOWN_SECTION_CODES or "2.6" not in EXPERT_DEFERRED_SECTION_CODES


def test_no_raw_enum_in_schedule_names() -> None:
    sched = compose_procedure_schedule(_study_ctx())
    blob = " ".join(p.name for p in sched.procedures)
    # Names may mention food condition code FED in meal name — check raw design enums not leaked as codes
    assert "CROSSOVER_2X2" not in blob


def test_integration_study_to_procedure_schedule_to_draft() -> None:
    ctx = _study_ctx()
    sched = compose_procedure_schedule(ctx)
    assert sched.procedures
    # Attach schedule summary into ctx for draft assembly (does not rewrite P2 DOCX)
    ctx = {
        **ctx,
        "procedure_schedule": sched.to_dict(),
        "bioanalysis_plan": empty_bioanalysis_plan().to_dict(),
        "safety_plan": ctx["safety_plan"],
    }
    out = assemble_protocol(ctx, blocking_validation=False)
    assert out["sections"]
    # Sampling section still generated from existing generators
    sec = next(s for s in out["sections"] if s["section_code"] == "4.4.2")
    assert sec.get("content_blocks") is not None
    # Bioanalysis remains unresolved placeholders (no invented params)
    bio = next(s for s in out["sections"] if s["section_code"] == "7.3.1")
    blob = " ".join(str(b.get("text") or "") for b in bio.get("content_blocks") or [])
    assert "{{BIOANALYSIS" in blob or bio.get("status") in {"UNRESOLVED", "GENERATED", "DRAFT"}
