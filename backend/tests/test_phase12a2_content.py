"""Phase 12A.2 — Protocol Content Foundation tests."""

from __future__ import annotations

from app.domain.content_draft_adapter import preview_section_blocks, resolved_to_draft_blocks
from app.domain.content_matrix import list_content_matrix
from app.domain.content_proposals import propose_bioanalysis, propose_safety
from app.domain.content_resolver import (
    ContentResolver,
    filter_decision_for_render,
    resolve_section,
)
from app.domain.content_validation import validate_resolved_contents
from app.domain.procedure_definition import ProcedureDefinition, validate_procedure_definition
from app.domain.procedure_events import events_from_schedule, structural_dependencies
from app.domain.procedure_schedule import compose_procedure_schedule
from app.domain.sample_processing import empty_sample_processing


def _pid(client, name="P12A2"):
    return client.post("/api/projects", json={"name": name}).json()["id"]


# ---- ProcedureDefinition ----


def test_procedure_definition_create_and_provenance(client):
    pid = _pid(client, "proc-def")
    r = client.post(
        "/api/procedure-definitions",
        json={
            "project_id": pid,
            "code": "DOSING.CUSTOM",
            "name": "Custom dosing marker",
            "category": "DOSING",
            "stage": "PERIOD_1",
            "source_ids": ["src-1"],
            "status": "PROPOSED",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["source_ids"] == ["src-1"]
    assert body["status"] == "PROPOSED"
    listed = client.get(f"/api/procedure-definitions?project_id={pid}").json()
    assert any(x["code"] == "DOSING.CUSTOM" for x in listed)


def test_procedure_definition_versioning_fields():
    p = ProcedureDefinition(
        code="X",
        name="n",
        category="OTHER",
        stage="SCREENING",
        status="PROPOSED",
    )
    assert p.id
    assert validate_procedure_definition(p) == []


# ---- Schedule / deps / no mutation ----


def test_procedure_schedule_ordering_and_deps(client):
    pid = _pid(client, "sched")
    client.post(
        f"/api/projects/{pid}/design",
        json={"type": "CROSSOVER_2X2", "periods": 2, "sequences": [["T", "R"], ["R", "T"]]},
    )
    client.post(
        f"/api/projects/{pid}/subjects",
        json={
            "target_evaluable_n": 24,
            "planned_randomized_n": 28,
            "reserve_n": 0,
            "planned_screened_n": 40,
        },
    )
    sched = client.get(f"/api/projects/{pid}/procedure-schedule").json()
    assert sched["count"] >= 1
    orders = [p["sequence_order"] for p in sched["procedures"]]
    assert orders == sorted(orders)
    assert sched["events"]
    assert sched["dependencies"]
    assert structural_dependencies()


def test_procedure_proposal_does_not_mutate_study(client):
    pid = _pid(client, "proc-mut")
    before = client.get(f"/api/projects/{pid}").json()
    client.post(f"/api/projects/{pid}/procedure-schedule", json={"persist": False})
    after = client.get(f"/api/projects/{pid}").json()
    assert after.get("design") == before.get("design")
    assert after.get("sampling") == before.get("sampling")
    assert after.get("food") == before.get("food")


# ---- Bioanalysis ----


def test_bioanalysis_proposal_no_defaults_and_gap():
    p = propose_bioanalysis()
    assert p.invented_defaults == []
    assert p.plan.get("analytical_method") is None
    assert p.plan.get("lloq") is None
    assert any("method" in g["question"].lower() for g in p.knowledge_gaps)
    p2 = propose_bioanalysis(provided={"analytical_method": "HPLC-MS/MS"})
    # unsourced HPLC cleared
    assert p2.plan.get("analytical_method") is None
    assert p2.invented_defaults == []


def test_bioanalysis_proposal_does_not_mutate_study(client):
    pid = _pid(client, "bio-mut")
    before = client.get(f"/api/projects/{pid}").json()
    r = client.post(f"/api/projects/{pid}/bioanalysis/propose", json={}).json()
    assert r["mutates_study"] is False
    assert r["invented_defaults"] == []
    after = client.get(f"/api/projects/{pid}").json()
    assert after.get("analytes") == before.get("analytes")


def test_no_invented_bioanalysis_defaults(client):
    r = client.post(f"/api/projects/{_pid(client, 'bio-def')}/bioanalysis/propose", json={}).json()
    plan = r["plan"]
    for k in ("lloq", "anticoagulant", "storage_temperature", "analytical_method"):
        assert plan.get(k) in (None, "", [])


# ---- Safety ----


def test_safety_proposal_gap_no_checklist():
    p = propose_safety()
    assert p.invented_defaults == []
    assert any("safety library" in g["question"].lower() for g in p.knowledge_gaps)
    assert p.plan.get("vital_signs") is None


def test_safety_proposal_does_not_mutate_study(client):
    pid = _pid(client, "saf-mut")
    before = client.get(f"/api/projects/{pid}").json()
    r = client.post(f"/api/projects/{pid}/safety-plan/propose", json={}).json()
    assert r["mutates_study"] is False
    after = client.get(f"/api/projects/{pid}").json()
    assert after.get("design") == before.get("design")


def test_no_invented_safety_defaults(client):
    r = client.post(f"/api/projects/{_pid(client, 'saf-def')}/safety-plan/propose", json={}).json()
    assert r["invented_defaults"] == []
    assert not r["plan"].get("AE")


# ---- Content matrix / resolver ----


def test_content_matrix_mapping(client):
    pid = _pid(client, "matrix")
    m = client.get(f"/api/projects/{pid}/content-matrix").json()
    assert m["count"] == len(list_content_matrix())
    assert any(r["section_code"] == "4.4.2" for r in m["rows"])
    assert any(r["section_code"] == "7.3.1" for r in m["rows"])


def test_content_resolver_does_not_write_canonical(client):
    pid = _pid(client, "res-mut")
    before = client.post(f"/api/projects/{pid}/validate").json().get("canonical_snapshot")
    r = client.post(f"/api/projects/{pid}/content/resolve", json={}).json()
    assert r["mutates_canonical"] is False
    after = client.post(f"/api/projects/{pid}/validate").json().get("canonical_snapshot")
    assert after == before


def test_content_resolver_approved_vs_proposed():
    snap = {"design": "CROSSOVER_2X2", "randomized_n": 28}
    r = resolve_section(section_code="4.3", canonical_snapshot=snap)
    assert r.source_type == "CANONICAL"
    assert r.display_as_final is True

    r2 = resolve_section(
        section_code="7.3.1",
        canonical_snapshot={},
        expert_decisions=[
            {
                "id": "d1",
                "decision_type": "OTHER",
                "status": "PROPOSED",
                "proposed_value": {"method": "X"},
            }
        ],
    )
    assert r2.display_as_final is False
    assert r2.source_type == "MISSING" or r2.knowledge_gaps


def test_proposed_decision_not_rendered_as_final():
    assert filter_decision_for_render({"status": "PROPOSED", "id": "1"}) is None


def test_rejected_decision_not_rendered():
    assert filter_decision_for_render({"status": "REJECTED", "id": "1"}) is None


def test_superseded_decision_not_rendered():
    assert filter_decision_for_render({"status": "SUPERSEDED", "id": "1"}) is None


def test_approved_decision_rendered():
    d = filter_decision_for_render({"status": "APPROVED", "id": "1", "final_value": {"x": 1}})
    assert d is not None


def test_missing_required_value_creates_gap():
    r = resolve_section(section_code="7.3.1", canonical_snapshot={})
    assert r.source_type == "MISSING"
    assert r.knowledge_gaps
    assert r.content is None  # no silent N/A string


def test_no_silent_na():
    r = resolve_section(section_code="6.1.9", canonical_snapshot={})
    assert r.content != "N/A"
    assert r.content is None or r.content == {}


def test_content_validation_legacy_and_proposed_as_final():
    from app.domain.content_resolver import ResolvedContent

    findings = validate_resolved_contents(
        [
            ResolvedContent(
                section_code="4.3",
                content="x",
                source_type="PROPOSED_EVIDENCE_OR_RULE",
                status="PROPOSED",
                display_as_final=True,
            )
        ],
        mark_proposed_as_final=True,
        legacy_template_values={"randomized_n": {"canonical": 28, "template": 46}},
        expert_decisions=[{"id": "d", "status": "REJECTED", "forced_render": True}],
    )
    codes = {f.code for f in findings}
    assert "CONTENT.PROPOSED_AS_FINAL" in codes
    assert "CONTENT.LEGACY_TEMPLATE_VALUE" in codes
    assert "CONTENT.CANONICAL_MISMATCH" in codes
    assert "CONTENT.STALE_DECISION" in codes


def test_draft_adapter_marks_proposed():
    from app.domain.content_resolver import ResolvedContent

    blocks = resolved_to_draft_blocks(
        ResolvedContent(
            section_code="7.3.1",
            content={"m": 1},
            source_type="PROPOSED_EVIDENCE_OR_RULE",
            status="PROPOSED",
            display_as_final=False,
        )
    )
    assert "PROPOSED" in blocks[0]["text"]
    assert blocks[0]["display_as_final"] is False


def test_sample_processing_empty():
    sp = empty_sample_processing()
    assert "anticoagulant" in sp.unresolved_fields()
    assert "EDTA" not in str(sp.to_dict()).upper() or "no universal" in sp.notes.lower()
    assert sp.anticoagulant is None


def test_content_api_validate(client):
    pid = _pid(client, "cval")
    r = client.post(
        f"/api/projects/{pid}/content/validate",
        json={"legacy_template_values": {"dose": {"canonical": "100 mg", "template": "50 mg"}}},
    ).json()
    assert any(f["code"] == "CONTENT.CANONICAL_MISMATCH" for f in r["findings"])


def test_events_from_composed_schedule():
    ctx = {
        "project_id": "p",
        "design": {"type": "CROSSOVER_2X2", "periods": 2},
        "subjects": {"planned_randomized_n": 24},
        "sampling": {"points": [{"time_h": 0.0}, {"time_h": 2.0}]},
        "food": {"condition": "FASTING"},
        "washout": {"requires_washout": True, "selected_value": 7, "unit": "day"},
        "observation": {},
        "safety_plan": {},
    }
    sched = compose_procedure_schedule(ctx)
    events = events_from_schedule(sched)
    assert events
    assert ContentResolver().procedure_sections("DOSING")


def test_preview_section_blocks_unit():
    blocks = preview_section_blocks(
        section_code="4.3",
        canonical_snapshot={"design": "CROSSOVER_2X2"},
    )
    assert blocks
    assert blocks[0].get("display_as_final") is True
