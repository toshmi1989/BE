"""Integration tests for Phase 2 API entities and relationships."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _project(client: TestClient) -> str:
    resp = client.post("/api/projects", json={"name": "Phase2 Study"})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_design_crud_and_validation(client: TestClient) -> None:
    pid = _project(client)

    bad = client.post(
        f"/api/projects/{pid}/design",
        json={"type": "CROSSOVER_2X2", "periods": 3, "sequences": [["T", "R"], ["R", "T"]]},
    )
    assert bad.status_code == 422

    ok = client.post(
        f"/api/projects/{pid}/design",
        json={
            "type": "CROSSOVER_2X2",
            "periods": 2,
            "sequences": [["T", "R"], ["R", "T"]],
            "treatments": ["T", "R"],
            "randomization": True,
            "blinding": False,
            "food_condition": "FED",
            "decision_status": "PROPOSED",
            "provenance": {"origin": "USER", "status": "PROPOSED", "source_ids": []},
        },
    )
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["type"] == "CROSSOVER_2X2"
    assert body["decision_status"] == "PROPOSED"
    assert body["provenance"]["origin"] == "USER"

    got = client.get(f"/api/projects/{pid}/design")
    assert got.status_code == 200

    patched = client.patch(
        f"/api/projects/{pid}/design",
        json={"rationale": "Expert confirmed structure"},
    )
    assert patched.status_code == 200
    assert patched.json()["rationale"] == "Expert confirmed structure"


def test_design_recommend_insufficient_and_persist(client: TestClient) -> None:
    pid = _project(client)

    needs = client.post(f"/api/projects/{pid}/design/recommend", json={})
    assert needs.status_code == 200
    assert needs.json()["status"] == "NEEDS_REVIEW"
    assert needs.json()["recommended_design"] is None

    rec = client.post(
        f"/api/projects/{pid}/design/recommend",
        json={
            "reference_product_known": True,
            "dosage_form": "tablet",
            "route": "oral",
            "food_condition": "FED",
            "persist": True,
        },
    )
    assert rec.status_code == 200, rec.text
    payload = rec.json()
    assert payload["status"] == "PROPOSED"
    assert payload["recommended_design"]["type"] == "CROSSOVER_2X2"
    assert payload["persisted_design"] is not None
    assert payload["persisted_design"]["decision_status"] == "PROPOSED"


def test_food_and_subjects_and_client_input(client: TestClient) -> None:
    pid = _project(client)

    food = client.post(
        f"/api/projects/{pid}/food",
        json={
            "condition": "FED",
            "meal_type": "HIGH_CALORIE",
            "meal_start_offset_min": 30,
            "dose_after_meal_min": 0,
            "water_volume_ml": 240,
            "provenance": {"origin": "SOURCE_DERIVED", "status": "NEEDS_REVIEW"},
        },
    )
    assert food.status_code == 201, food.text
    assert food.json()["condition"] == "FED"
    assert food.json()["provenance"]["origin"] == "SOURCE_DERIVED"

    bad_food = client.patch(
        f"/api/projects/{pid}/food",
        json={"meal_start_offset_min": -5},
    )
    assert bad_food.status_code == 422

    subjects = client.post(
        f"/api/projects/{pid}/subjects",
        json={
            "target_evaluable_n": 24,
            "planned_randomized_n": 28,
            "reserve_n": 0,
            "planned_screened_n": 40,
        },
    )
    assert subjects.status_code == 201, subjects.text

    bad_n = client.patch(
        f"/api/projects/{pid}/subjects",
        json={"planned_randomized_n": 10},
    )
    assert bad_n.status_code == 422

    # missing values must not become zeros
    partial = client.post(
        "/api/projects",
        json={"name": "Partial N"},
    ).json()["id"]
    only_eval = client.post(
        f"/api/projects/{partial}/subjects",
        json={"target_evaluable_n": 24},
    )
    assert only_eval.status_code == 201
    body = only_eval.json()
    assert body["target_evaluable_n"] == 24
    assert body["planned_randomized_n"] is None
    assert body["planned_screened_n"] is None

    ci = client.post(
        f"/api/projects/{pid}/client-input",
        json={
            "requested_product_name": "Bosutinib",
            "inn": "bosutinib",
            "dosage": "400 mg",
            "dosage_form": "tablet",
            "route": "oral",
            "requested_subject_count": 28,
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    assert ci.status_code == 201, ci.text
    assert ci.json()["inn"] == "bosutinib"

    upd = client.patch(
        f"/api/projects/{pid}/client-input",
        json={"requested_subject_count": 32},
    )
    assert upd.status_code == 200
    assert upd.json()["requested_subject_count"] == 32
    assert upd.json()["entity_version"] == 2

    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["client_input"]["dosage"] == "400 mg"
    assert detail["food"]["condition"] == "FED"
    assert detail["subjects"]["planned_randomized_n"] == 28


def test_eligibility_crud_shared_object(client: TestClient) -> None:
    pid = _project(client)

    replaced = client.put(
        f"/api/projects/{pid}/eligibility",
        json={
            "inclusion": [{"text": "Healthy adults"}, {"number": 2, "text": "BMI 18.5–30"}],
            "non_inclusion": [{"text": "Prior BE within 3 months"}],
            "exclusion": [{"text": "Pregnancy"}],
        },
    )
    assert replaced.status_code == 200, replaced.text
    data = replaced.json()
    assert len(data["inclusion"]) == 2
    assert data["inclusion"][0]["number"] == 1
    assert data["inclusion"][1]["number"] == 2
    assert len(data["exclusion"]) == 1

    created = client.post(
        f"/api/projects/{pid}/eligibility/criteria",
        json={"category": "exclusion", "text": "Known hypersensitivity"},
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    assert created.json()["number"] == 2

    # duplicate number rejected
    dup = client.post(
        f"/api/projects/{pid}/eligibility/criteria",
        json={"category": "exclusion", "number": 2, "text": "dup"},
    )
    assert dup.status_code == 409

    patched = client.patch(
        f"/api/projects/{pid}/eligibility/criteria/{cid}",
        json={"text": "Known hypersensitivity to bosutinib"},
    )
    assert patched.status_code == 200
    assert "bosutinib" in patched.json()["text"]

    # Same criterion object appears once in GET eligibility
    got = client.get(f"/api/projects/{pid}/eligibility").json()
    excl_ids = [c["id"] for c in got["exclusion"]]
    assert len(excl_ids) == len(set(excl_ids))

    deleted = client.delete(f"/api/projects/{pid}/eligibility/criteria/{cid}")
    assert deleted.status_code == 204
    assert len(client.get(f"/api/projects/{pid}/eligibility").json()["exclusion"]) == 1
