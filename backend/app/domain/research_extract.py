"""Deterministic claim extraction from research sources — Phase 15.2."""

from __future__ import annotations

import re
from typing import Any

from app.domain.research_evidence_models import (
    AnalogueStudyRecord,
    CVintraEvidence,
    EvidenceMeasurement,
    ResearchClaim,
    SourceResult,
)
from app.domain.research_provider import ProviderHit


def extract_claims_from_hit(
    hit: ProviderHit,
    *,
    research_task_id: str,
    source_result: SourceResult,
    study_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> list[ResearchClaim]:
    """Extract candidate claims. Always PROPOSED. Never invent missing numbers."""
    ctx = context or {}
    claims: list[ResearchClaim] = []
    meta = hit.metadata or {}
    text = hit.text or ""

    # Prefer explicit metadata from mock/provider; otherwise light regex
    param = meta.get("parameter")
    if param == "t_half" or (not param and re.search(r"t\s*1\s*/\s*2|half[- ]?life|t½|t1/2", text, re.I)):
        claims.append(_half_life_claim(hit, meta, text, research_task_id, source_result, study_id, ctx))
    if param == "Tmax" or (not param and re.search(r"\bTmax\b", text, re.I)):
        claims.append(_tmax_claim(hit, meta, text, research_task_id, source_result, study_id, ctx))
    if param in {"CVintra", "CV"} or (
        _CV_LABEL_RE.search(text) and (_WITHIN_SUBJECT_RE.search(text) or _BETWEEN_SUBJECT_RE.search(text))
    ):
        claims.append(_cv_claim(hit, meta, text, research_task_id, source_result, study_id, ctx))
    if meta.get("meal_description") or re.search(r"high[- ]calorie|meal composition|breakfast", text, re.I):
        claims.append(_meal_claim(hit, meta, text, research_task_id, source_result, study_id, ctx))
    if meta.get("active_substance") or (
        "bioequivalence" in text.lower() and "crossover" in text.lower()
    ):
        claims.append(_analogue_claim(hit, meta, text, research_task_id, source_result, study_id, ctx))

    # Deduplicate empty
    return [c for c in claims if c is not None]


def _half_life_claim(hit, meta, text, task_id, sr, study_id, ctx) -> ResearchClaim | None:
    stat = meta.get("statistic") or "UNKNOWN"
    value = meta.get("value")
    rlow, rhigh = meta.get("range_low"), meta.get("range_high")
    from_text = False
    stating = None
    if value is None and rlow is None:
        parsed = _hours_from_text(text, _HALF_LIFE_LABEL)
        if parsed is None:
            # A source that only mentions half-life carries no value to propose
            return None
        stat, value = parsed["statistic"], parsed["value"]
        rlow, rhigh = parsed["range_low"], parsed["range_high"]
        stating = parsed.get("clause")
        from_text = True
    # Do not collapse range into a single number
    if stat == "RANGE" or (rlow is not None and rhigh is not None and value is None):
        value = None
        stat = "RANGE"
    meas = EvidenceMeasurement(
        parameter="t_half",
        value=value,
        unit=meta.get("unit") or "hours",
        parameter_context=meta.get("parameter_context") or "terminal half-life",
        condition=meta.get("condition") or _infer_condition(text),
        population=meta.get("population") or _infer_population(text),
        dose=meta.get("dose") or ctx.get("dose") or _infer_dose(text),
        dosage_form=ctx.get("dosage_form"),
        route=meta.get("route") or "oral",
        analyte=ctx.get("analyte") or ctx.get("active_substance"),
        study_design=meta.get("study_design"),
        statistic_type=stat if stat in {
            "MEAN", "MEDIAN", "RANGE", "GEOMETRIC_MEAN", "POINT", "UNKNOWN"
        } else "UNKNOWN",
        range_low=rlow,
        range_high=rhigh,
        applicability="UNKNOWN",
        verification_status="PROPOSED",
        usability="REQUIRES_REVIEW",
    )
    excerpt = (stating or text)[:240]
    return ResearchClaim(
        claim_text=_format_half_life(meas),
        research_task_id=task_id,
        field_path="pk.t_half",
        value=meas.value if meas.statistic_type != "RANGE" else f"{rlow}-{rhigh}",
        unit=meas.unit,
        source_id=sr.registered_source_id,
        source_version_id=sr.registered_source_version_id,
        source_result_id=sr.id,
        location=hit.locator,
        excerpt=excerpt,
        extraction_method="DETERMINISTIC",
        measurement=meas.to_dict(),
        decision_domains=["WASHOUT", "SAMPLING"],
        study_id=study_id,
    )


def _tmax_claim(hit, meta, text, task_id, sr, study_id, ctx) -> ResearchClaim | None:
    stat = meta.get("statistic") or "UNKNOWN"
    value = meta.get("value")
    rlow, rhigh = meta.get("range_low"), meta.get("range_high")
    from_text = False
    stating = None
    if value is None and rlow is None:
        parsed = _hours_from_text(text, _TMAX_LABEL)
        if parsed is None:
            return None
        stat, value = parsed["statistic"], parsed["value"]
        rlow, rhigh = parsed["range_low"], parsed["range_high"]
        stating = parsed.get("clause")
        from_text = True
    # Preserve range; do not auto-mean
    meas = EvidenceMeasurement(
        parameter="Tmax",
        value=value,
        unit=meta.get("unit") or "hours",
        condition=_infer_condition(text),
        population=_infer_population(text),
        dose=ctx.get("dose") or _infer_dose(text),
        dosage_form=ctx.get("dosage_form"),
        analyte=ctx.get("analyte"),
        statistic_type=stat if stat in {
            "MEAN", "MEDIAN", "RANGE", "GEOMETRIC_MEAN", "POINT", "UNKNOWN"
        } else "UNKNOWN",
        range_low=rlow,
        range_high=rhigh,
        applicability="UNKNOWN",
        verification_status="PROPOSED",
        usability="REQUIRES_REVIEW",
    )
    return ResearchClaim(
        claim_text=f"Tmax {stat.lower()}={value} {meas.unit}"
        + (f" (range {rlow}-{rhigh})" if rlow is not None else ""),
        research_task_id=task_id,
        field_path="pk.Tmax",
        value=value,
        unit=meas.unit,
        source_id=sr.registered_source_id,
        source_version_id=sr.registered_source_version_id,
        source_result_id=sr.id,
        location=hit.locator,
        excerpt=(stating or text)[:240],
        extraction_method="DETERMINISTIC",
        measurement=meas.to_dict(),
        decision_domains=["SAMPLING"],
        study_id=study_id,
    )


def _cv_claim(hit, meta, text, task_id, sr, study_id, ctx) -> ResearchClaim | None:
    cv_value = meta.get("CV_value")
    # A table cell can state a range just as a sentence can
    rlow, rhigh = meta.get("CV_range_low"), meta.get("CV_range_high")
    stating = text
    if cv_value is None and rlow is None:
        parsed = _cv_percent_from_text(text)
        if parsed is None:
            # Nothing to propose: the source names CV without stating it
            return None
        cv_value, rlow, rhigh = parsed["value"], parsed["range_low"], parsed["range_high"]
        stating = parsed["clause"]
    var = meta.get("variability_type") or variability_type(stating)
    pk = meta.get("PK_parameter") or (
        "Cmax"
        if re.search(r"Cmax", stating, re.I)
        else ("AUC" if re.search(r"AUC", stating, re.I) else "OTHER")
    )
    if pk not in {"Cmax", "AUC", "AUC0-t", "AUC0-inf", "Tmax", "t_half", "OTHER"}:
        pk = "OTHER"
    cv = CVintraEvidence(
        CV_value=cv_value,
        CV_range_low=rlow,
        CV_range_high=rhigh,
        CV_unit=meta.get("CV_unit") or "%",
        PK_parameter=pk,
        variability_type=var,
        study_design=meta.get("study_design") or ("2x2 crossover" if "crossover" in text.lower() else None),
        dose=ctx.get("dose") or _infer_dose(text),
        population=_infer_population(text),
        condition=_infer_condition(text),
        source_id=sr.registered_source_id,
        applicability="UNKNOWN",
        verification_status="PROPOSED",
        usability="REQUIRES_REVIEW",
    )
    # Between-subject must not be labeled usable as CVintra
    if var != "WITHIN_SUBJECT":
        cv.usability = "NOT_USABLE_FOR_DECISION"
        cv.applicability = "NOT_APPLICABLE"
    stated = (
        f"{cv.CV_range_low}–{cv.CV_range_high}{cv.CV_unit}"
        if cv.CV_value is None
        else f"{cv.CV_value}{cv.CV_unit}"
    )
    label = {
        "WITHIN_SUBJECT": "CVintra",
        "BETWEEN_SUBJECT": "Between-subject CV",
    }.get(var, "CV (variability type not stated)")
    return ResearchClaim(
        claim_text=f"{label} for {pk} = {stated}",
        research_task_id=task_id,
        field_path="cv_intra" if var == "WITHIN_SUBJECT" else "cv_between",
        value=cv.CV_value,
        unit=cv.CV_unit,
        source_id=sr.registered_source_id,
        source_version_id=sr.registered_source_version_id,
        source_result_id=sr.id,
        location=hit.locator,
        # The expert must see the sentence that states the number, not the page start
        excerpt=(stating or text)[:240],
        extraction_method="DETERMINISTIC",
        cvintra=cv.to_dict(),
        decision_domains=["DESIGN", "STATISTICS"] if var == "WITHIN_SUBJECT" else [],
        applicability=cv.applicability,
        usability=cv.usability,
        study_id=study_id,
    )


_KCAL_RE = re.compile(
    r"(\d{3,4})\s*(?:[-–—]|to|до)?\s*(\d{3,4})?\s*(?:kcal|kcals|ккал|calories|калори)",
    re.I,
)
_FAT_RE = re.compile(
    r"(?:(\d{1,2})\s*%[^.]{0,30}?fat|fat[^.\d]{0,30}?(\d{1,2})\s*%)",
    re.I,
)


def _meal_claim(hit, meta, text, task_id, sr, study_id, ctx) -> ResearchClaim:
    desc = meta.get("meal_description")
    # Read kcal/fat only if the source states them — never invent a composition
    calories = meta.get("calories")
    fat = meta.get("fat")
    if calories is None:
        m = _KCAL_RE.search(text)
        if m:
            calories = f"{m.group(1)}–{m.group(2)}" if m.group(2) else int(m.group(1))
    if fat is None:
        m = _FAT_RE.search(text)
        if m:
            fat = int(m.group(1) or m.group(2))
    if not desc and not calories and not fat:
        desc = "high-calorie breakfast" if "high-calorie" in text.lower() else None
    claim = desc or text[:120]
    meas = EvidenceMeasurement(
        parameter="meal_composition",
        value={"description": desc, "calories": calories, "fat": fat},
        parameter_context="as stated in source — no invented composition",
        statistic_type="POINT" if calories is not None else "UNKNOWN",
        applicability="UNKNOWN",
        verification_status="PROPOSED",
        usability="REQUIRES_REVIEW",
    )
    return ResearchClaim(
        claim_text=str(claim),
        research_task_id=task_id,
        # Only a stated kcal figure is the value the food engine can use
        field_path="food.calorie_target" if calories is not None else "food.meal_description",
        value=calories if calories is not None else desc,
        unit="kcal" if calories is not None else None,
        source_id=sr.registered_source_id,
        source_version_id=sr.registered_source_version_id,
        source_result_id=sr.id,
        location=hit.locator,
        excerpt=text[:240],
        extraction_method="DETERMINISTIC",
        measurement=meas.to_dict(),
        decision_domains=["FOOD"],
        study_id=study_id,
    )


def _analogue_claim(hit, meta, text, task_id, sr, study_id, ctx) -> ResearchClaim:
    rec = AnalogueStudyRecord(
        study_title=hit.title,
        source_id=sr.registered_source_id,
        source_version_id=sr.registered_source_version_id,
        active_substance=meta.get("active_substance"),
        dose=meta.get("dose"),
        dosage_form=meta.get("dosage_form"),
        population=meta.get("population"),
        design=meta.get("design"),
        condition=meta.get("condition"),
        applicability_status="UNKNOWN",
        verification_status="PROPOSED",
        study_id=study_id,
    )
    return ResearchClaim(
        claim_text=f"Analogue study: {hit.title}",
        research_task_id=task_id,
        field_path="analogue.study",
        value=rec.study_title,
        source_id=sr.registered_source_id,
        source_version_id=sr.registered_source_version_id,
        source_result_id=sr.id,
        location=hit.locator,
        excerpt=text[:240],
        extraction_method="DETERMINISTIC",
        measurement={"analogue": rec.to_dict()},
        decision_domains=["DESIGN"],
        study_id=study_id,
    )


def _format_half_life(m: EvidenceMeasurement) -> str:
    if m.statistic_type == "RANGE":
        return f"t½ range {m.range_low}-{m.range_high} {m.unit}"
    return f"t½ {m.statistic_type.lower()}={m.value} {m.unit}"


_NUM = r"(\d{1,3}(?:[.,]\d+)?)"
_HOURS = r"(?:h\b|hr?s?\b|hours?\b|ч\b|час[а-я]*)"
_HALF_LIFE_LABEL = r"(?:t\s*1\s*/\s*2|t½|half[-\s]?li(?:fe|ves)|период\s+полувыведения)"
_TMAX_LABEL = r"(?:t\s*max|время\s+достижения\s+максимальной\s+концентрации)"
# The value must stay in the same clause as its label, so the gap excludes . ; and digits
_GAP = r"[^0-9.;\n]{0,25}?"

_WITHIN_SUBJECT_RE = re.compile(
    r"within[-\s]?subject|intra[-\s]?subject|intra[-\s]?individual|"
    r"CV\s*intra|CV\s*w\b|внутри\s*индивидуал|внутрииндивидуал",
    re.I,
)
_BETWEEN_SUBJECT_RE = re.compile(
    r"between[-\s]?subject|inter[-\s]?subject|inter[-\s]?individual|"
    r"CV\s*b\b|между\s*индивидуал|межиндивидуал",
    re.I,
)
_CV_LABEL_RE = re.compile(
    r"\bCV\b|%\s*CV|coefficient\s+of\s+variation|variabilit\w*|вариабельност\w*|"
    r"коэффициент\s+вариации",
    re.I,
)
_CV_LABEL = f"(?:{_CV_LABEL_RE.pattern})"
_PCT = r"(\d{1,3}(?:[.,]\d+)?)\s*%"
_RANGE_SEP = r"\s*(?:[-–—]|to|до)\s*"
# Label and value must sit in one clause; the gap allows "(CV %) of drug X AUC and Cmax was"
_CV_GAP = r"[^.;:\n]{0,60}?"
# Dot leaders and section pointers mean a table of contents, not a measurement
_LOOKS_LIKE_CONTENTS_RE = re.compile(r"\.{3,}|\bpage\s+\d|\bsee\s+(?:section|table)\b", re.I)


def _clause_at(text: str, start: int, *, back: int = 160, span: int = 200) -> str:
    """The sentence around a label — the qualifier usually sits to its left.

    "the between-subject variability (CV %) … was 20% to 35%" only means
    something when the words before the label travel with the number.
    """
    left = text[max(0, start - back) : start]
    cut = max(left.rfind(". "), left.rfind("; "), left.rfind(": "), left.rfind("\n"))
    lead = left[cut + 1 :] if cut >= 0 else left
    tail = text[start : start + span]
    stop = re.search(r"[.;:](?:\s|$)", tail[1:])
    if stop:
        tail = tail[: stop.start() + 1]
    return (lead + tail).strip()


def _statistic_near(text: str, start: int) -> str:
    lead = text[max(0, start - 40) : start].lower()
    if "median" in lead or "медиан" in lead:
        return "MEDIAN"
    if "geometric" in lead:
        return "GEOMETRIC_MEAN"
    if "mean" in lead or "средн" in lead:
        return "MEAN"
    return "UNKNOWN"


def _as_number(raw: str) -> float:
    return float(raw.replace(",", "."))


def _hours_from_text(text: str, label: str) -> dict[str, Any] | None:
    """Read a value in hours stated next to its label. Returns None if not stated."""
    rng = re.search(label + _GAP + _NUM + r"\s*(?:[-–—]|to|до)\s*" + _NUM + r"\s*" + _HOURS, text, re.I)
    if rng:
        return {
            "statistic": "RANGE",
            "value": None,
            "range_low": _as_number(rng.group(1)),
            "range_high": _as_number(rng.group(2)),
            "clause": _clause_at(text, rng.start()),
        }
    point = re.search(label + _GAP + _NUM + r"\s*" + _HOURS, text, re.I)
    if point:
        return {
            "statistic": _statistic_near(text, point.start()),
            "value": _as_number(point.group(1)),
            "range_low": None,
            "range_high": None,
            "clause": _clause_at(text, point.start()),
        }
    return None


def _percent_near_cv(text: str) -> float | None:
    m = re.search(r"CV[^0-9%\n]{0,25}?(\d{1,2}(?:[.,]\d+)?)\s*%", text, re.I) or re.search(
        r"(\d{1,2}(?:[.,]\d+)?)\s*%[^.;\n]{0,25}?CV", text, re.I
    )
    return _as_number(m.group(1)) if m else None


def variability_type(text: str) -> str:
    """Within- and between-subject are different quantities; never guess between them."""
    within = bool(_WITHIN_SUBJECT_RE.search(text))
    between = bool(_BETWEEN_SUBJECT_RE.search(text))
    if within and not between:
        return "WITHIN_SUBJECT"
    if between and not within:
        return "BETWEEN_SUBJECT"
    # Both named in one passage, or neither — the expert must read the source
    return "UNKNOWN"


def _cv_percent_from_text(text: str) -> dict[str, Any] | None:
    """Read a variability percentage as stated, with the clause that states it.

    One paragraph can carry several percentages (Cmax/AUC and clearance, say),
    so every candidate is scored and the clause of the winner travels with the
    value — that is what the PK parameter and variability type are read from.
    """
    best: dict[str, Any] | None = None
    best_score = -1.0
    for label in _CV_LABEL_RE.finditer(text):
        clause = _clause_at(text, label.start())
        if _LOOKS_LIKE_CONTENTS_RE.search(clause):
            continue
        # "20% to 35%" and "5-7%" are both ranges and must stay ranges
        rng = re.search(_PCT + _RANGE_SEP + _PCT, clause) or re.search(
            r"(\d{1,3}(?:[.,]\d+)?)" + _RANGE_SEP + _PCT, clause
        )
        point = None if rng else re.search(_PCT, clause)
        if rng:
            low, high = _as_number(rng.group(1)), _as_number(rng.group(2))
            if low is None or high is None or low > high:
                continue
            candidate = {"value": None, "range_low": low, "range_high": high, "clause": clause}
        elif point:
            candidate = {
                "value": _as_number(point.group(1)),
                "range_low": None,
                "range_high": None,
                "clause": clause,
            }
        else:
            continue
        score = 0.0
        if re.search(r"Cmax|AUC", clause, re.I):
            score += 2
        if _WITHIN_SUBJECT_RE.search(clause) or _BETWEEN_SUBJECT_RE.search(clause):
            score += 1
        if score > best_score:
            best, best_score = candidate, score
    if best is not None:
        return best
    legacy = _percent_near_cv(text)
    if legacy is not None:
        return {"value": legacy, "range_low": None, "range_high": None, "clause": text[:240]}
    return None


def _infer_population(text: str) -> str | None:
    if re.search(r"healthy\s+volunteer", text, re.I):
        return "healthy volunteers"
    return None


def _infer_condition(text: str) -> str | None:
    if re.search(r"single\s+dose", text, re.I):
        return "single dose"
    if re.search(r"fasting|fasted", text, re.I):
        return "fasting"
    if re.search(r"\bfed\b", text, re.I):
        return "fed"
    return None


def _infer_dose(text: str) -> str | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*mg", text, re.I)
    return f"{m.group(1)} mg" if m else None
