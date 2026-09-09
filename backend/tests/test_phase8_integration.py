"""Phase 8 protocol assembly API integration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _configure_complete(client: TestClient, *, food: str = "FED", extra_analyte: bool = False) -> str:
    project = client.post("/api/projects", json={"name": "Phase8 complete"}).json()
    pid = project["id"]

    client.put(
        f"/api/projects/{pid}/product",
        json={
            "trade_name": "Bosutinib-T",
            "inn": "bosutinib",
            "dosage": "400 mg",
            "dosage_form": "tablet",
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
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
            "food_condition": food,
            "decision_status": "PROPOSED",
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    meal = "HIGH_CALORIE" if food == "FED" else None
    client.post(
        f"/api/projects/{pid}/food",
        json={
            "condition": food,
            "meal_type": meal,
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
    if extra_analyte:
        client.post(
            f"/api/projects/{pid}/analytes",
            json={
                "name": "metabolite-m",
                "type": "ACTIVE_METABOLITE",
                "tmax_min": 3,
                "tmax_max": 5,
                "tmax_unit": "h",
                "half_life_min": 20,
                "half_life_max": 30,
                "half_life_unit": "h",
                "provenance": {"origin": "USER", "status": "PROPOSED"},
            },
        )
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
    client.post(
        f"/api/projects/{pid}/blood-volume/calculate",
        json={
            "blood_volume_per_pk_sample_ml": 5,
            "screening_volume_ml": 15,
            "safety_laboratory_volume_ml": 10,
            "subjects": 28,
        },
    )
    cv = client.post(
        f"/api/projects/{pid}/statistics/cv",
        json={
            "source_id": "src-cv",
            "analyte_id": aid,
            "parameter": "Cmax",
            "design": "CROSSOVER_2X2",
            "condition": food,
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


def test_build_complete_protocol_api(client: TestClient) -> None:
    pid = _configure_complete(client)
    build = client.post(f"/api/projects/{pid}/protocol/build", json={})
    assert build.status_code == 200, build.text
    body = build.json()
    assert body["status"] in {"DRAFT", "READY_FOR_REVIEW", "BLOCKED"}
    assert body["template_version"]
    assert body["generator_version"]
    assert body["sections"]
    assert body["tables"]
    assert body["build_report"]
    assert "ХХ" not in str(body)
    assert "XXX" not in str(body).replace("{{", "").replace("}}", "")

    got = client.get(f"/api/projects/{pid}/protocol")
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]

    sections = client.get(f"/api/projects/{pid}/protocol/sections")
    assert sections.status_code == 200
    codes = {s["section_code"] for s in sections.json()}
    assert "SYNOPSIS" in codes
    assert "4.4.2" in codes
    assert "9.2" in codes

    report = client.get(f"/api/projects/{pid}/protocol/build-report")
    assert report.status_code == 200
    assert "generated_sections" in report.json()

    preview = client.get(f"/api/projects/{pid}/protocol/preview")
    assert preview.status_code == 200
    assert preview.json()["tree"]

    rebuild = client.post(f"/api/projects/{pid}/protocol/sections/4.4.2/rebuild")
    assert rebuild.status_code == 200


def test_blocking_validation_blocks_protocol(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "empty"}).json()
    pid = project["id"]
    build = client.post(f"/api/projects/{pid}/protocol/build", json={})
    assert build.status_code == 200, build.text
    assert build.json()["status"] == "BLOCKED"
    assert build.json()["build_report"]["blocking_issues"]


def test_missing_sampling_blocks_or_unresolved(client: TestClient) -> None:
    pid = _configure_complete(client)
    # wipe sampling by building incomplete project instead
    project = client.post("/api/projects", json={"name": "no-samp"}).json()
    pid2 = project["id"]
    client.put(
        f"/api/projects/{pid2}/reference-product",
        json={
            "trade_name": "Bosulif",
            "inn": "bosutinib",
            "dosage": "400 mg",
            "purchased_status": "UNKNOWN",
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    build = client.post(f"/api/projects/{pid2}/protocol/build", json={})
    assert build.status_code == 200
    assert build.json()["status"] == "BLOCKED"


def test_fed_protocol_differs_from_fasting(client: TestClient) -> None:
    fed_id = _configure_complete(client, food="FED")
    fast_id = _configure_complete(client, food="FASTING")
    fed = client.post(f"/api/projects/{fed_id}/protocol/build", json={}).json()
    fast = client.post(f"/api/projects/{fast_id}/protocol/build", json={}).json()
    fed_sec = next(s for s in fed["sections"] if s["section_code"] == "6.2.1")
    fast_sec = next(s for s in fast["sections"] if s["section_code"] == "6.2.1")
    assert fed_sec["content_blocks"] != fast_sec["content_blocks"]


def test_multi_analyte_protocol(client: TestClient) -> None:
    pid = _configure_complete(client, extra_analyte=True)
    body = client.post(f"/api/projects/{pid}/protocol/build", json={}).json()
    detail = client.get(f"/api/projects/{pid}").json()
    assert len(detail["analytes"]) >= 2
    sec = next(s for s in body["sections"] if s["section_code"] == "7.1")
    assert any(b.get("block_code") == "MULTI_ANALYTE_NOTE" for b in sec["content_blocks"])
    assert "metabolite-m" in str(sec["content_blocks"])


def test_snapshot_reproducible_via_api(client: TestClient) -> None:
    pid = _configure_complete(client)
    a = client.post(f"/api/projects/{pid}/protocol/build", json={}).json()
    b = client.post(f"/api/projects/{pid}/protocol/build", json={}).json()
    assert a["canonical_fingerprint"] == b["canonical_fingerprint"]
    assert a["build_report"]["extras"]["snapshot_fingerprint"] == b["build_report"]["extras"][
        "snapshot_fingerprint"
    ]
