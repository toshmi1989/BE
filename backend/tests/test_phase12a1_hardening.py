"""Phase 12A.1-HARDENING — architectural regression tests."""

from __future__ import annotations

import re
from pathlib import Path

from app.domain.criteria_rules import default_source_priority_profile, evaluate_criteria
from app.domain.decision_proposals import propose_food, propose_sample_size_layer, propose_washout
from app.domain.design_decision_engine import propose_design
from app.domain.display_value_registry import resolve_display
from app.domain.knowledge_seed import FOUNDATION_KNOWLEDGE_GAPS, list_seed_rules
from app.domain.knowledge_transitions import assert_knowledge_rule_transition
from app.domain.pk_semantic import display_auc_metric, resolve_auc_metric_type, standard_pk_profile
from app.domain.protocol_qa import compare_identity_maps, run_protocol_qa
from app.domain.sampling_rules import CompatibilitySamplingPointGenerator, evaluate_sampling_plan
from app.domain.validation_engine import validate_knowledge_gaps, validate_knowledge_rules
from app.domain.exceptions import ValidationError
import pytest


def _pid(client, name="H12A1"):
    return client.post("/api/projects", json={"name": name}).json()["id"]


# ---- A/B Status + provenance ----


def test_rejected_rule_cannot_become_verified(client):
    r = client.post(
        "/api/knowledge-rules",
        json={
            "rule_code": "H-KR-REJ",
            "name": "r",
            "domain": "QA",
            "description": "d",
            "status": "PROPOSED",
        },
    ).json()
    client.patch(f"/api/knowledge-rules/{r['id']}", json={"status": "REJECTED", "rejection_reason": "no"})
    bad = client.patch(
        f"/api/knowledge-rules/{r['id']}",
        json={"status": "VERIFIED", "source_ids": ["x"]},
    )
    assert bad.status_code in {400, 422}
    assert assert_knowledge_rule_transition  # imported for unit
    with pytest.raises(ValidationError):
        assert_knowledge_rule_transition("REJECTED", "VERIFIED")


def test_verified_requires_provenance(client):
    r = client.post(
        "/api/knowledge-rules",
        json={
            "rule_code": "H-KR-PROV",
            "name": "r",
            "domain": "QA",
            "description": "d",
        },
    ).json()
    bad = client.patch(f"/api/knowledge-rules/{r['id']}", json={"status": "VERIFIED"})
    assert bad.status_code in {400, 422}
    ok = client.patch(
        f"/api/knowledge-rules/{r['id']}",
        json={"status": "VERIFIED", "evidence_claim_ids": ["claim-1"]},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "VERIFIED"


def test_cannot_create_approved_decision_directly(client):
    pid = _pid(client, "create-approved")
    r = client.post(
        "/api/expert-decisions",
        json={
            "project_id": pid,
            "decision_type": "DESIGN",
            "target_entity_type": "Design",
            "proposed_value": {"design": "CROSSOVER_2X2"},
            "rationale": "bypass attempt",
            "status": "APPROVED",
        },
    )
    assert r.status_code in {400, 422}


def test_cannot_approve_superseded(client):
    pid = _pid(client, "super")
    d1 = client.post(
        "/api/expert-decisions",
        json={
            "project_id": pid,
            "decision_type": "DESIGN",
            "target_entity_type": "Design",
            "proposed_value": {"design": "CROSSOVER_2X2"},
            "rationale": "v1",
        },
    ).json()
    client.post(f"/api/expert-decisions/{d1['id']}/approve", json={"decided_by": "e1"})
    d2 = client.post(
        "/api/expert-decisions",
        json={
            "project_id": pid,
            "decision_type": "DESIGN",
            "target_entity_type": "Design",
            "proposed_value": {"design": "REPLICATE_2X2X4"},
            "rationale": "v2",
        },
    ).json()
    client.post(f"/api/expert-decisions/{d2['id']}/approve", json={"decided_by": "e2"})
    listed = {x["id"]: x for x in client.get(f"/api/expert-decisions?project_id={pid}").json()}
    assert listed[d1["id"]]["status"] == "SUPERSEDED"
    assert listed[d1["id"]]["proposed_value"]["design"] == "CROSSOVER_2X2"  # not overwritten
    assert listed[d2["id"]]["status"] == "APPROVED"
    again = client.post(f"/api/expert-decisions/{d1['id']}/approve", json={"decided_by": "e3"})
    assert again.status_code in {400, 422}


# ---- D/E No silent mutation / approve ≠ apply ----


def test_design_proposal_does_not_mutate_study(client):
    pid = _pid(client, "des-mut")
    before = client.get(f"/api/projects/{pid}").json()
    assert before.get("design") is None
    prop = client.post(
        f"/api/projects/{pid}/design/propose",
        json={
            "cv_intra_cmax": 20,
            "ci_cmax": [90, 110],
            "variability_indication": "NOT_HIGH",
        },
    ).json()
    assert prop["proposed_design"] == "CROSSOVER_2X2"
    after = client.get(f"/api/projects/{pid}").json()
    assert after.get("design") is None


def test_sampling_proposal_does_not_mutate_canonical(client):
    pid = _pid(client, "samp-mut")
    before = client.get(f"/api/projects/{pid}").json()
    assert before.get("sampling") is None
    client.post(
        f"/api/projects/{pid}/sampling/propose",
        json={"existing_points": [{"time_h": 0}, {"time_h": 1}, {"time_h": 2}]},
    )
    after = client.get(f"/api/projects/{pid}").json()
    assert after.get("sampling") is None


def test_pk_proposal_does_not_mutate_study(client):
    pid = _pid(client, "pk-mut")
    before = client.get(f"/api/projects/{pid}").json()
    n_before = len(before.get("analytes") or [])
    client.post(f"/api/projects/{pid}/pk/analytes/propose", json={})
    client.post(f"/api/projects/{pid}/pk/parameters/propose", json={})
    after = client.get(f"/api/projects/{pid}").json()
    assert len(after.get("analytes") or []) == n_before
    assert after.get("pk_parameters") == before.get("pk_parameters") or after.get("pk") == before.get("pk")


def test_food_proposal_does_not_mutate_study(client):
    pid = _pid(client, "food-mut")
    before = client.get(f"/api/projects/{pid}").json()
    assert before.get("food") is None
    p = propose_food(condition="FED")
    assert p.proposed_condition == "FED"
    assert p.requires_expert_confirmation is True
    assert "kcal" in p.forbidden_auto_constants
    after = client.get(f"/api/projects/{pid}").json()
    assert after.get("food") is None


def test_washout_proposal_does_not_mutate_study(client):
    pid = _pid(client, "wash-mut")
    before = client.get(f"/api/projects/{pid}").json()
    assert before.get("washout") is None
    p = propose_washout(half_life=12.0)
    assert p.calculated_minimum == 60.0
    assert p.requires_expert_confirmation is True
    after = client.get(f"/api/projects/{pid}").json()
    assert after.get("washout") is None


def test_sample_size_proposal_does_not_mutate_study(client):
    pid = _pid(client, "ss-mut")
    before = client.get(f"/api/projects/{pid}").json()
    p = propose_sample_size_layer(design="CROSSOVER_2X2", cv_intra=25.0)
    assert p.requires_expert_confirmation is True
    after = client.get(f"/api/projects/{pid}").json()
    assert after.get("sample_size") == before.get("sample_size")
    assert after.get("statistics") == before.get("statistics")


def test_approve_decision_is_not_apply_decision(client):
    pid = _pid(client, "approve-not-apply")
    created = client.post(
        f"/api/projects/{pid}/design",
        json={"type": "CROSSOVER_2X2", "periods": 2, "sequences": [["T", "R"], ["R", "T"]]},
    )
    assert created.status_code in {200, 201}
    design_before = client.get(f"/api/projects/{pid}").json()["design"]["type"]
    assert design_before == "CROSSOVER_2X2"
    snap_before = client.post(f"/api/projects/{pid}/validate").json()["canonical_snapshot"]
    d = client.post(
        "/api/expert-decisions",
        json={
            "project_id": pid,
            "decision_type": "DESIGN",
            "target_entity_type": "Design",
            "proposed_value": {"design": "REPLICATE_2X2X4"},
            "rationale": "want replicate",
        },
    ).json()
    approved = client.post(
        f"/api/expert-decisions/{d['id']}/approve",
        json={"decided_by": "auditor"},
    ).json()
    assert approved["status"] == "APPROVED"
    assert approved["decided_by"] == "auditor"
    assert approved["decided_at"] is not None
    assert approved["final_value"]["design"] == "REPLICATE_2X2X4"
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["design"]["type"] == "CROSSOVER_2X2"
    snap_after = client.post(f"/api/projects/{pid}/validate").json()["canonical_snapshot"]
    assert snap_after.get("design") == snap_before.get("design")


# ---- F Critical gaps ----


def test_critical_gap_resolved_stops_blocking(client):
    pid = _pid(client, "gap-res")
    g = client.post(
        "/api/knowledge-gaps",
        json={
            "project_id": pid,
            "domain": "SAMPLE_SIZE",
            "question": "H-CRITICAL-GAP",
            "importance": "CRITICAL",
            "blocking": True,
        },
    ).json()
    run1 = client.post(f"/api/projects/{pid}/validate").json()
    assert any(i["rule_id"] == "VAL.KNOWLEDGE.GAP_OPEN.v1" for i in run1["issues"])
    resolved = client.post(
        f"/api/knowledge-gaps/{g['id']}/resolve",
        json={"resolution": "N fixed", "resolved_by": "expert"},
    ).json()
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolved_at"] is not None
    assert resolved["resolved_by"] == "expert"
    assert resolved["resolution"] == "N fixed"
    run2 = client.post(f"/api/projects/{pid}/validate").json()
    still = [i for i in run2["issues"] if i.get("entity_id") == g["id"]]
    assert still == []


def test_medium_gap_does_not_block(client):
    pid = _pid(client, "gap-med")
    client.post(
        "/api/knowledge-gaps",
        json={
            "project_id": pid,
            "domain": "PK",
            "question": "H-MEDIUM-GAP",
            "importance": "MEDIUM",
            "blocking": False,
        },
    )
    issues = validate_knowledge_gaps(
        {
            "knowledge_gaps": [
                {
                    "id": "m1",
                    "status": "OPEN",
                    "importance": "MEDIUM",
                    "blocking": False,
                    "question": "x",
                }
            ]
        }
    )
    assert issues == []
    run = client.post(f"/api/projects/{pid}/validate").json()
    assert not any(
        i["rule_id"] == "VAL.KNOWLEDGE.GAP_OPEN.v1" and "H-MEDIUM-GAP" in i["message"]
        for i in run["issues"]
    )


# ---- G Design ----


def test_design_proposal_contains_traceable_reason():
    p = propose_design(
        cv_intra_cmax=18,
        cv_intra_auc=15,
        ci_cmax=[90, 110],
        ci_auc=[90, 110],
        variability_indication="NOT_HIGH",
    )
    assert p.proposed_design == "CROSSOVER_2X2"
    assert p.reasons
    assert p.decision_inputs
    assert "DESIGN-01" in p.triggered_rules
    assert p.requires_expert_confirmation is True


def test_design_high_var_no_expanded_be_auto():
    p = propose_design(
        cv_intra_cmax=50,
        ci_cmax=[80, 125],
        variability_indication="HIGH",
    )
    assert p.proposed_design == "REPLICATE_2X2X4"
    assert any("Expanded BE" in g["question"] for g in p.knowledge_gaps)
    assert "expanded" not in (p.proposed_design or "").lower()


def test_design_no_numeric_cv_threshold_in_engine_source():
    src = Path(__file__).resolve().parents[1] / "app" / "domain" / "design_decision_engine.py"
    text = src.read_text(encoding="utf-8")
    assert "variability_indication" in text
    # No magic CV cutoff like cv > 30
    assert not re.search(r"cv_intra.*>\s*\d+", text)


# ---- H Sampling ----


def test_sampling_heuristic_not_regulatory_pass():
    gen = CompatibilitySamplingPointGenerator()
    prop = gen.propose(existing_points=[{"time_h": 1.0}])
    assert "TMAX_CAPTURE_WINDOW" in prop.heuristic_used
    ev = evaluate_sampling_plan(points=[{"time_h": 1.0}], tmax_h=1.0)
    assert ev.failed_rules  # heuristic alone insufficient


def test_sampling_adequacy_proposed_not_verified():
    points = [
        {"time_h": t}
        for t in [0, 0.5, 1, 1.5, 2, 3, 4, 6, 12, 24]
    ]
    r = evaluate_sampling_plan(points=points, tmax_h=2.0, half_life_h=4.0, auc_t_over_inf=0.85)
    assert r.status == "PROPOSED"
    assert r.requires_expert_confirmation is True


# ---- I PK ----


def test_auc_alias_canonical_display_chain():
    assert resolve_auc_metric_type("AUC0-t") == "AUC_0_LAST"
    assert resolve_auc_metric_type("AUC0-x") == "AUC_0_LAST"
    assert resolve_auc_metric_type("AUC0-72") == "AUC_0_72H"
    assert resolve_auc_metric_type("AUC0-t") != resolve_auc_metric_type("AUC0-72")
    assert display_auc_metric("AUC_0_LAST") == "AUC0-x"
    assert display_auc_metric("AUC_0_72H") == "AUC0-72"
    assert "AUC_0_LAST" not in display_auc_metric("AUC_0_LAST")


def test_display_no_raw_enums_for_design_long():
    d = resolve_display("CROSSOVER_2X2", context="design_long")
    assert "CROSSOVER" not in d
    assert "2×2" in d


# ---- J Criteria / source ----


def test_criteria_vomiting_proposed_not_verified():
    r = evaluate_criteria(tmax_h=2.0)
    vomit = next(o for o in r.drug_specific_overlays if o["type"] == "VOMITING_WINDOW_PROPOSED")
    assert vomit["status"] == "PROPOSED"
    assert r.status == "PROPOSED"


def test_source_priority_does_not_auto_resolve():
    sp = default_source_priority_profile()
    assert sp.requires_expert_confirmation is True
    assert any("conflict" in g["question"].lower() for g in sp.knowledge_gaps)


# ---- K/L Diff + QA ----


def test_legacy_suspected_not_deleted():
    items = compare_identity_maps(
        previous={"sponsor": "Old", "trade_name": "OldDrug", "dosage": "10", "randomized_n": 46},
        current={"sponsor": "New", "trade_name": "NewDrug", "dosage": "20", "randomized_n": 28},
    )
    legacy = [i for i in items if i.diff_type == "LEGACY_SUSPECTED"]
    assert legacy
    assert all(i.review_status == "OPEN" for i in legacy)


def test_qa_finding_shape_and_severity_blocking():
    findings = run_protocol_qa(
        canonical={"design": "A", "auc_metric": "AUC_0_LAST"},
        displayed={"design": "B", "auc_metric": "AUC_0_72H"},
        document_text="{{X.Y}}",
    )
    by_code = {f.code: f for f in findings}
    assert by_code["QA-DESIGN-01"].blocking is True
    assert by_code["QA-DOC-01"].severity == "CRITICAL"
    for f in findings:
        assert f.code and f.severity and f.message


# ---- M API ----


def test_api_404_and_422(client):
    assert client.get("/api/knowledge-rules/00000000-0000-0000-0000-000000000001").status_code == 404
    assert client.get("/api/expert-decisions/00000000-0000-0000-0000-000000000001").status_code == 404
    bad = client.post(
        "/api/knowledge-rules",
        json={"rule_code": "x", "name": "n", "domain": "NOT_A_DOMAIN", "description": "d"},
    )
    assert bad.status_code in {400, 422}
    pid = _pid(client, "api-ok")
    assert client.post(f"/api/projects/{pid}/criteria/evaluate", json={}).status_code == 200
    assert client.post(f"/api/projects/{pid}/qa/run", json={"canonical": {}, "displayed": {}}).status_code == 200


def test_decision_scoped_to_project(client):
    p1 = _pid(client, "own1")
    p2 = _pid(client, "own2")
    d = client.post(
        "/api/expert-decisions",
        json={
            "project_id": p1,
            "decision_type": "OTHER",
            "target_entity_type": "Study",
            "proposed_value": {"x": 1},
            "rationale": "scope",
        },
    ).json()
    listed = client.get(f"/api/expert-decisions?project_id={p2}").json()
    assert all(x["id"] != d["id"] for x in listed)


# ---- N Migration additive ----


def test_migration_0013_is_additive():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0013_phase12a1_knowledge.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "op.create_table" in text
    # No drop of pre-existing study tables in upgrade
    upgrade = text.split("def downgrade")[0]
    assert "op.drop_table(\"designs\")" not in upgrade
    assert "op.drop_table(\"studies\")" not in upgrade
    assert "def downgrade" in text


# ---- Seed safety ----


def test_all_seeds_proposed_expert_required_no_kcal_constants():
    seeds = list_seed_rules()
    assert len(seeds) == 36
    for s in seeds:
        assert s["status"] == "PROPOSED"
        assert s["requires_expert_confirmation"] is True
        blob = str(s).lower()
        assert "800 kcal" not in blob
        assert "1000 kcal" not in blob
        assert "potvin" not in blob or "not" in s["description"].lower() or "gap" in str(s.get("action_definition")).lower() or s["rule_code"] == "SAMPLE-05"
    assert any("ExpertRule" in g["question"] or "coexistence" in g["question"] for g in FOUNDATION_KNOWLEDGE_GAPS)
    assert any("approve" in g["question"].lower() or "canonical" in g["question"].lower() for g in FOUNDATION_KNOWLEDGE_GAPS)


def test_validate_verified_rule_without_provenance_unit():
    issues = validate_knowledge_rules(
        {
            "knowledge_rules": [
                {
                    "id": "r1",
                    "rule_code": "X",
                    "status": "VERIFIED",
                    "regulatory_basis_id": None,
                    "evidence_claim_ids": [],
                    "source_ids": [],
                }
            ]
        }
    )
    assert len(issues) == 1
    assert issues[0].rule_id == "VAL.KNOWLEDGE.VERIFIED_WITHOUT_PROVENANCE.v1"


def test_regulatory_basis_verified_needs_section(client):
    bad = client.post(
        "/api/regulatory-bases",
        json={"title": "Fake", "status": "VERIFIED"},
    )
    assert bad.status_code in {400, 422}
    ok = client.post(
        "/api/regulatory-bases",
        json={
            "title": "Decision 85",
            "document_identifier": "Decision 85",
            "section_reference": "p.18",
            "status": "VERIFIED",
        },
    )
    assert ok.status_code == 201


def test_reseed_does_not_downgrade_verified(client):
    client.post("/api/knowledge-rules/seed")
    rules = client.get("/api/knowledge-rules").json()
    target = next(r for r in rules if r["rule_code"] == "INPUT-01")
    client.patch(
        f"/api/knowledge-rules/{target['id']}",
        json={"status": "VERIFIED", "source_ids": ["manual-src"]},
    )
    client.post("/api/knowledge-rules/seed")
    again = next(r for r in client.get("/api/knowledge-rules").json() if r["rule_code"] == "INPUT-01")
    assert again["status"] == "VERIFIED"
