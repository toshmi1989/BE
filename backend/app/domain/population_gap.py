"""Phase 19 — Population gap investigation (B-002 related population fields).

Does NOT invent medical rules. Observes which subjects/population fields appear
in real packages and which protocol sections depend on them.
"""

from __future__ import annotations

from typing import Any

from app.domain.study_input_classes import COVERAGE_DOMAINS, FIELD_PATHS
from app.domain.study_input_package import StudyInputPackage
from app.domain.study_input_pipeline import load_design_only_fixture, load_real_fixture_package

# Population-related controlled paths already in vocabulary
POPULATION_FIELDS: tuple[str, ...] = tuple(
    p for p in FIELD_PATHS if p.startswith("subjects.") or p.startswith("design.population")
)

PROTOCOL_SECTIONS_DEPENDING_ON_POPULATION: dict[str, tuple[str, ...]] = {
    "subjects.sex": ("Subjects", "Eligibility"),
    "subjects.age_min": ("Subjects", "Eligibility"),
    "subjects.age_max": ("Subjects", "Eligibility"),
    "subjects.screened_n": ("Subjects", "Sample Size"),
    "subjects.randomized_n": ("Subjects", "Sample Size", "Statistics"),
    "subjects.group_allocation": ("Subjects", "Study Design"),
    "subjects.type": ("Subjects",),
    "design.population": ("Subjects", "Background", "Objectives"),
}


def observe_population_fields(pkg: StudyInputPackage) -> dict[str, Any]:
    present: dict[str, Any] = {}
    for c in pkg.candidates:
        if c.field_path in POPULATION_FIELDS:
            present.setdefault(c.field_path, []).append(
                {
                    "value": c.value,
                    "status": c.status,
                    "source_id": c.source_id,
                    "document_type": c.document_type,
                    "excerpt_present": bool(c.excerpt),
                }
            )
    missing = [f for f in POPULATION_FIELDS if f not in present]
    return {
        "present_fields": sorted(present.keys()),
        "missing_fields": missing,
        "details": present,
        "domain_subjects": list(COVERAGE_DOMAINS.get("SUBJECTS") or []),
    }


def investigate_population_gap() -> dict[str, Any]:
    """Compare full UPDCB vs incomplete design-only — observed only."""
    full = load_real_fixture_package()
    partial = load_design_only_fixture()
    full_obs = observe_population_fields(full)
    partial_obs = observe_population_fields(partial)

    repeatedly_needed = [
        f
        for f in (
            "subjects.sex",
            "subjects.age_min",
            "subjects.age_max",
            "subjects.screened_n",
            "subjects.randomized_n",
            "subjects.group_allocation",
        )
        if f in FIELD_PATHS
    ]

    usually_present_in_full = [f for f in repeatedly_needed if f in full_obs["present_fields"]]
    missing_in_partial = [f for f in repeatedly_needed if f in partial_obs["missing_fields"]]

    # Blocker analysis — missing population does not invent defaults; readiness/preflight may warn
    blocks_final = True  # expert-controlled final; missing subjects typically blocks finalize
    proposed_model_change = {
        "required": False,
        "reason": (
            "Existing subjects.* field paths already cover observed UPDCB population facts. "
            "No new medical rule. Gap is package completeness (insufficient REAL cases), "
            "not missing schema fields."
        ),
        "recommendation": (
            "Prioritize intake of ≥10 distinct REAL packages with subjects metadata; "
            "ensure Writer Review highlights MISSING subjects.* without silent N/A."
        ),
    }

    return {
        "issue": "B-002",
        "phase20_reassessment": {
            "schema_sufficient": True,
            "schema_resolution": "RESOLVED",
            "package_population_resolution": "OPEN",
            "evidence": (
                "subjects.* vocabulary covers repeatedly needed population fields on UPDCB; "
                "incomplete packages leave fields MISSING for writer entry. "
                "Do not invent medical defaults. Package count gate remains unmet."
            ),
        },
        "clarification": (
            "B-002 originally mixed schema vs package-population concerns. "
            "Phase 20 separates them: schema sufficient; package population still open."
        ),
        "vocabulary_population_fields": list(POPULATION_FIELDS),
        "protocol_section_dependencies": PROTOCOL_SECTIONS_DEPENDING_ON_POPULATION,
        "full_package": {
            "fixture": full.fixture_id,
            **full_obs,
        },
        "partial_package": {
            "fixture": partial.fixture_id,
            **partial_obs,
        },
        "repeatedly_needed_from_observation": repeatedly_needed,
        "usually_present_when_package_complete": usually_present_in_full,
        "missing_when_incomplete_package": missing_in_partial,
        "writer_currently_enters_manually": missing_in_partial,
        "blocks_protocol_final_when_missing": blocks_final,
        "invented_medical_rule": False,
        "proposed_model_change": proposed_model_change,
    }
