"""Expected (planning) vs observed PK parameters."""

from app.domain.expected_pk import (
    resolve_verified_expected_half_life,
    resolve_verified_expected_tmax,
    tmax_role_note,
)


def test_expected_tmax_requires_verified():
    facts = {"pk.expected_tmax": "2–4 h", "pk.Tmax": 3.0}
    assert resolve_verified_expected_tmax(facts, {}) is None
    assert resolve_verified_expected_tmax(facts, {"pk.expected_tmax": "PROPOSED"}) is None
    assert resolve_verified_expected_tmax(facts, {"pk.expected_tmax": "VERIFIED"}) == "2–4 h"


def test_legacy_pk_tmax_verified_counts_as_planning():
    facts = {"pk.Tmax": 2.5}
    assert resolve_verified_expected_tmax(facts, {"pk.Tmax": "VERIFIED"}) == 2.5


def test_observed_tmax_not_used_as_planning():
    facts = {"pk.observed_tmax": 3.1, "results.tmax": 3.1}
    assert resolve_verified_expected_tmax(facts, {"pk.observed_tmax": "VERIFIED"}) is None


def test_half_life_verified():
    facts = {"pk.expected_t_half": 9.0}
    assert resolve_verified_expected_half_life(facts, {"pk.expected_t_half": "VERIFIED"}) == 9.0


def test_role_notes_distinguish():
    n = tmax_role_note()
    assert "Planning" in n["expected_tmax"] or "planning" in n["expected_tmax"].lower()
    assert "Post-study" in n["observed_tmax"] or "post-study" in n["observed_tmax"].lower()
