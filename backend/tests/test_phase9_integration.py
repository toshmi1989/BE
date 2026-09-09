"""Phase 9 DOCX integration: Study → ProtocolDraft → DOCX."""

from __future__ import annotations

import io

from docx import Document
from fastapi.testclient import TestClient

from app.domain.docx_profile import TEMPLATE_CHECKSUM_SHA256, get_template_profile
from app.domain.document_ingest import sha256_hex


def _configure_docx_ready(client: TestClient) -> str:
    project = client.post("/api/projects", json={"name": "Phase9 DOCX"}).json()
    pid = project["id"]

    client.put(
        f"/api/projects/{pid}/study",
        json={
            "protocol_number": "BE-BOS-400-001",
            "title": "Bosutinib 400 mg BE",
            "short_title": "Bosutinib BE",
            "version": "1.0",
            "provenance": {"origin": "USER", "status": "PROPOSED"},
        },
    )
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
    client.post(f"/api/projects/{pid}/washout/calculate", json={"selected_value": 5, "selected_unit": "day"})
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


def test_docx_build_draft_and_download(client: TestClient) -> None:
    pid = _configure_docx_ready(client)
    assert client.post(f"/api/projects/{pid}/protocol/build", json={}).status_code == 200

    built = client.post(
        f"/api/projects/{pid}/protocol/docx/build",
        json={"mode": "DRAFT", "ensure_protocol": True},
    )
    assert built.status_code == 200, built.text
    body = built.json()
    assert body["status"] == "READY", body
    assert body["checksum"]
    assert body["template_version"]
    assert body["generator_version"]
    assert body["storage_key"]
    assert not str(body.get("storage_key", "")).startswith("C:")
    assert body["validation_report"]["table_count"] == 33

    status = client.get(f"/api/projects/{pid}/protocol/docx/status")
    assert status.status_code == 200
    assert status.json()["latest"]["id"] == body["id"]

    validation = client.get(f"/api/projects/{pid}/protocol/docx/validation")
    assert validation.status_code == 200

    download = client.get(f"/api/projects/{pid}/protocol/docx/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert len(download.content) > 1000
    Document(io.BytesIO(download.content))
    assert sha256_hex(get_template_profile().template_path().read_bytes()) == TEMPLATE_CHECKSUM_SHA256


def test_final_blocked_without_sponsor(client: TestClient) -> None:
    pid = _configure_docx_ready(client)
    built = client.post(
        f"/api/projects/{pid}/protocol/docx/build",
        json={"mode": "FINAL", "ensure_protocol": True},
    )
    assert built.status_code == 200, built.text
    assert built.json()["status"] == "BLOCKED"
    assert built.json()["blocking_reasons"]
    assert any(
        "sponsor" in str(r).lower() or "unresolved" in str(r).lower()
        for r in built.json()["blocking_reasons"]
    )


def test_empty_project_docx_blocked(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "empty-docx"}).json()["id"]
    built = client.post(
        f"/api/projects/{pid}/protocol/docx/build",
        json={"mode": "DRAFT", "ensure_protocol": True},
    )
    assert built.status_code == 200
    assert built.json()["status"] in {"BLOCKED", "FAILED"}


def test_versions_not_overwritten(client: TestClient) -> None:
    pid = _configure_docx_ready(client)
    a = client.post(f"/api/projects/{pid}/protocol/docx/build", json={"mode": "DRAFT"}).json()
    b = client.post(f"/api/projects/{pid}/protocol/docx/build", json={"mode": "DRAFT"}).json()
    assert a["id"] != b["id"]
    assert a["filename"] != b["filename"]
    assert a["storage_key"] != b["storage_key"]
