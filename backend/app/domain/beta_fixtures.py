"""Phase 18 — Build synthetic StudyInputPackages for beta cases (clearly labelled)."""

from __future__ import annotations

from typing import Any

from app.domain.study_input_package import CandidateStudyValue, StudyInputDocument, StudyInputPackage
from app.domain.study_input_pipeline import create_package, load_design_only_fixture, load_real_fixture_package


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    return "string"


def _cand(
    field_path: str,
    value: Any,
    *,
    doc: str = "SYNOPSIS",
    source: str = "SRC-SYNTH",
    excerpt: str = "synthetic fixture excerpt",
    status: str = "PROPOSED",
) -> CandidateStudyValue:
    allowed_docs = {
        "CHECKLIST",
        "SYNOPSIS",
        "DESIGN",
        "SMPC",
        "PREVIOUS_PROTOCOL",
        "REGULATORY",
        "PUBLICATION",
        "OTHER",
        "UNKNOWN",
        "GOLDEN_PROTOCOL",
    }
    dtype = doc if doc in allowed_docs else ("PREVIOUS_PROTOCOL" if doc == "PROTOCOL" else "OTHER")
    return CandidateStudyValue(
        field_path=field_path,
        value=value,
        value_type=_value_type(value),
        source_id=source,
        document_type=dtype,
        excerpt=excerpt,
        location="synthetic§1",
        confidence="LOW",
        extraction_method="DETERMINISTIC",
        status=status,
        notes="SYNTHETIC — not a real writer package",
    )


def build_synthetic_package(case: dict[str, Any]) -> StudyInputPackage:
    case_id = str(case["case_id"])
    pkg = create_package(fixture_id=f"SYNTH-{case_id}")
    pkg.study_id = case_id
    pkg.notes = f"SYNTHETIC beta case {case_id}. Not a real medical writer package."
    for dtype in case.get("input_documents") or ["SYNOPSIS"]:
        allowed = {
            "CHECKLIST",
            "SYNOPSIS",
            "DESIGN",
            "SMPC",
            "PREVIOUS_PROTOCOL",
            "REGULATORY",
            "PUBLICATION",
            "OTHER",
            "UNKNOWN",
            "GOLDEN_PROTOCOL",
        }
        mapped = "PREVIOUS_PROTOCOL" if dtype == "PROTOCOL" else dtype
        if mapped not in allowed:
            mapped = "OTHER"
        pkg.documents.append(
            StudyInputDocument(
                document_id=f"DOC-{mapped}-{case_id[-6:]}",
                source_id=f"SRC-{mapped}-SYNTH",
                document_type=mapped,
                original_filename=f"{mapped.lower()}_synthetic.txt",
                content_hash=f"synth-{mapped}-{case_id}",
                mime_type="text/plain",
                role="INPUT",
            )
        )
    facts = dict(case.get("expected_key_facts") or {})
    # Seed candidates from expected key facts (synthetic known ground) as PROPOSED only
    for fp, val in facts.items():
        doc = (case.get("input_documents") or ["SYNOPSIS"])[0]
        pkg.candidates.append(_cand(fp, val, doc=doc, source=f"SRC-{doc}-SYNTH"))

    # Case-specific synthetic shapes
    if case.get("category") == "F":
        pkg.knowledge_gaps.append({"code": "MISSING_CVINTRA", "field": "cvintra"})
        pkg.blocking_issues.append("missing CVintra")
    if case.get("category") == "G":
        pkg.knowledge_gaps.append({"code": "MISSING_HALF_LIFE", "field": "half_life"})
        pkg.blocking_issues.append("missing half-life")
    if case.get("category") == "H":
        pkg.knowledge_gaps.append({"code": "MISSING_TMAX", "field": "tmax"})
        pkg.blocking_issues.append("missing Tmax")
    if case.get("category") == "J":
        for m in case.get("expected_missing_data") or []:
            pkg.knowledge_gaps.append({"code": f"MISSING_{str(m).upper()}", "field": m})
            pkg.blocking_issues.append(f"missing {m}")
    if case.get("category") == "L":
        pkg.candidates.append(_cand("subjects.randomized_n", 48, doc="PROTOCOL", source="SRC-LEGACY"))
        pkg.candidates.append(_cand("subjects.randomized_n", 56, doc="SYNOPSIS", source="SRC-SYNOPSIS-SYNTH"))
        pkg.conflicts.append(
            {
                "field_path": "subjects.randomized_n",
                "status": "OPEN",
                "values": [
                    {"value": "48", "document_type": "PROTOCOL"},
                    {"value": "56", "document_type": "SYNOPSIS"},
                ],
                "auto_resolve": False,
                "note": "stale protocol vs synopsis — protocol not SoT",
            }
        )
    for conf in case.get("expected_conflicts") or []:
        if case.get("category") == "L":
            continue  # already added
        if conf.get("field_path") and not any(
            c.get("field_path") == conf["field_path"] for c in pkg.conflicts
        ):
            pkg.conflicts.append(
                {
                    **conf,
                    "status": "OPEN",
                    "auto_resolve": False,
                }
            )
    pkg.research_tasks = [
        {"question": q, "status": "PENDING"} for q in (case.get("expected_research_questions") or [])
    ]
    return pkg


def load_case_package(case: dict[str, Any]) -> StudyInputPackage:
    loader = case.get("fixture_loader")
    if loader == "UPDCB_REAL":
        pkg = load_real_fixture_package()
        pkg.study_id = pkg.study_id or "UPDCB-02-BE-2026"
        return pkg
    if loader == "DESIGN_ONLY":
        pkg = load_design_only_fixture()
        pkg.study_id = case["case_id"]
        # Mark missing docs for availability UI
        for m in case.get("expected_missing_data") or []:
            pkg.knowledge_gaps.append({"code": f"MISSING_{str(m).upper()}", "field": m})
            pkg.blocking_issues.append(f"missing {m}")
        return pkg
    return build_synthetic_package(case)
