"""Phase 29 — the gap workflow over HTTP, exactly as the writer UI calls it."""

from __future__ import annotations

from fastapi.testclient import TestClient

STUDY = "UPDCB-02-BE-2026"


def _bind_golden(client: TestClient) -> None:
    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "gaps-api"},
    )
    assert wf.status_code == 200, wf.text


def _gap(client: TestClient, code: str) -> dict:
    body = client.get(f"/api/studies/{STUDY}/gaps").json()
    return next((g for g in body["gaps"] if g["code"] == code), None)


def test_gaps_listed_after_analysis(client: TestClient):
    _bind_golden(client)
    body = client.get(f"/api/studies/{STUDY}/gaps").json()
    assert body["gaps"], "expected gaps for the golden package"
    assert body["counts"]["total"] == len(body["gaps"])


def test_research_button_returns_proposals(client: TestClient):
    _bind_golden(client)
    assert _gap(client, "MISSING_TMAX_FOR_SAMPLING")["status"] == "OPEN"

    r = client.post(
        f"/api/studies/{STUDY}/gaps/MISSING_TMAX_FOR_SAMPLING/research",
        json={"active_substance": "upadacitinib", "use_mock_provider": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["research_task_id"]
    assert body["status"] == "OK"
    assert body["found"] >= 1
    assert body["message"]
    assert body["gap"] is not None, "gap disappeared right after the search"
    assert body["gap"]["proposals"], "search produced no proposals for the UI"
    assert body["gap"]["status"] == "PROPOSED"

    # Proposals must survive the next read — not only the response of the POST
    again = _gap(client, "MISSING_TMAX_FOR_SAMPLING")
    assert again["proposals"], "proposals lost between requests"


def test_research_reports_when_web_search_is_off(client: TestClient, monkeypatch):
    """A search that cannot run must say so — never look like a dead button."""
    from app.domain import research_http

    _bind_golden(client)
    real_settings = research_http.research_http_settings()
    monkeypatch.setattr(
        research_http,
        "research_http_settings",
        lambda: {**real_settings, "enabled": False},
    )

    r = client.post(
        f"/api/studies/{STUDY}/gaps/MISSING_TMAX_FOR_SAMPLING/research",
        json={"active_substance": "upadacitinib"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "SEARCH_UNAVAILABLE"
    assert body["found"] == 0
    assert "вручную" in body["message"]
    assert body["gap"] is not None, "the gap must stay visible with its manual option"


def test_web_search_extracts_a_value_and_lists_its_sources(client: TestClient, monkeypatch):
    """The default path is a real source search, not the deterministic mock."""
    from app.domain import research_real_web

    _bind_golden(client)
    monkeypatch.setattr(
        research_real_web,
        "default_duckduckgo_search",
        lambda query, client=None: [
            {
                "title": "Clinical pharmacokinetics of upadacitinib",
                "url": "https://example.test/pk-review",
                "snippet": "Median Tmax was 2-4 hours and t1/2 = 9.5 h after single dosing.",
            }
        ],
    )

    r = client.post(
        f"/api/studies/{STUDY}/gaps/MISSING_TMAX_FOR_SAMPLING/research",
        json={"active_substance": "upadacitinib"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "WEB"
    assert body["status"] == "OK"
    assert body["found"] >= 1
    assert body["sources"] and body["sources"][0]["url"] == "https://example.test/pk-review"
    assert body["gap"]["status"] == "PROPOSED"
    assert body["gap"]["proposals"][0]["verification_status"] == "PROPOSED"


def test_web_search_with_sources_but_no_value_says_so(client: TestClient, monkeypatch):
    from app.domain import research_real_web

    _bind_golden(client)
    monkeypatch.setattr(
        research_real_web,
        "default_duckduckgo_search",
        lambda query, client=None: [
            {
                "title": "Product page",
                "url": "https://example.test/product",
                "snippet": "Prescribing information for healthcare professionals.",
            }
        ],
    )

    body = client.post(
        f"/api/studies/{STUDY}/gaps/MISSING_TMAX_FOR_SAMPLING/research",
        json={"active_substance": "upadacitinib"},
    ).json()
    assert body["status"] == "SOURCES_ONLY"
    assert body["found"] == 0
    assert body["sources"]
    assert "вручную" in body["message"]


def test_research_without_results_tells_the_writer(client: TestClient, monkeypatch):
    from app.domain import research_real_web

    _bind_golden(client)
    monkeypatch.setattr(
        research_real_web,
        "default_duckduckgo_search",
        lambda query, client=None: [],
    )

    r = client.post(
        f"/api/studies/{STUDY}/gaps/MISSING_TMAX_FOR_SAMPLING/research",
        json={"active_substance": "upadacitinib"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "WEB"
    assert body["status"] == "NOTHING_FOUND"
    assert body["found"] == 0
    assert body["message"]


def test_research_reports_a_failed_web_search(client: TestClient, monkeypatch):
    from app.domain import research_real_web
    from app.domain.research_http import ResearchHttpError

    _bind_golden(client)

    def _boom(query, client=None):
        raise ResearchHttpError("Request timeout", kind="TIMEOUT")

    monkeypatch.setattr(research_real_web, "default_duckduckgo_search", _boom)

    r = client.post(
        f"/api/studies/{STUDY}/gaps/MISSING_TMAX_FOR_SAMPLING/research",
        json={"active_substance": "upadacitinib"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "SEARCH_FAILED"
    assert "TIMEOUT" in body["message"]
    assert body["found"] == 0
    assert _gap(client, "MISSING_TMAX_FOR_SAMPLING")["status"] == "OPEN"


def test_verify_proposal_unblocks_dependent_step(client: TestClient):
    _bind_golden(client)
    client.post(
        f"/api/studies/{STUDY}/gaps/MISSING_TMAX_FOR_SAMPLING/research",
        json={"active_substance": "upadacitinib", "use_mock_provider": True},
    )
    gap = _gap(client, "MISSING_TMAX_FOR_SAMPLING")
    claim_id = gap["proposals"][0]["claim_id"]

    v = client.post(
        f"/api/studies/{STUDY}/gaps/MISSING_TMAX_FOR_SAMPLING/verify",
        json={"claim_id": claim_id, "reviewer": "writer@example.com"},
    )
    assert v.status_code == 200, v.text
    assert "SAMPLING" in v.json()["recomputed_domains"]
    assert _gap(client, "MISSING_TMAX_FOR_SAMPLING") is None


def test_manual_entry_over_http(client: TestClient):
    _bind_golden(client)
    r = client.post(
        f"/api/studies/{STUDY}/gaps/MISSING_HALF_LIFE_FOR_WASHOUT/resolve-manual",
        json={
            "value": "9.5",
            "rationale": "SmPC оригинального препарата, раздел 5.2",
            "actor": "writer@example.com",
        },
    )
    assert r.status_code == 200, r.text
    assert "WASHOUT" in r.json()["recomputed_domains"]
    assert _gap(client, "MISSING_HALF_LIFE_FOR_WASHOUT") is None
