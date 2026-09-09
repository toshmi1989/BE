"""Document classification — Phase 14.

Deterministic heuristics first. Never silently overwrite user-selected type.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ClassificationResult:
    document_type: str
    method: str  # HEURISTIC|MANUAL|AI
    confidence: str
    rationale: str
    overridable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_document(
    *,
    filename: str,
    text: str,
    user_selected_type: str | None = None,
) -> ClassificationResult:
    if user_selected_type:
        return ClassificationResult(
            document_type=user_selected_type,
            method="MANUAL",
            confidence="HIGH",
            rationale="Explicit user-selected document type",
            overridable=False,
        )

    name = (filename or "").lower()
    body = (text or "").lower()

    # Golden protocol / previous protocol heuristics
    if "golden" in name or name.startswith("пки_") or "protocol" in name and "corr" in name:
        if "пки" in name or "протокол клинического исследования" in body[:2000]:
            # Prefer GOLDEN if filename matches golden fixture naming
            if "updcb" in name and "corr" in name:
                return ClassificationResult("GOLDEN_PROTOCOL", "HEURISTIC", "MEDIUM", "Filename matches golden protocol pattern")
            return ClassificationResult("PREVIOUS_PROTOCOL", "HEURISTIC", "MEDIUM", "Looks like full clinical protocol")

    if "чек-лист" in name or "checklist" in name or "чек лист" in name:
        return ClassificationResult("CHECKLIST", "HEURISTIC", "HIGH", "Filename contains checklist marker")
    if "синопсис" in name or "synopsis" in name:
        return ClassificationResult("SYNOPSIS", "HEURISTIC", "HIGH", "Filename contains synopsis marker")
    if "smpc" in name or "охлп" in name or "spc" in name:
        return ClassificationResult("SMPC", "HEURISTIC", "HIGH", "Filename contains SmPC marker")
    if "дизайн" in name and "синопсис" not in name:
        return ClassificationResult("DESIGN", "HEURISTIC", "MEDIUM", "Filename suggests design-only input")

    # Content heuristics
    checklist_hits = sum(
        1
        for k in ("спонсор", "референтн", "кио", "маркировк", "упаковк", "дру")
        if k in body
    )
    synopsis_hits = sum(
        1
        for k in ("дизайн исследования", "субъекты исследования", "отбор проб", "фармакокинетическ", "критерии включения")
        if k in body
    )
    design_hits = sum(
        1
        for k in ("рандомизированное", "перекрестное", "двухпериодное", "скринированных", "рандомизированных")
        if k in body
    )
    smpc_hits = sum(
        1
        for k in ("общая характеристика", "лекарственного препарата", "противопоказан", "фармакокинетика", "состав")
        if k in body
    )

    scores = {
        "CHECKLIST": checklist_hits,
        "SYNOPSIS": synopsis_hits,
        "DESIGN": design_hits,
        "SMPC": smpc_hits,
    }
    best = max(scores, key=scores.get)
    if scores[best] >= 3:
        # DESIGN-only short texts: high design hits but low synopsis structure
        if best == "DESIGN" and synopsis_hits < 2 and len(body) < 2500:
            return ClassificationResult("DESIGN", "HEURISTIC", "HIGH", "Short design-like text")
        if best == "SYNOPSIS" and synopsis_hits >= 3:
            return ClassificationResult("SYNOPSIS", "HEURISTIC", "HIGH", "Synopsis section markers")
        if best == "CHECKLIST" and checklist_hits >= 3:
            return ClassificationResult("CHECKLIST", "HEURISTIC", "HIGH", "Checklist administrative markers")
        if best == "SMPC" and smpc_hits >= 3:
            return ClassificationResult("SMPC", "HEURISTIC", "HIGH", "SmPC product-information markers")
        return ClassificationResult(best, "HEURISTIC", "MEDIUM", f"Heuristic score winner={best}")

    if design_hits >= 3 and len(body) < 3000:
        return ClassificationResult("DESIGN", "HEURISTIC", "MEDIUM", "Design keywords in short document")

    return ClassificationResult("UNKNOWN", "HEURISTIC", "LOW", "Insufficient classification signals")
