"""Phase 29.1 — reading the source itself, not the search snippet.

A search result page states the title; the number lives inside the PDF. These
tests pin the reading rules that keep proposals honest: a value must be stated
next to its parameter, within-subject and between-subject stay separate, and a
document that never names the substance is marked as such.
"""

from __future__ import annotations

import pytest

from app.domain.research_deep_read import (
    FIELD_PATTERNS,
    deep_read_task_sources,
    relevant_passages,
)
from app.domain.research_evidence_engine import create_tasks_from_gaps
from app.domain.research_evidence_store import clear_research_evidence_store, list_claims
from app.domain.research_http import ResearchHttpError
from app.domain.research_real_search import store_search_results
from app.domain.research_search_result import ResearchSearchResult

STUDY = "DEEP-READ-STUDY"

FDA_TEXT = """
Clinical Pharmacology Review — upadacitinib
Accumulation Following QD dosing, steady state was achieved within 4 days.
In healthy subjects, the between-subject
variability (CV %) of upadacitinib AUC and Cmax was approximately
20% to 35% for the clinically relevant regimens.
Based on population PK analysis, the between-subject variability for CL/F
is estimated to be 37% in RA patients.
"""

BE_STUDY_TEXT = """
Bioequivalence study of upadacitinib extended-release tablets.
A 2x2 crossover study in 24 healthy volunteers under fasting conditions
reported an intra-subject CV of 18.4% for Cmax.
Median Tmax was 2-4 hours after single dosing.
"""

OTHER_DRUG_TEXT = """
Clinical Pharmacology Review — tofacitinib
Observed intra-subject variability in Cmax was 7% across the studied doses.
"""


def _source(url: str, title: str, priority: str = "OFFICIAL_REGULATORY") -> ResearchSearchResult:
    return ResearchSearchResult(
        title=title,
        url=url,
        provider="WEB",
        snippet="",
        source_type="REGULATORY",
        priority_class=priority,
    )


def _task(sources: list[ResearchSearchResult], code: str = "MISSING_CVINTRA"):
    tasks = create_tasks_from_gaps(STUDY, [{"code": code, "title": code}])
    task = tasks[0]
    store_search_results(task.id, sources)
    return task


@pytest.fixture(autouse=True)
def _clean():
    clear_research_evidence_store()
    yield
    clear_research_evidence_store()


def test_a_mention_without_a_number_is_not_a_passage():
    text = "The intra-subject variability of statins is comparable across formulations."
    assert relevant_passages(text, FIELD_PATTERNS["cv_intra"]) == []


def test_line_wrapped_pdf_text_is_read_as_running_text():
    passages = relevant_passages(FDA_TEXT, FIELD_PATTERNS["cv_intra"])
    assert passages, "line breaks must not hide the sentence"
    assert "20% to 35%" in passages[0]
    assert "\n" not in passages[0]


def test_between_subject_cv_never_becomes_cvintra():
    task = _task([_source("https://fda.test/review.pdf", "Clinical Pharmacology Review")])

    out = deep_read_task_sources(
        task.id,
        field_paths=["cv_intra"],
        context={"active_substance": "upadacitinib"},
        fetcher=lambda url, client=None: (None, FDA_TEXT),
    )

    assert out["new_claim_count"] >= 1
    cv = [c for c in list_claims(task.id) if c.cvintra]
    assert cv, "the stated variability must be recorded"
    assert all(c.field_path == "cv_between" for c in cv)
    assert all(c.cvintra["variability_type"] == "BETWEEN_SUBJECT" for c in cv)
    assert all(c.usability == "NOT_USABLE_FOR_DECISION" for c in cv)


def test_a_stated_range_stays_a_range():
    task = _task([_source("https://fda.test/review.pdf", "Review")])

    deep_read_task_sources(
        task.id,
        field_paths=["cv_intra"],
        context={"active_substance": "upadacitinib"},
        fetcher=lambda url, client=None: (None, FDA_TEXT),
    )

    claim = next(c for c in list_claims(task.id) if c.cvintra)
    assert claim.value is None, "20% to 35% must not collapse into one number"
    assert claim.cvintra["CV_range_low"] == 20.0
    assert claim.cvintra["CV_range_high"] == 35.0
    assert "20" in claim.excerpt and "35" in claim.excerpt


def test_a_range_written_with_one_percent_sign_is_still_a_range():
    """Reviews write "(i.e., 5-7%)" — one number would be an invented precision."""
    task = _task([_source("https://fda.test/review.pdf", "Review")])

    deep_read_task_sources(
        task.id,
        field_paths=["cv_intra"],
        context={"active_substance": "upadacitinib"},
        fetcher=lambda url, client=None: (
            None,
            "Observed intra-subject variability in AUC and Cmax for upadacitinib was\n"
            "similar between healthy subjects (i.e., 5-7%) and patients.",
        ),
    )

    claim = next(c for c in list_claims(task.id) if c.field_path == "cv_intra")
    assert claim.value is None
    assert (claim.cvintra["CV_range_low"], claim.cvintra["CV_range_high"]) == (5.0, 7.0)


def test_within_subject_cv_is_proposed_with_the_sentence_that_states_it():
    task = _task([_source("https://journal.test/be-study", "BE study", "PEER_REVIEWED")])

    deep_read_task_sources(
        task.id,
        field_paths=["cv_intra"],
        context={"active_substance": "upadacitinib"},
        fetcher=lambda url, client=None: (None, BE_STUDY_TEXT),
    )

    claim = next(c for c in list_claims(task.id) if c.field_path == "cv_intra")
    assert claim.value == 18.4
    assert claim.cvintra["PK_parameter"] == "Cmax"
    assert claim.verification_status == "PROPOSED"
    assert "18.4" in claim.excerpt


def test_value_from_a_document_that_never_names_the_substance_is_flagged():
    task = _task([_source("https://fda.test/other.pdf", "Another review")])

    deep_read_task_sources(
        task.id,
        field_paths=["cv_intra"],
        context={"active_substance": "upadacitinib"},
        fetcher=lambda url, client=None: (None, OTHER_DRUG_TEXT),
    )

    claim = next(c for c in list_claims(task.id) if c.cvintra)
    assert claim.applicability == "LOW"
    assert "upadacitinib" in claim.applicability_reason


def test_an_unreachable_source_is_reported_and_does_not_stop_the_read():
    task = _task(
        [
            _source("https://paywall.test/article", "Paywalled article"),
            _source("https://journal.test/be-study", "BE study", "PEER_REVIEWED"),
        ]
    )

    def _fetch(url, client=None):
        if "paywall" in url:
            raise ResearchHttpError("Access denied (403)", kind="ACCESS_DENIED")
        return None, BE_STUDY_TEXT

    out = deep_read_task_sources(
        task.id,
        field_paths=["cv_intra"],
        context={"active_substance": "upadacitinib"},
        fetcher=_fetch,
    )

    assert [f["error"] for f in out["sources_failed"]] == ["ACCESS_DENIED"]
    assert [r["url"] for r in out["sources_read"]] == ["https://journal.test/be-study"]
    assert out["new_claim_count"] >= 1


def test_reading_the_same_source_twice_adds_nothing():
    task = _task([_source("https://journal.test/be-study", "BE study", "PEER_REVIEWED")])
    args = {
        "field_paths": ["cv_intra"],
        "context": {"active_substance": "upadacitinib"},
        "fetcher": lambda url, client=None: (None, BE_STUDY_TEXT),
    }

    first = deep_read_task_sources(task.id, **args)
    second = deep_read_task_sources(task.id, **args)

    assert first["new_claim_count"] >= 1
    assert second["new_claim_count"] == 0


def test_nothing_is_verified_by_reading():
    task = _task([_source("https://journal.test/be-study", "BE study", "PEER_REVIEWED")])

    out = deep_read_task_sources(
        task.id,
        field_paths=["cv_intra"],
        context={"active_substance": "upadacitinib"},
        fetcher=lambda url, client=None: (None, BE_STUDY_TEXT),
    )

    assert out["automatic_verifications"] == 0
    assert out["study_mutated"] is False
    assert all(c.verification_status == "PROPOSED" for c in list_claims(task.id))
