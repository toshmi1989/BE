"""Remaining-work list must name the next click once — not the same gap twice."""

from __future__ import annotations

from app.domain.research_evidence_store import clear_research_evidence_store, put_claim
from app.domain.sample_size_store import put_calculation, reset_sample_size_store
from app.domain.statistics_store import put_plan, reset_statistics_store
from app.domain.workspace_progress import _actionable_blockers
from tests.sample_size_test_helpers import make_verified_cvintra_claim
from app.domain.sample_size_models import SampleSizeCalculationRecord
from app.domain.statistics_models import StatisticsPlan


STUDY = "PROGRESS-REMAINING-STUDY"


def setup_function():
    reset_sample_size_store()
    reset_statistics_store()
    clear_research_evidence_store()


def test_calculated_sample_size_asks_for_approval_not_recalculation():
    put_claim(make_verified_cvintra_claim(study_id=STUDY, cv_value=22, pk_parameter="Cmax"))
    put_calculation(
        SampleSizeCalculationRecord(
            study_id=STUDY,
            design="STANDARD_2X2_CROSSOVER",
            parameter="Cmax",
            randomized_n=8,
            required_n=8,
            status="CALCULATED",
            method="BE_TOST_2X2",
        )
    )
    calcs = __import__("app.domain.sample_size_store", fromlist=["list_calculations"]).list_calculations
    ss = calcs(STUDY)[-1]
    blockers = _actionable_blockers(
        study_id=STUDY,
        conflicts=[],
        preflight={},
        ss=ss,
        st=None,
        docs=[{"document_type": "SMPC"}],
        facts_count=3,
    )
    sample = next(b for b in blockers if b["code"] == "SAMPLE_SIZE_NOT_APPROVED")
    assert "утвердить" in sample["what"].lower()
    assert "CALCULATED" in sample["why"]
    assert sample["action_label"] == "Утвердить размер выборки"


def test_expert_statistics_gaps_are_not_listed_twice():
    put_plan(
        StatisticsPlan(
            study_id=STUDY,
            design="STANDARD_2X2_CROSSOVER",
            status="DRAFT",
            blocking_reasons=[
                "MISSING_ANALYSIS_POPULATION_RULE",
                "PRIMARY_BE_REQUIRES_EXPERT_SELECTION",
                "REQUIRES_EXPERT_DECISION",
            ],
        )
    )
    st = __import__("app.domain.statistics_store", fromlist=["latest_plan"]).latest_plan(STUDY)
    blockers = _actionable_blockers(
        study_id=STUDY,
        conflicts=[],
        preflight={},
        ss=None,
        st=st,
        docs=[{"document_type": "SMPC"}],
        facts_count=3,
    )
    codes = [b["code"] for b in blockers]
    assert "PRIMARY_BE_NOT_APPROVED" in codes
    assert "GAP_MISSING_PRIMARY_BE_SELECTION" not in codes
    assert "GAP_MISSING_ANALYSIS_POPULATION_RULE" not in codes
    primary = next(b for b in blockers if b["code"] == "PRIMARY_BE_NOT_APPROVED")
    assert "endpoint" in primary["what"].lower() or "популяц" in primary["what"].lower()
