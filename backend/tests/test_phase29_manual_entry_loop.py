"""Diagnostic: the writer types every missing value and expects to reach the DOCX.

Reported from a live session: entered values were lost or not recorded, and the
pipeline kept sending the writer back to the same step, so protocol generation
was never reachable. This walks the API exactly as the UI does — including the
remaining expert gates (dose, statistics, sample size) required by preflight.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

STUDY = "UPDCB-02-BE-2026"

MANUAL_VALUES: dict[str, dict] = {
    "MISSING_TMAX_FOR_SAMPLING": {"value": "2-4", "unit": "ч"},
    "MISSING_HALF_LIFE_FOR_WASHOUT": {"value": 12.0, "unit": "ч"},
    "MISSING_CVINTRA": {"value": 24.5, "unit": "%", "pk_parameter": "Cmax"},
    "MISSING_MEAL_COMPOSITION": {"value": "800-1000", "unit": "ккал"},
    "MISSING_ANALYTE": {"value": "upadacitinib"},
}


def _bind_golden(client: TestClient) -> None:
    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "manual-loop"},
    )
    assert wf.status_code == 200, wf.text


def _panel(client: TestClient) -> dict:
    r = client.get(f"/api/studies/{STUDY}/gaps")
    assert r.status_code == 200, r.text
    return r.json()


def test_manual_values_are_recorded_and_survive_the_next_read(client: TestClient):
    _bind_golden(client)
    before = _panel(client)
    manual_codes = [
        g["code"] for g in before["gaps"] if "MANUAL" in g["resolution"] and g["code"] in MANUAL_VALUES
    ]
    assert manual_codes, f"expected gaps to type into, got {[g['code'] for g in before['gaps']]}"

    for code in manual_codes:
        body = {
            **MANUAL_VALUES[code],
            "rationale": "Значение из SmPC, проверено экспертом",
            "actor": "writer@example.test",
        }
        r = client.post(f"/api/studies/{STUDY}/gaps/{code}/resolve-manual", json=body)
        assert r.status_code == 200, f"{code}: {r.text}"
        out = r.json()
        assert out["applied_fields"], f"{code}: value was not written anywhere"

    after = _panel(client)
    still_open = [g["code"] for g in after["gaps"] if g["status"] == "OPEN"]
    assert not [c for c in still_open if c in manual_codes], (
        f"typed values disappeared: {still_open}"
    )


def test_typed_values_unblock_the_steps_that_needed_them(client: TestClient):
    _bind_golden(client)
    for code, body in MANUAL_VALUES.items():
        client.post(
            f"/api/studies/{STUDY}/gaps/{code}/resolve-manual",
            json={**body, "rationale": "Значение из SmPC", "actor": "writer@example.test"},
        )

    progress = client.get(f"/api/studies/{STUDY}/writer-progress")
    assert progress.status_code == 200, progress.text
    body = progress.json()
    blockers = [b for step in body.get("steps") or [] for b in (step.get("blockers") or [])]
    gap_blockers = [
        b for b in blockers if str(b.get("tab")) == "gaps" and str(b.get("code")) in MANUAL_VALUES
    ]
    assert not gap_blockers, f"steps still blocked by values already typed in: {gap_blockers}"


def test_protocol_generation_is_reachable_after_typing_the_values(client: TestClient):
    _bind_golden(client)
    actor = "writer@example.test"
    for code, body in MANUAL_VALUES.items():
        client.post(
            f"/api/studies/{STUDY}/gaps/{code}/resolve-manual",
            json={**body, "rationale": "Значение из SmPC", "actor": actor},
        )

    # Critical dose conflict remains expert-controlled
    dose = client.post(
        f"/api/studies/{STUDY}/decisions/expert",
        json={
            "question": "reference_product.dose conflict",
            "selected_option": "15 mg",
            "status": "APPROVED",
            "rationale": "SmPC-aligned expert resolution",
        },
    )
    assert dose.status_code == 200, dose.text

    stats = client.post(
        f"/api/studies/{STUDY}/statistics/recompute",
        json={
            "primary_be_parameters": ["Cmax", "AUC0-t"],
            "primary_be_source": "EXPERT_DECISION",
            "analysis_population": "PER_PROTOCOL",
            "analysis_population_source": "EXPERT_DECISION",
            "created_by": actor,
        },
    )
    assert stats.status_code == 200, stats.text
    plan_id = (client.get(f"/api/studies/{STUDY}/statistics").json().get("latest") or {}).get("id")
    assert plan_id
    assert client.post(
        f"/api/statistics/{plan_id}/request-review", json={"reviewer": actor}
    ).status_code == 200
    assert (
        client.post(
            f"/api/statistics/{plan_id}/approve",
            json={"reviewer": actor, "comment": "manual-loop"},
        ).status_code
        == 200
    )

    ss = client.post(
        f"/api/studies/{STUDY}/sample-size/calculate",
        json={
            "design": "STANDARD_2X2_CROSSOVER",
            "parameters": ["Cmax"],
            "expected_ratio": 0.95,
            "expected_ratio_source": "EXPERT_INPUT",
            "power": 0.8,
            "power_source": "EXPERT_INPUT",
            "alpha": 0.05,
            "alpha_source": "EXPERT_INPUT",
            "be_lower": 0.8,
            "be_upper": 1.25,
            "be_limits_source": "EXPLICIT_CONFIGURATION",
            "dropout_percent": 10,
            "dropout_source": "EXPERT_INPUT",
            "inflation_method": "DIVIDE_BY_RETAINMENT_RATE",
            "created_by": actor,
        },
    )
    assert ss.status_code == 200, ss.text
    calc_id = client.get(f"/api/studies/{STUDY}/sample-size/panel").json().get(
        "latest_calculation_id"
    )
    assert calc_id
    assert client.post(
        f"/api/sample-size/calculations/{calc_id}/request-review",
        json={"reviewer": actor},
    ).status_code == 200
    assert (
        client.post(
            f"/api/sample-size/calculations/{calc_id}/approve",
            json={
                "reviewer": actor,
                "decision": "ACCEPT_CALCULATION",
                "comment": "manual-loop",
            },
        ).status_code
        == 200
    )

    # Refresh draft against approved tip (writer re-assemble)
    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={
            "use_golden_fixture": False,
            "prepare_protocol_draft": True,
            "created_by": actor,
        },
    )
    assert wf.status_code == 200, wf.text

    docx = client.post(
        f"/api/studies/{STUDY}/protocol/generate-docx",
        json={"created_by": actor, "confirm_warnings": True},
    )
    assert docx.status_code == 200, f"protocol generation refused: {docx.text}"
