"""Phase 12A.1 — Expert Knowledge Foundation tests."""

from __future__ import annotations

from app.domain.criteria_rules import default_source_priority_profile, evaluate_criteria
from app.domain.design_decision_engine import DesignDecisionEngine, propose_design
from app.domain.display_value_registry import resolve_display
from app.domain.knowledge_seed import FOUNDATION_KNOWLEDGE_GAPS, list_seed_rules
from app.domain.pk_semantic import (
    display_auc_metric,
    resolve_auc_metric_type,
    standard_pk_profile,
)
from app.domain.protocol_qa import compare_identity_maps, run_protocol_qa
from app.domain.sampling_rules import (
    CompatibilitySamplingPointGenerator,
    evaluate_sampling_plan,
)
from app.domain.validation_engine import validate_knowledge_gaps, validate_project


def _project(client, name="P12A1"):
    return client.post("/api/projects", json={"name": name}).json()


# ---- Seed / KnowledgeRule ----


def test_seed_rules_are_proposed_and_require_expert():
    seeds = list_seed_rules()
    assert len(seeds) >= 30
    assert all(s["status"] == "PROPOSED" for s in seeds)
    assert all(s["requires_expert_confirmation"] is True for s in seeds)
    codes = {s["rule_code"] for s in seeds}
    assert "INPUT-01" in codes and "DESIGN-01" in codes and "SAMPLING-01" in codes


def test_knowledge_rule_crud_and_status(client):
    seeded = client.post("/api/knowledge-rules/seed").json()
    assert len(seeded) >= 30
    assert all(r["status"] == "PROPOSED" for r in seeded)

    created = client.post(
        "/api/knowledge-rules",
        json={
            "rule_code": "TEST-KR-01",
            "name": "Test rule",
            "domain": "QA",
            "description": "provenance test",
            "source_ids": ["src-1"],
            "evidence_claim_ids": ["claim-1"],
            "status": "PROPOSED",
            "requires_expert_confirmation": True,
        },
    )
    assert created.status_code == 201
    rule = created.json()
    rid = rule["id"]
    assert rule["source_ids"] == ["src-1"]
    assert rule["evidence_claim_ids"] == ["claim-1"]

    got = client.get(f"/api/knowledge-rules/{rid}").json()
    assert got["rule_code"] == "TEST-KR-01"

    patched = client.patch(
        f"/api/knowledge-rules/{rid}",
        json={"status": "VERIFIED", "reviewed_by": "expert-1", "source_ids": ["src-verified"]},
    ).json()
    assert patched["status"] == "VERIFIED"
    assert patched["reviewed_by"] == "expert-1"

    rejected = client.patch(
        f"/api/knowledge-rules/{rid}",
        json={"status": "REJECTED", "rejection_reason": "insufficient basis"},
    ).json()
    assert rejected["status"] == "REJECTED"
    assert rejected["rejection_reason"] == "insufficient basis"


# ---- ExpertDecision ----


def test_expert_decision_propose_approve_reject_supersede(client):
    pid = _project(client)["id"]
    d1 = client.post(
        "/api/expert-decisions",
        json={
            "project_id": pid,
            "decision_type": "DESIGN",
            "target_entity_type": "Design",
            "proposed_value": {"design": "CROSSOVER_2X2"},
            "rationale": "standard variability indicated",
        },
    ).json()
    assert d1["status"] == "PROPOSED"

    approved = client.post(
        f"/api/expert-decisions/{d1['id']}/approve",
        json={"decided_by": "expert-a"},
    ).json()
    assert approved["status"] == "APPROVED"
    assert approved["decided_by"] == "expert-a"
    assert approved["final_value"]["design"] == "CROSSOVER_2X2"

    # Approve must not create Design if none existed
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail.get("design") is None

    d2 = client.post(
        "/api/expert-decisions",
        json={
            "project_id": pid,
            "decision_type": "DESIGN",
            "target_entity_type": "Design",
            "proposed_value": {"design": "REPLICATE_2X2X4"},
            "rationale": "high variability",
        },
    ).json()
    client.post(f"/api/expert-decisions/{d2['id']}/approve", json={"decided_by": "expert-b"})
    listed = client.get(f"/api/expert-decisions?project_id={pid}").json()
    statuses = {x["id"]: x["status"] for x in listed}
    assert statuses[d1["id"]] == "SUPERSEDED"
    assert statuses[d2["id"]] == "APPROVED"

    d3 = client.post(
        "/api/expert-decisions",
        json={
            "project_id": pid,
            "decision_type": "WASHOUT",
            "target_entity_type": "Washout",
            "proposed_value": {"days": 7},
            "rationale": "5x half-life proposed",
        },
    ).json()
    rejected = client.post(
        f"/api/expert-decisions/{d3['id']}/reject",
        json={"decided_by": "expert-a", "rationale": "need more evidence"},
    ).json()
    assert rejected["status"] == "REJECTED"


# ---- KnowledgeGap ----


def test_knowledge_gap_create_resolve_blocking(client):
    pid = _project(client, "gaps")["id"]
    client.post(f"/api/knowledge-rules/seed?project_id={pid}")
    gaps = client.get(f"/api/knowledge-gaps?project_id={pid}").json()
    assert len(gaps) >= len(FOUNDATION_KNOWLEDGE_GAPS)
    critical = [g for g in gaps if g["importance"] == "CRITICAL" and g["blocking"]]
    assert critical

    created = client.post(
        "/api/knowledge-gaps",
        json={
            "project_id": pid,
            "domain": "DESIGN",
            "question": "Need verified high-variability indication source",
            "importance": "HIGH",
            "blocking": True,
        },
    ).json()
    assert created["status"] == "OPEN"

    resolved = client.post(
        f"/api/knowledge-gaps/{created['id']}/resolve",
        json={"resolution": "Evidence claim XYZ verified", "resolved_by": "expert"},
    ).json()
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolution"]


def test_critical_knowledge_gap_blocks_validation(client):
    pid = _project(client, "gap-block")["id"]
    client.post(
        "/api/knowledge-gaps",
        json={
            "project_id": pid,
            "domain": "SAMPLE_SIZE",
            "question": "Final randomized N decision logic not yet specified.",
            "importance": "CRITICAL",
            "blocking": True,
        },
    )
    run = client.post(f"/api/projects/{pid}/validate").json()
    gap_issues = [i for i in run["issues"] if i["rule_id"] == "VAL.KNOWLEDGE.GAP_OPEN.v1"]
    assert gap_issues
    assert all(i["blocking"] for i in gap_issues)
    summary = client.get(f"/api/projects/{pid}/validation/summary").json()
    assert summary["blocking"] is True
    assert summary["critical"] >= 1


def test_validate_knowledge_gaps_unit():
    issues = validate_knowledge_gaps(
        {
            "knowledge_gaps": [
                {
                    "id": "g1",
                    "status": "OPEN",
                    "importance": "CRITICAL",
                    "blocking": True,
                    "question": "block me",
                    "domain": "QA",
                },
                {
                    "id": "g2",
                    "status": "RESOLVED",
                    "importance": "CRITICAL",
                    "blocking": True,
                    "question": "done",
                },
            ]
        }
    )
    assert len(issues) == 1
    assert issues[0].blocking is True


# ---- DesignDecision ----


def test_design_standard_2x2_proposal():
    p = propose_design(
        cv_intra_cmax=18.0,
        cv_intra_auc=15.0,
        ci_cmax=[90, 112],
        ci_auc=[92, 108],
        variability_indication="NOT_HIGH",
    )
    assert p.proposed_design == "CROSSOVER_2X2"
    assert "DESIGN-01" in p.triggered_rules
    assert p.requires_expert_confirmation is True


def test_design_replicate_proposal():
    p = propose_design(
        cv_intra_cmax=45.0,
        cv_intra_auc=40.0,
        ci_cmax=[80, 125],
        ci_auc=[80, 125],
        variability_indication="HIGH",
    )
    assert p.proposed_design == "REPLICATE_2X2X4"
    assert "DESIGN-02" in p.triggered_rules
    assert "DESIGN-03" in p.triggered_rules
    assert any("Expanded BE" in g["question"] for g in p.knowledge_gaps)


def test_design_adaptive_when_missing_cv_ci():
    p = propose_design()
    assert p.proposed_design == "ADAPTIVE"
    assert "DESIGN-04" in p.triggered_rules


def test_design_parallel_not_auto_selected_for_long_hl():
    p = propose_design(
        cv_intra_cmax=20.0,
        ci_cmax=[90, 110],
        variability_indication="NOT_HIGH",
        half_life=40.0,
        long_half_life_indicated=True,
    )
    assert p.proposed_design == "CROSSOVER_2X2"
    assert "DESIGN-05" in p.triggered_rules
    assert any("long half-life" in g["question"].lower() for g in p.knowledge_gaps)


def test_design_no_magic_threshold_on_half_life_alone():
    p = propose_design(half_life=100.0)
    assert p.proposed_design == "ADAPTIVE"
    assert any("no threshold" in g["question"].lower() or "half-life" in g["question"].lower() for g in p.knowledge_gaps)


def test_design_api_propose_and_expert_required(client):
    pid = _project(client, "design-prop")["id"]
    res = client.post(
        f"/api/projects/{pid}/design/propose",
        json={
            "cv_intra_cmax": 20,
            "cv_intra_auc": 18,
            "ci_cmax": [90, 110],
            "ci_auc": [90, 110],
            "variability_indication": "NOT_HIGH",
        },
    ).json()
    assert res["proposed_design"] == "CROSSOVER_2X2"
    assert res["requires_expert_confirmation"] is True
    assert DesignDecisionEngine().propose(cv_intra_cmax=1, ci_cmax=1).requires_expert_confirmation


# ---- Sampling ----


def test_sampling_adequacy_rules():
    points = [
        {"time_h": 0.0},
        {"time_h": 0.5},
        {"time_h": 1.0},
        {"time_h": 1.5},
        {"time_h": 2.0},  # Tmax
        {"time_h": 3.0},
        {"time_h": 4.0},
        {"time_h": 6.0},
        {"time_h": 12.0},
        {"time_h": 24.0},
    ]
    r = evaluate_sampling_plan(points=points, tmax_h=2.0, half_life_h=4.0, auc_t_over_inf=0.85)
    assert "SAMPLING-01" in r.passed_rules
    assert "SAMPLING-02" in r.passed_rules
    assert "SAMPLING-03" in r.passed_rules
    assert "SAMPLING-05" in r.passed_rules
    assert "SAMPLING-06" in r.passed_rules
    assert "SAMPLING-07" in r.passed_rules
    assert any("HEURISTIC" in w or "heuristic" in w.lower() for w in r.warnings)


def test_sampling_fails_before_after_tmax_and_last_point():
    points = [{"time_h": 0.0}, {"time_h": 2.0}, {"time_h": 3.0}]
    r = evaluate_sampling_plan(points=points, tmax_h=2.0, half_life_h=10.0, auc_t_over_inf=0.5)
    assert "SAMPLING-01" in r.failed_rules
    assert "SAMPLING-06" in r.failed_rules
    assert "SAMPLING-07" in r.failed_rules


def test_sampling_heuristic_separated_from_pass():
    gen = CompatibilitySamplingPointGenerator()
    prop = gen.propose(existing_points=[{"time_h": 1.0}])
    assert "TMAX_CAPTURE_WINDOW" in prop.heuristic_used
    assert prop.requires_expert_confirmation is True
    # Heuristic alone must not imply regulatory PASS
    ev = evaluate_sampling_plan(points=[{"time_h": 1.0}], tmax_h=1.0)
    assert "SAMPLING-01" in ev.failed_rules or "SAMPLING-02" in ev.failed_rules


def test_sampling_api(client):
    pid = _project(client, "samp")["id"]
    ev = client.post(
        f"/api/projects/{pid}/sampling/evaluate",
        json={
            "points": [
                {"time_h": 0},
                {"time_h": 0.5},
                {"time_h": 1},
                {"time_h": 1.5},
                {"time_h": 2},
                {"time_h": 3},
                {"time_h": 4},
                {"time_h": 8},
                {"time_h": 24},
            ],
            "tmax_h": 2,
            "half_life_h": 5,
            "auc_t_over_inf": 0.9,
        },
    ).json()
    assert "passed_rules" in ev
    prop = client.post(
        f"/api/projects/{pid}/sampling/propose",
        json={"existing_points": [{"time_h": 0}, {"time_h": 2}]},
    ).json()
    assert prop["requires_expert_confirmation"] is True


# ---- PK ----


def test_pk_auc_semantic_and_display():
    assert resolve_auc_metric_type("AUC0-t") == "AUC_0_LAST"
    assert resolve_auc_metric_type("AUC0-72") == "AUC_0_72H"
    assert resolve_auc_metric_type("AUC0-inf") == "AUC_0_INF"
    assert display_auc_metric("AUC_0_LAST") == "AUC0-x"
    assert "AUC0" in display_auc_metric("AUC_0_72H")
    profile = standard_pk_profile()
    codes = {p.code for p in profile.parameters}
    assert {"Cmax", "AUC_0_LAST", "AUC_0_INF", "Tmax"} <= codes
    assert profile.kind == "STANDARD_PROPOSED"
    assert profile.requires_expert_confirmation is True


def test_pk_api_propose(client):
    pid = _project(client, "pk")["id"]
    a = client.post(f"/api/projects/{pid}/pk/analytes/propose", json={}).json()
    assert a["requires_expert_confirmation"] is True
    p = client.post(f"/api/projects/{pid}/pk/parameters/propose", json={}).json()
    assert p["kind"] == "STANDARD_PROPOSED"


def test_display_registry_design_and_food():
    assert "2×2" in resolve_display("CROSSOVER_2X2", context="design_long")
    assert "2×2×4" in resolve_display("REPLICATE_2X2X4", context="design_long")
    assert resolve_display("FED", context="food") == "после приёма пищи"


# ---- Criteria ----


def test_criteria_overlays():
    r = evaluate_criteria(
        has_cyp_mentions=True,
        has_contraindications=True,
        has_smoking_enzyme_link=True,
        contraception_days_from_smpc=30,
        tmax_h=2.0,
        smpc_evidence_claim_ids=["e1"],
    )
    for code in ("CRIT-01", "CRIT-03", "CRIT-04", "CRIT-05", "CRIT-06", "CRIT-07"):
        assert code in r.applied_rules
    vomit = next(o for o in r.drug_specific_overlays if o["type"] == "VOMITING_WINDOW_PROPOSED")
    assert vomit["proposed_window_h"] == 4.0
    assert vomit["status"] == "PROPOSED"
    sp = default_source_priority_profile()
    assert sp.ordered_classes[0] == "EEC_DECISION_85"
    assert sp.requires_expert_confirmation is True


def test_criteria_api(client):
    pid = _project(client, "crit")["id"]
    r = client.post(
        f"/api/projects/{pid}/criteria/evaluate",
        json={"has_cyp_mentions": True, "tmax_h": 1.5},
    ).json()
    assert "CRIT-05" in r["applied_rules"]


# ---- Previous protocol / QA ----


def test_previous_protocol_legacy_diff():
    items = compare_identity_maps(
        previous={
            "sponsor": "Old Sponsor",
            "trade_name": "OldDrug",
            "dosage": "50 mg",
            "randomized_n": 46,
            "tmax": 1.0,
            "half_life": 5.0,
        },
        current={
            "sponsor": "New Sponsor",
            "trade_name": "NewDrug",
            "dosage": "100 mg",
            "randomized_n": 28,
            "tmax": 2.0,
            "half_life": 5.0,
        },
    )
    types = {i.diff_type for i in items}
    assert "VALUE_CHANGED" in types
    assert "LEGACY_SUSPECTED" in types
    unchanged = [i for i in items if i.paragraph_or_field == "half_life" and i.diff_type == "VALUE_UNCHANGED"]
    assert unchanged


def test_protocol_qa_checks():
    findings = run_protocol_qa(
        canonical={
            "design": "CROSSOVER_2X2",
            "washout": 7,
            "auc_metric": "AUC_0_LAST",
            "sponsor": "NewCo",
        },
        displayed={
            "design": "ADAPTIVE",
            "washout": 7,
            "auc_metric": "AUC_0_72H",
            "sponsor": "NewCo",
        },
        document_text="Hello {{PLACEHOLDER.X}} and CROSSOVER_2X2 leftover",
        previous_identity={"sponsor": "OldCo"},
    )
    codes = {f.code for f in findings}
    assert "QA-DESIGN-01" in codes
    assert "QA-PK-01" in codes
    assert "QA-DOC-01" in codes
    assert "QA-DOC-03" in codes
    assert any(f.code.startswith("QA-LEGACY") for f in findings)


def test_qa_and_diff_api(client):
    pid = _project(client, "qa")["id"]
    qa = client.post(
        f"/api/projects/{pid}/qa/run",
        json={
            "canonical": {"design": "A"},
            "displayed": {"design": "B"},
            "document_text": "ok",
        },
    ).json()
    assert "findings" in qa or "id" in qa
    listed = client.get(f"/api/projects/{pid}/qa").json()
    assert listed is not None

    diff = client.post(
        f"/api/projects/{pid}/protocol-diff",
        json={
            "previous_map": {"sponsor": "Old", "dosage": "10 mg"},
            "current_map": {"sponsor": "New", "dosage": "20 mg"},
        },
    ).json()
    assert diff.get("diff_items") or "id" in diff


def test_validate_project_includes_knowledge_collector():
    ctx = {"knowledge_gaps": [], "study": {}, "design": None}
    # Should not crash when other validators get empty ctx
    issues = validate_project(
        {
            "study": {"title": "t"},
            "design": None,
            "food": None,
            "eligibility": None,
            "analytes": [],
            "pk": None,
            "washout": None,
            "observation": None,
            "sampling": None,
            "blood_volume": None,
            "statistics": None,
            "subjects": None,
            "administration": None,
            "knowledge_gaps": [],
            "sources": [],
            "evidence_claims": [],
            "product": None,
            "reference_product": None,
            "sponsor": None,
        }
    )
    assert isinstance(issues, list)
