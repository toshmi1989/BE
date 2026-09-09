"""Phase 4 statistics API integration + Bosutinib golden (known source facts only)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_project(client: TestClient) -> tuple[str, str]:
    project = client.post("/api/projects", json={"name": "Bosutinib stats"}).json()
    pid = project["id"]
    design = client.post(
        f"/api/projects/{pid}/design",
        json={
            "type": "CROSSOVER_2X2",
            "periods": 2,
            "sequences": [["T", "R"], ["R", "T"]],
            "food_condition": "FED",
            "decision_status": "PROPOSED",
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    assert design.status_code == 201, design.text
    analyte = client.post(
        f"/api/projects/{pid}/analytes",
        json={
            "name": "bosutinib",
            "type": "PARENT",
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    assert analyte.status_code == 201, analyte.text
    return pid, analyte.json()["id"]


def test_cv_crud_pool_select_sample_size(client: TestClient) -> None:
    pid, analyte_id = _seed_project(client)

    cv1 = client.post(
        f"/api/projects/{pid}/statistics/cv",
        json={
            "source_id": "gopineedu-2023",
            "study_name": "Bosutinib 100 mg FED BE",
            "analyte_id": analyte_id,
            "parameter": "Cmax",
            "design": "CROSSOVER_2X2",
            "condition": "FED",
            "dose": "100 mg",
            "n_total": 46,
            "n_be_analysis": 40,
            "cv_value": 25.0,
            "cv_unit": "percent",
            "evidence": [
                {
                    "source_id": "gopineedu-2023",
                    "page": 1,
                    "section": "results",
                    "extracted_text": "example CV placeholder for API test",
                    "confidence": 0.5,
                    "status": "PROPOSED",
                }
            ],
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    assert cv1.status_code == 201, cv1.text
    cv1_id = cv1.json()["id"]

    cv2 = client.post(
        f"/api/projects/{pid}/statistics/cv",
        json={
            "source_id": "src-2",
            "analyte_id": analyte_id,
            "parameter": "Cmax",
            "design": "CROSSOVER_2X2",
            "condition": "FED",
            "dose": "100 mg",
            "n_total": 36,
            "n_be_analysis": 32,
            "cv_value": 30.0,
            "provenance": {"origin": "SOURCE_DERIVED", "status": "PROPOSED"},
        },
    )
    assert cv2.status_code == 201
    cv2_id = cv2.json()["id"]

    listed = client.get(f"/api/projects/{pid}/statistics/cv")
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    pool = client.post(
        f"/api/projects/{pid}/statistics/cv/pool",
        json={"cv_study_ids": [cv1_id, cv2_id]},
    )
    assert pool.status_code == 200, pool.text
    assert pool.json()["status"] == "PROPOSED"
    assert pool.json()["pooled_cv"] is not None
    pool_id = pool.json()["id"]

    incompatible = client.post(
        f"/api/projects/{pid}/statistics/cv",
        json={
            "source_id": "src-auc",
            "analyte_id": analyte_id,
            "parameter": "AUC0_t",
            "design": "CROSSOVER_2X2",
            "condition": "FED",
            "n_be_analysis": 40,
            "cv_value": 22.0,
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
    assert incompatible.status_code == 201
    bad_pool = client.post(
        f"/api/projects/{pid}/statistics/cv/pool",
        json={"cv_study_ids": [cv1_id, incompatible.json()["id"]]},
    )
    assert bad_pool.status_code == 200
    assert bad_pool.json()["status"] == "NEEDS_REVIEW"
    assert bad_pool.json()["pooled_cv"] is None

    select = client.post(
        f"/api/projects/{pid}/statistics/cv/select",
        json={
            "selection_method": "POOLED",
            "pool_id": pool_id,
            "cv_study_ids": [cv1_id, cv2_id],
        },
    )
    assert select.status_code == 200, select.text
    assert select.json()["selected_cv"] is not None

    cfg = client.get(f"/api/projects/{pid}/statistics/config")
    assert cfg.status_code == 200
    assert cfg.json()["alpha"] == 0.05
    assert cfg.json()["power"] == 0.8
    assert cfg.json()["rule_id"] == "STAT.DEFAULTS.ABE.v1"

    ss = client.post(
        f"/api/projects/{pid}/statistics/sample-size",
        json={
            "design_type": "CROSSOVER_2X2",
            "dropout_pct": 10,
            "reserve_pct": 0,
            "created_by": "test",
        },
    )
    assert ss.status_code == 200, ss.text
    body = ss.json()
    assert body["status"] == "PROPOSED"
    assert body["evaluable_n"] % 2 == 0
    assert body["randomized_n"] >= body["evaluable_n"]
    assert body["algorithm_version"]
    assert body["inputs_snapshot"]["selected_cv_percent"] is not None

    ss2 = client.post(
        f"/api/projects/{pid}/statistics/sample-size",
        json={"design_type": "CROSSOVER_2X2", "dropout_pct": 10},
    )
    assert ss2.json()["evaluable_n"] == body["evaluable_n"]
    assert ss2.json()["randomized_n"] == body["randomized_n"]

    hist = client.get(f"/api/projects/{pid}/statistics/sample-size")
    assert len(hist.json()) >= 2

    validation = client.post(f"/api/projects/{pid}/statistics/validate")
    assert validation.status_code == 200
    assert validation.json()["blocking"] is False

    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["cv_selection"]["selected_cv"] is not None
    assert detail["sample_size"]["evaluable_n"] == body["evaluable_n"]


def test_ai_cv_cannot_be_verified(client: TestClient) -> None:
    pid, analyte_id = _seed_project(client)
    resp = client.post(
        f"/api/projects/{pid}/statistics/cv",
        json={
            "source_id": "ai-src",
            "analyte_id": analyte_id,
            "parameter": "Cmax",
            "cv_value": 20,
            "provenance": {"origin": "AI_PROPOSED", "status": "VERIFIED"},
        },
    )
    assert resp.status_code == 422


def test_invalid_n_be_rejected(client: TestClient) -> None:
    pid, analyte_id = _seed_project(client)
    resp = client.post(
        f"/api/projects/{pid}/statistics/cv",
        json={
            "source_id": "s",
            "analyte_id": analyte_id,
            "parameter": "Cmax",
            "n_total": 20,
            "n_be_analysis": 25,
            "cv_value": 20,
        },
    )
    assert resp.status_code == 422


def test_bosutinib_golden_known_facts_only(client: TestClient) -> None:
    """Golden scenario from Bosutinib protocol template — invent nothing.

    Known from source DOCX:
    - design: 2×2 crossover, FED
    - planned randomized N = 46
    - alpha=0.05, power=0.8, BE 80–125%
    - CVintra formula documented
    - numeric CVintra for sample-size justification is placeholder (ХХ%) → NEEDS_REVIEW
    """
    pid, analyte_id = _seed_project(client)

    cfg = client.get(f"/api/projects/{pid}/statistics/config").json()
    assert cfg["alpha"] == 0.05
    assert cfg["power"] == 0.8
    assert cfg["be_lower"] == 0.8
    assert cfg["be_upper"] == 1.25

    # Without a numeric CV from source, sample size must not invent one
    validation = client.post(f"/api/projects/{pid}/statistics/validate").json()
    assert validation["blocking"] is True
    codes = {i["code"] for i in validation["issues"]}
    assert "NO_CV" in codes

    # Record protocol-stated planned N as subject plan (not as statistical formula)
    subjects = client.post(
        f"/api/projects/{pid}/subjects",
        json={
            "target_evaluable_n": None,
            "planned_randomized_n": 46,
            "provenance": {
                "origin": "SOURCE_DERIVED",
                "status": "PROPOSED",
                "notes": "Protocol synopsis: randomized volunteers = 46; CV% placeholder ХХ — not invented",
            },
        },
    )
    assert subjects.status_code == 201
    assert subjects.json()["planned_randomized_n"] == 46

    # Attempting sample size without selected CV fails
    ss = client.post(
        f"/api/projects/{pid}/statistics/sample-size",
        json={"design_type": "CROSSOVER_2X2"},
    )
    assert ss.status_code == 422

    # Expert may enter CV only with NEEDS_REVIEW — not VERIFIED
    select = client.post(
        f"/api/projects/{pid}/statistics/cv/select",
        json={"selection_method": "EXPERT_SELECTED", "expert_cv": 30.0},
    )
    assert select.status_code == 200
    assert select.json()["status"] == "NEEDS_REVIEW"
    assert select.json()["selected_cv"] == 30.0

    # Calculation remains PROPOSED (never auto-VERIFIED)
    calc = client.post(
        f"/api/projects/{pid}/statistics/sample-size",
        json={"design_type": "CROSSOVER_2X2", "selected_cv": 30.0, "expected_ratio": 0.95},
    )
    assert calc.status_code == 200
    assert calc.json()["status"] == "PROPOSED"
    assert calc.json()["evaluable_n"] is not None
    # Do not assert equality with hardcoded 46 — that is protocol narrative, not engine output
    assert calc.json()["evaluable_n"] != 46 or calc.json()["inputs_snapshot"]["selected_cv_percent"] == 30.0
