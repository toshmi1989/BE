from __future__ import annotations

from fastapi.testclient import TestClient


def _create_project(client: TestClient, name: str = "Bosutinib BE") -> dict:
    response = client.post("/api/projects", json={"name": name, "description": "Phase 1 test"})
    assert response.status_code == 201, response.text
    return response.json()


def test_project_crud(client: TestClient) -> None:
    created = _create_project(client)
    project_id = created["id"]
    assert created["study"] is not None
    assert created["study"]["provenance"]["status"] == "MISSING"

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert any(p["id"] == project_id for p in listed.json())

    patched = client.patch(f"/api/projects/{project_id}", json={"name": "Bosutinib 400 mg"})
    assert patched.status_code == 200
    assert patched.json()["name"] == "Bosutinib 400 mg"
    assert patched.json()["entity_version"] == 2

    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_entity_graph_and_links(client: TestClient) -> None:
    project = _create_project(client)
    project_id = project["id"]

    # Organization (bioanalytical lab)
    org_resp = client.post(
        f"/api/projects/{project_id}/organizations",
        json={
            "name": "BE Lab",
            "role": "BIOANALYTICAL_LAB",
            "country": "RU",
            "provenance": {"status": "PROPOSED", "origin": "EXPERT_ENTERED"},
        },
    )
    assert org_resp.status_code == 201, org_resp.text
    org = org_resp.json()
    assert org["project_id"] == project_id
    assert org["provenance"]["status"] == "PROPOSED"

    # Sponsor linked to organization
    sponsor_resp = client.put(
        f"/api/projects/{project_id}/sponsor",
        json={
            "name": "Test Sponsor LLC",
            "country": "RU",
            "organization_id": org["id"],
            "provenance": {"status": "NEEDS_REVIEW", "origin": "EXPERT_ENTERED"},
        },
    )
    assert sponsor_resp.status_code == 200, sponsor_resp.text
    sponsor = sponsor_resp.json()
    assert sponsor["organization_id"] == org["id"]
    assert sponsor["project_id"] == project_id

    # Study linked to sponsor
    study_resp = client.put(
        f"/api/projects/{project_id}/study",
        json={
            "title": "Bosutinib 400 mg BE study",
            "protocol_number": "BE-BOS-001",
            "country": "RU",
            "sponsor_id": sponsor["id"],
            "provenance": {
                "status": "PROPOSED",
                "origin": "EXPERT_ENTERED",
                "source_ids": [],
            },
        },
    )
    assert study_resp.status_code == 200, study_resp.text
    study = study_resp.json()
    assert study["sponsor_id"] == sponsor["id"]
    assert study["protocol_number"] == "BE-BOS-001"

    # Cross-project sponsor link must fail
    other = _create_project(client, name="Other")
    bad = client.put(
        f"/api/projects/{other['id']}/study",
        json={"sponsor_id": sponsor["id"]},
    )
    assert bad.status_code == 409
    assert bad.json()["error"]["code"] == "CONFLICT"

    # Source
    source_resp = client.post(
        f"/api/projects/{project_id}/sources",
        json={
            "type": "LABEL",
            "title": "Bosulif SmPC",
            "year": 2024,
            "page": 12,
            "provenance": {"status": "VERIFIED", "origin": "SOURCE_DERIVED", "confidence": 0.9},
        },
    )
    assert source_resp.status_code == 201, source_resp.text
    source = source_resp.json()
    source_id = source["id"]

    # Product with provenance pointing to source
    product_resp = client.put(
        f"/api/projects/{project_id}/product",
        json={
            "trade_name": "Bosutinib",
            "inn": "bosutinib",
            "dosage": "400 mg",
            "dosage_form": "tablet",
            "route": "oral",
            "provenance": {
                "status": "PROPOSED",
                "origin": "SOURCE_DERIVED",
                "source_ids": [source_id],
                "confidence": 0.8,
            },
        },
    )
    assert product_resp.status_code == 200, product_resp.text
    product = product_resp.json()
    assert product["dosage"] == "400 mg"
    assert source_id in product["provenance"]["source_ids"]

    # Reference product
    ref_resp = client.put(
        f"/api/projects/{project_id}/reference-product",
        json={
            "trade_name": "Bosulif",
            "inn": "bosutinib",
            "dosage": "400 mg",
            "purchased_status": "NOT_PURCHASED",
            "provenance": {
                "status": "NEEDS_REVIEW",
                "origin": "EXPERT_ENTERED",
                "source_ids": [source_id],
            },
        },
    )
    assert ref_resp.status_code == 200, ref_resp.text
    ref = ref_resp.json()
    assert ref["trade_name"] == "Bosulif"
    assert ref["purchased_status"] == "NOT_PURCHASED"

    # Aggregate detail contains all relations
    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["study"]["sponsor_id"] == sponsor["id"]
    assert detail["sponsor"]["organization_id"] == org["id"]
    assert detail["product"]["inn"] == "bosutinib"
    assert detail["reference_product"]["trade_name"] == "Bosulif"
    assert len(detail["organizations"]) == 1
    assert len(detail["sources"]) == 1

    # Version snapshot captures linked graph
    version_resp = client.post(
        f"/api/projects/{project_id}/versions",
        json={"label": "phase1-baseline"},
    )
    assert version_resp.status_code == 201, version_resp.text
    snapshot = version_resp.json()["snapshot"]
    assert snapshot["product"]["trade_name"] == "Bosutinib"
    assert snapshot["reference_product"]["trade_name"] == "Bosulif"
    assert snapshot["sponsor"]["organization_id"] == org["id"]
    assert snapshot["study"]["sponsor_id"] == sponsor["id"]
    assert len(snapshot["sources"]) == 1

    versions = client.get(f"/api/projects/{project_id}/versions")
    assert versions.status_code == 200
    assert len(versions.json()) == 1

    # Source update + delete
    upd = client.patch(
        f"/api/projects/{project_id}/sources/{source_id}",
        json={"title": "Bosulif SmPC (updated)", "verified": True},
    )
    assert upd.status_code == 200
    assert upd.json()["entity_version"] == 2

    deleted = client.delete(f"/api/projects/{project_id}/sources/{source_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/projects/{project_id}").json()["sources"] == []


def test_ai_cannot_overwrite_verified_via_api(client: TestClient) -> None:
    project = _create_project(client)
    project_id = project["id"]

    verified = client.put(
        f"/api/projects/{project_id}/product",
        json={
            "trade_name": "Bosutinib",
            "provenance": {"status": "VERIFIED", "origin": "EXPERT_ENTERED"},
        },
    )
    assert verified.status_code == 200
    assert verified.json()["provenance"]["status"] == "VERIFIED"

    blocked = client.put(
        f"/api/projects/{project_id}/product",
        json={
            "trade_name": "Hacked by AI",
            "provenance": {"origin": "AI_PROPOSED", "status": "PROPOSED"},
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "PROVENANCE_GUARD"

    # Expert may still update verified data
    allowed = client.put(
        f"/api/projects/{project_id}/product",
        json={
            "trade_name": "Bosutinib 400 mg",
            "provenance": {"origin": "EXPERT_ENTERED", "status": "VERIFIED"},
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["trade_name"] == "Bosutinib 400 mg"


def test_organization_crud(client: TestClient) -> None:
    project = _create_project(client)
    project_id = project["id"]
    created = client.post(
        f"/api/projects/{project_id}/organizations",
        json={"name": "CRO Alpha", "role": "CRO"},
    ).json()
    org_id = created["id"]

    listed = client.get(f"/api/projects/{project_id}/organizations")
    assert len(listed.json()) == 1

    patched = client.patch(
        f"/api/projects/{project_id}/organizations/{org_id}",
        json={"country": "KZ"},
    )
    assert patched.status_code == 200
    assert patched.json()["country"] == "KZ"
    assert patched.json()["entity_version"] == 2

    deleted = client.delete(f"/api/projects/{project_id}/organizations/{org_id}")
    assert deleted.status_code == 204
