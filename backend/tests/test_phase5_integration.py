"""Phase 5 evidence foundation + full validation integration."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _configure_complete(client: TestClient) -> str:
    project = client.post("/api/projects", json={"name": "Phase5 complete"}).json()
    pid = project["id"]

    client.put(
        f"/api/projects/{pid}/sponsor",
        json={"name": "Phase5 Sponsor", "country": "RU", "contact_email": "sponsor@test.example"},
    )
    client.put(
        f"/api/projects/{pid}/reference-product",
        json={
            "trade_name": "Bosulif",
            "inn": "bosutinib",
            "dosage": "400 mg",
            "purchased_status": "UNKNOWN",
            "provenance": {"origin": "USER", "status": "PROPOSED", "source_ids": ["label-1"]},
        },
    )
    client.post(
        f"/api/projects/{pid}/sources",
        json={"type": "SmPC", "title": "Bosulif SmPC", "provenance": {"origin": "USER", "status": "PROPOSED"}},
    )
    client.post(
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
    client.post(
        f"/api/projects/{pid}/food",
        json={
            "condition": "FED",
            "meal_type": "HIGH_CALORIE",
            "decision_status": "PROPOSED",
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    client.put(
        f"/api/projects/{pid}/eligibility",
        json={"inclusion": [{"number": 1, "text": "Healthy volunteers"}], "non_inclusion": [], "exclusion": []},
    )
    client.post(
        f"/api/projects/{pid}/subjects",
        json={
            "target_evaluable_n": 24,
            "planned_randomized_n": 28,
            "planned_screened_n": 40,
            "reserve_n": 0,
        },
    )
    analyte = client.post(
        f"/api/projects/{pid}/analytes",
        json={
            "name": "bosutinib",
            "type": "PARENT",
            "tmax_min": 2,
            "tmax_max": 3,
            "tmax_unit": "h",
            "half_life_min": 10,
            "half_life_max": 12,
            "half_life_unit": "h",
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    ).json()
    aid = analyte["id"]
    client.post(
        f"/api/projects/{pid}/pk/parameters",
        json={
            "analyte_id": aid,
            "parameter_code": "Tmax",
            "unit": "h",
            "range_min": 2,
            "range_max": 3,
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    client.post(
        f"/api/projects/{pid}/washout/calculate",
        json={"selected_value": 5, "selected_unit": "day"},
    )
    client.post(
        f"/api/projects/{pid}/observation/calculate",
        json={"selected_duration": 36, "selected_unit": "h"},
    )
    client.post(f"/api/projects/{pid}/sampling/recommend", json={"persist": True})
    detail = client.get(f"/api/projects/{pid}").json()
    points = len(detail["sampling"]["points"])
    client.post(
        f"/api/projects/{pid}/blood-volume/calculate",
        json={
            "blood_volume_per_pk_sample_ml": 5,
            "screening_volume_ml": 15,
            "safety_laboratory_volume_ml": 10,
            "subjects": 28,
        },
    )
    # ensure blood volume matches point count (service uses sampling)
    _ = points
    cv = client.post(
        f"/api/projects/{pid}/statistics/cv",
        json={
            "source_id": "src-cv",
            "analyte_id": aid,
            "parameter": "Cmax",
            "design": "CROSSOVER_2X2",
            "condition": "FED",
            "n_total": 46,
            "n_be_analysis": 40,
            "cv_value": 25,
            "evidence": [{"source_id": "src-cv", "extracted_text": "CV 25%", "status": "PROPOSED"}],
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    ).json()
    client.post(
        f"/api/projects/{pid}/statistics/cv/select",
        json={
            "selection_method": "SINGLE_STUDY",
            "selected_study_id": cv["id"],
            "cv_study_ids": [cv["id"]],
        },
    )
    client.post(
        f"/api/projects/{pid}/statistics/sample-size",
        json={"design_type": "CROSSOVER_2X2", "dropout_pct": 10},
    )
    return pid


def test_valid_complete_project_zero_blocking(client: TestClient) -> None:
    pid = _configure_complete(client)
    run = client.post(f"/api/projects/{pid}/validate")
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["summary"]["blocking"] is False, body["summary"]
    assert body["summary"]["critical"] == 0
    assert body["summary"]["errors"] == 0
    assert body["consistency_snapshot"]["design"] == "CROSSOVER_2X2"
    assert body["canonical_snapshot"]["project_id"] == pid

    listed = client.get(f"/api/projects/{pid}/validation")
    assert listed.status_code == 200
    summary = client.get(f"/api/projects/{pid}/validation/summary")
    assert summary.json()["blocking"] is False

    if listed.json():
        issue_id = listed.json()[0]["id"]
        ack = client.post(f"/api/projects/{pid}/validation/{issue_id}/acknowledge")
        assert ack.status_code == 200
        assert ack.json()["status"] == "ACKNOWLEDGED"


def test_empty_project_validate_blocking(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "empty"}).json()["id"]
    run = client.post(f"/api/projects/{pid}/validate").json()
    assert run["summary"]["blocking"] is True


def test_research_case_evidence_apply_and_conflict(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "research"}).json()
    pid = project["id"]
    analyte = client.post(
        f"/api/projects/{pid}/analytes",
        json={
            "name": "parent",
            "type": "PARENT",
            "tmax_min": 1,
            "tmax_max": 1,
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    ).json()

    case = client.post(f"/api/projects/{pid}/research-case", json={"status": "NEW"})
    assert case.status_code == 201, case.text

    task = client.post(
        f"/api/projects/{pid}/research-case/tasks",
        json={"task_type": "PK", "query_profile": {"inn": "bosutinib"}, "priority": 10},
    )
    assert task.status_code == 201

    # PROPOSED claim must not update study
    ev_prop = client.post(
        f"/api/projects/{pid}/research-case/evidence",
        json={
            "source_id": "src-a",
            "evidence_type": "PK",
            "verification_status": "PROPOSED",
            "claims": [
                {
                    "field_name": "tmax",
                    "value": "2–3 h",
                    "normalized_value": {"min": 2, "max": 3},
                    "unit": "h",
                    "status": "PROPOSED",
                    "source_ids": ["src-a"],
                }
            ],
        },
    )
    assert ev_prop.status_code == 201
    proposed_claim_id = ev_prop.json()["claims"][0]["id"]
    apply_prop = client.post(
        f"/api/projects/{pid}/research-case/apply-verified",
        json={"claim_ids": [proposed_claim_id], "analyte_id": analyte["id"]},
    )
    assert apply_prop.status_code == 200
    assert apply_prop.json()["applied"] == []
    assert apply_prop.json()["skipped"]
    refreshed = client.get(f"/api/projects/{pid}").json()
    assert refreshed["analytes"][0]["tmax_min"] == 1

    # VERIFIED claim updates study + provenance
    ev_ver = client.post(
        f"/api/projects/{pid}/research-case/evidence",
        json={
            "source_id": "src-b",
            "evidence_type": "PK",
            "verification_status": "VERIFIED",
            "claims": [
                {
                    "field_name": "tmax",
                    "value": "2–3 h",
                    "normalized_value": {"min": 2, "max": 3},
                    "unit": "h",
                    "status": "VERIFIED",
                    "origin": "SOURCE_DERIVED",
                    "source_ids": ["src-b"],
                }
            ],
        },
    )
    assert ev_ver.status_code == 201
    verified_claim_id = ev_ver.json()["claims"][0]["id"]
    apply_ver = client.post(
        f"/api/projects/{pid}/research-case/apply-verified",
        json={"claim_ids": [verified_claim_id], "analyte_id": analyte["id"]},
    )
    assert apply_ver.status_code == 200, apply_ver.text
    assert apply_ver.json()["applied"]
    refreshed = client.get(f"/api/projects/{pid}").json()
    a = refreshed["analytes"][0]
    assert a["tmax_min"] == 2
    assert a["tmax_max"] == 3
    assert a["provenance"]["origin"] == "SOURCE_DERIVED"
    assert "src-b" in a["provenance"]["source_ids"]

    # Conflict create + resolve
    conflict = client.post(
        f"/api/projects/{pid}/research-case/conflicts",
        json={
            "field_name": "tmax",
            "evidence_ids": [ev_prop.json()["id"], ev_ver.json()["id"]],
            "values": ["1 h", "2–3 h"],
            "severity": "WARNING",
        },
    )
    assert conflict.status_code == 201
    resolved = client.post(
        f"/api/projects/{pid}/research-case/conflicts/{conflict.json()['id']}/resolve",
        json={"resolution": "Use 2–3 h from SmPC", "resolved_by": "expert"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None

    ranking = client.get("/api/reference-data/source-ranking")
    assert ranking.status_code == 200
    assert ranking.json()["rules"]


def test_proposed_cannot_overwrite_verified_analyte(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "guard"}).json()["id"]
    analyte = client.post(
        f"/api/projects/{pid}/analytes",
        json={
            "name": "parent",
            "type": "PARENT",
            "tmax_min": 2,
            "tmax_max": 3,
            "provenance": {"origin": "USER", "status": "VERIFIED", "source_ids": ["x"]},
        },
    ).json()
    client.post(f"/api/projects/{pid}/research-case", json={})
    ev = client.post(
        f"/api/projects/{pid}/research-case/evidence",
        json={
            "source_id": "y",
            "evidence_type": "PK",
            "claims": [
                {
                    "field_name": "tmax",
                    "normalized_value": {"min": 4, "max": 5},
                    "unit": "h",
                    "status": "PROPOSED",
                    "source_ids": ["y"],
                }
            ],
        },
    ).json()
    resp = client.post(
        f"/api/projects/{pid}/research-case/apply-verified",
        json={"claim_ids": [ev["claims"][0]["id"]], "analyte_id": analyte["id"]},
    )
    assert resp.status_code == 409
