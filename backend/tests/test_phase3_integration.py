"""End-to-end Phase 3 integration: Design → Analyte → Washout → Obs → Sampling → Blood."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_phase3_e2e_pipeline(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "Bosutinib PK pipeline"}).json()
    pid = project["id"]

    design = client.post(
        f"/api/projects/{pid}/design",
        json={
            "type": "CROSSOVER_2X2",
            "periods": 2,
            "sequences": [["T", "R"], ["R", "T"]],
            "treatments": ["T", "R"],
            "food_condition": "FED",
            "decision_status": "PROPOSED",
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    assert design.status_code == 201, design.text

    subjects = client.post(
        f"/api/projects/{pid}/subjects",
        json={
            "target_evaluable_n": 24,
            "planned_randomized_n": 28,
            "reserve_n": 0,
            "planned_screened_n": 40,
        },
    )
    assert subjects.status_code == 201

    analyte = client.post(
        f"/api/projects/{pid}/analytes",
        json={
            "name": "bosutinib",
            "type": "PARENT",
            "matrix": "plasma",
            "tmax_min": 2,
            "tmax_max": 3,
            "tmax_unit": "h",
            "half_life_min": 10,
            "half_life_max": 12,
            "half_life_unit": "h",
            "provenance": {"origin": "SOURCE_DERIVED", "status": "PROPOSED", "source_ids": ["src-demo"]},
        },
    )
    assert analyte.status_code == 201, analyte.text
    analyte_id = analyte.json()["id"]

    metabolite = client.post(
        f"/api/projects/{pid}/analytes",
        json={
            "name": "metabolite-X",
            "type": "ACTIVE_METABOLITE",
            "tmax_min": 4,
            "tmax_max": 6,
            "half_life_min": 14,
            "half_life_max": 16,
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    assert metabolite.status_code == 201

    pk = client.post(
        f"/api/projects/{pid}/pk/parameters",
        json={
            "analyte_id": analyte_id,
            "parameter_code": "Tmax",
            "unit": "h",
            "range_min": 2,
            "range_max": 3,
            "evidence": [
                {
                    "source_id": "src-demo",
                    "page": 12,
                    "section": "PK",
                    "extracted_text": "Tmax 2-3 h",
                    "confidence": 0.8,
                    "status": "PROPOSED",
                }
            ],
            "provenance": {"origin": "SOURCE_DERIVED", "status": "PROPOSED"},
        },
    )
    assert pk.status_code == 201, pk.text
    assert pk.json()["range_min"] == 2

    wash = client.post(
        f"/api/projects/{pid}/washout/calculate",
        json={"selected_value": 5, "selected_unit": "day"},
    )
    assert wash.status_code == 200, wash.text
    assert wash.json()["requires_washout"] is True
    assert wash.json()["calculated_minimum"] is not None

    obs = client.post(
        f"/api/projects/{pid}/observation/calculate",
        json={"selected_duration": 36, "selected_unit": "h"},
    )
    assert obs.status_code == 200, obs.text
    assert obs.json()["selected_duration"] == 36

    samp = client.post(
        f"/api/projects/{pid}/sampling/recommend",
        json={"persist": True},
    )
    assert samp.status_code == 200, samp.text
    body = samp.json()
    assert body["design_id"] == design.json()["id"]
    assert body["total_points_per_period"] >= 5
    assert body["points"][0]["time_h"] == 0
    assert body["points"][0]["reason"] == "BASELINE"
    assert body["manual_override"] is False

    validated = client.post(f"/api/projects/{pid}/sampling/validate")
    assert validated.status_code == 200
    assert "issues" in validated.json()

    # manual override edit
    points = [
        {
            "time_h": p["time_h"],
            "reason": p["reason"],
            "window_before_min": p["window_before_min"],
            "window_after_min": p["window_after_min"],
            "mandatory": p["mandatory"],
            "analyte_ids": p["analyte_ids"],
        }
        for p in body["points"]
    ]
    points.append(
        {
            "time_h": 2.25,
            "reason": "TMAX_CAPTURE",
            "window_before_min": 2,
            "window_after_min": 2,
            "mandatory": False,
            "analyte_ids": [analyte_id],
        }
    )
    patched = client.patch(
        f"/api/projects/{pid}/sampling",
        json={"points": points, "final_observation_h": 36, "manual_override": True},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["manual_override"] is True

    blood = client.post(
        f"/api/projects/{pid}/blood-volume/calculate",
        json={
            "blood_volume_per_pk_sample_ml": 5,
            "screening_volume_ml": 15,
            "safety_laboratory_volume_ml": 10,
        },
    )
    assert blood.status_code == 200, blood.text
    assert blood.json()["periods"] == 2
    assert blood.json()["subjects"] == 28
    assert blood.json()["total_volume_ml"] > 0
    assert "formula_pk" in blood.json()["breakdown"]

    detail = client.get(f"/api/projects/{pid}").json()
    assert len(detail["analytes"]) == 2
    assert detail["washout"] is not None
    assert detail["observation"] is not None
    assert detail["sampling"] is not None
    assert detail["blood_volume"] is not None
    assert detail["design"]["type"] == "CROSSOVER_2X2"


def test_analyte_validation_and_delete(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "Analyte CRUD"}).json()["id"]
    bad = client.post(
        f"/api/projects/{pid}/analytes",
        json={"name": "x", "type": "PARENT", "tmax_min": 5, "tmax_max": 1},
    )
    assert bad.status_code == 422

    ok = client.post(
        f"/api/projects/{pid}/analytes",
        json={"name": "parent", "type": "PARENT", "tmax_min": 1, "tmax_max": 2},
    )
    assert ok.status_code == 201
    aid = ok.json()["id"]
    assert client.delete(f"/api/projects/{pid}/analytes/{aid}").status_code == 204
    assert client.get(f"/api/projects/{pid}/analytes").json() == []
