"""Phase 29.2 — reading variability out of PK tables.

The number an FDA label or a BE article states for CVintra almost always sits in
a table cell, not in a sentence. These tests pin what the reader may conclude
from a grid: a cell means something only together with its row and its column,
the within/between qualifier is read and never guessed, and a row that does not
line up with the header is left unread rather than attributed to a neighbour.
"""

from __future__ import annotations

import pytest

from app.domain.research_deep_read import deep_read_task_sources
from app.domain.research_evidence_engine import create_tasks_from_gaps
from app.domain.research_evidence_store import clear_research_evidence_store, list_claims
from app.domain.research_real_search import store_search_results
from app.domain.research_search_result import ResearchSearchResult
from app.domain.research_tables import (
    cv_table_findings,
    html_text_with_tables,
    split_table_rows,
)

STUDY = "TABLE-READ-STUDY"

# An FDA clinical pharmacology review states the variability in its own column
FDA_TABLE = """
Table 3. Pharmacokinetic parameters of upadacitinib after a single 15 mg dose
Parameter                Test        Reference     Intra-subject CV (%)
Cmax (ng/mL)             45.2        41.0          24.5
AUC0-t (ng*h/mL)         310.5       298.7         18.2
Tmax (h)                 2.0         2.0           NR
"""

# A product label states the geometric mean with the CV in brackets
LABEL_TABLE = """
Table 1. Summary of pharmacokinetics of upadacitinib
Parameter | Geometric Mean (CV%) | N
Cmax (ng/mL) | 47.3 (31.4) | 24
AUC0-inf (ng*h/mL) | 402.1 (22.8) | 24
"""

# A review tabulates between-subject variability — a different quantity
BETWEEN_TABLE = """
Table 5. Between-subject variability of upadacitinib exposure
Parameter | CV (%)
Cmax | 35.1
AUC0-t | 28.4
"""

# Nothing in this table says which variability it is
UNQUALIFIED_TABLE = """
Table 2. Pharmacokinetics of upadacitinib
Parameter | Mean | CV (%)
Cmax | 45.2 | 24.5
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


def _task(text_sources: list[ResearchSearchResult], code: str = "MISSING_CVINTRA"):
    task = create_tasks_from_gaps(STUDY, [{"code": code, "title": code}])[0]
    store_search_results(task.id, text_sources)
    return task


def _read(text: str, url: str = "https://fda.test/review.pdf"):
    task = _task([_source(url, "Clinical Pharmacology Review")])
    out = deep_read_task_sources(
        task.id,
        field_paths=["cv_intra"],
        context={"active_substance": "upadacitinib"},
        fetcher=lambda u, client=None: (None, text),
    )
    return task, out


@pytest.fixture(autouse=True)
def _clean():
    clear_research_evidence_store()
    yield
    clear_research_evidence_store()


def test_a_row_is_read_as_cells_not_as_a_sentence():
    blocks = split_table_rows(FDA_TABLE)

    assert len(blocks) == 1
    assert blocks[0].caption.startswith("Table 3.")
    assert blocks[0].rows[1] == ["Cmax (ng/mL)", "45.2", "41.0", "24.5"]


def test_prose_is_not_mistaken_for_a_table():
    prose = (
        "The intra-subject CV of upadacitinib Cmax was 24.5% in the pivotal study.\n"
        "Exposure increased proportionally with dose.\n"
    )

    assert split_table_rows(prose) == []


def test_the_cv_column_is_read_per_pk_parameter():
    findings = cv_table_findings(FDA_TABLE)
    by_parameter = {f.pk_parameter: f for f in findings}

    assert by_parameter["Cmax"].value == 24.5
    assert by_parameter["AUC0-t"].value == 18.2
    assert all(f.variability_type == "WITHIN_SUBJECT" for f in findings)
    # "NR" states no number, so Tmax yields nothing
    assert "Tmax" not in by_parameter


def test_the_excerpt_names_the_row_and_the_column():
    finding = next(f for f in cv_table_findings(FDA_TABLE) if f.pk_parameter == "Cmax")

    assert "Cmax (ng/mL)" in finding.excerpt
    assert "Intra-subject CV (%)" in finding.excerpt
    assert "24.5" in finding.excerpt
    assert "Table 3." in finding.excerpt


def test_a_mean_with_the_cv_in_brackets_is_read_as_the_cv():
    """'Geometric Mean (CV%)' states two numbers; only the bracketed one is the CV."""
    by_parameter = {f.pk_parameter: f for f in cv_table_findings(LABEL_TABLE)}

    assert by_parameter["Cmax"].value == 31.4
    assert by_parameter["AUC0-inf"].value == 22.8


def test_a_column_without_a_qualifier_falls_back_to_the_caption():
    findings = cv_table_findings(BETWEEN_TABLE)

    assert [f.variability_type for f in findings] == ["BETWEEN_SUBJECT", "BETWEEN_SUBJECT"]


def test_a_table_that_never_states_the_variability_type_stays_unknown():
    findings = cv_table_findings(UNQUALIFIED_TABLE)

    assert [f.variability_type for f in findings] == ["UNKNOWN"]


def test_a_row_that_does_not_line_up_with_the_header_is_not_read():
    """A dropped cell shifts the columns — the value would land under a guess."""
    shifted = """
Table 4. Pharmacokinetics
Parameter | Test | Reference | Intra-subject CV (%)
Cmax (ng/mL) | 45.2 | 24.5
"""

    assert cv_table_findings(shifted) == []


def test_a_missing_header_label_shifts_the_columns_by_one():
    """Labels tables often leave the corner cell empty; that offset is known."""
    cornerless = """
Table 6. Intra-subject variability of upadacitinib
| Test | Reference | CV (%)
Cmax (ng/mL) | 45.2 | 41.0 | 24.5
"""

    findings = cv_table_findings(cornerless)

    assert [(f.pk_parameter, f.value) for f in findings] == [("Cmax", 24.5)]


def test_a_range_in_a_cell_stays_a_range():
    ranged = """
Table 7. Intra-subject variability of upadacitinib
Parameter | CV (%)
Cmax | 20-35
"""

    finding = cv_table_findings(ranged)[0]

    assert finding.value is None
    assert (finding.range_low, finding.range_high) == (20.0, 35.0)


def test_a_transposed_table_is_read_too():
    transposed = """
Table 8. Intra-subject variability of upadacitinib
Statistic | Cmax | AUC0-t
Geometric mean | 45.2 | 310.5
Intra-subject CV (%) | 24.5 | 18.2
"""

    by_parameter = {f.pk_parameter: f.value for f in cv_table_findings(transposed)}

    assert by_parameter == {"Cmax": 24.5, "AUC0-t": 18.2}


def test_a_figure_that_cannot_be_a_percentage_is_not_read_as_one():
    absurd = """
Table 9. Intra-subject variability by study year
Parameter | Year | CV (%)
Cmax | 2019 | 24.5
"""

    assert [f.value for f in cv_table_findings(absurd)] == [24.5]


def test_an_html_table_keeps_its_grid():
    html = (
        "<p>Table 2. Intra-subject variability</p>"
        "<table><tr><th>Parameter</th><th>CV (%)</th></tr>"
        "<tr><td>Cmax</td><td>24.5</td></tr></table>"
    )

    text = html_text_with_tables(html)

    assert "Cmax | 24.5" in text
    assert [(f.pk_parameter, f.value) for f in cv_table_findings(text)] == [("Cmax", 24.5)]


def test_a_tabulated_cv_becomes_a_proposal_for_the_writer():
    task, out = _read(FDA_TABLE)

    assert out["table_values"] >= 2
    proposals = [c for c in list_claims(task.id) if c.field_path == "cv_intra"]
    values = sorted(c.value for c in proposals)
    assert values == [18.2, 24.5]
    assert all(c.verification_status == "PROPOSED" for c in proposals)
    assert out["study_mutated"] is False
    assert out["automatic_verifications"] == 0


def test_two_parameters_sharing_one_cv_value_are_both_kept():
    same = """
Table 10. Intra-subject variability of upadacitinib
Parameter | CV (%)
Cmax | 24.5
AUC0-t | 24.5
"""

    task, _out = _read(same)

    parameters = {c.cvintra["PK_parameter"] for c in list_claims(task.id) if c.cvintra}
    assert parameters == {"Cmax", "AUC0-t"}


def test_a_tabulated_between_subject_cv_is_not_offered_as_cvintra():
    task, _out = _read(BETWEEN_TABLE)

    claims = [c for c in list_claims(task.id) if c.cvintra]
    assert claims
    assert all(c.cvintra["variability_type"] == "BETWEEN_SUBJECT" for c in claims)
    assert all(c.usability == "NOT_USABLE_FOR_DECISION" for c in claims)
    assert not [c for c in claims if c.field_path == "cv_intra"]


def test_reading_the_same_table_twice_adds_nothing():
    task = _task([_source("https://fda.test/review.pdf", "Review")])
    args = {
        "field_paths": ["cv_intra"],
        "context": {"active_substance": "upadacitinib"},
        "fetcher": lambda u, client=None: (None, FDA_TABLE),
    }

    first = deep_read_task_sources(task.id, **args)
    second = deep_read_task_sources(task.id, **args)

    assert first["new_claim_count"] >= 2
    assert second["new_claim_count"] == 0
