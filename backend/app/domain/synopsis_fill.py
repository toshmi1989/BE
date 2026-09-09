"""Synopsis (T03) fill — canonical Sponsor / SubjectPlan → template labels.

Phase 11C-H: deterministic replacement of subject-count cells only.
Does not globally scrub the digit 46 (TOC page numbers stay untouched).
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.org_render import (
    analytical_labs,
    clinical_centers,
    format_org,
    format_person,
    investigators,
    key_organizations,
    resolve_sponsor,
    sponsor_persons,
)

LEGACY_TEMPLATE_SUBJECT_N = 46

# Whole-number 46 only when used as a subject / volunteer count (not TOC pages, not ages).
SUBJECT_COUNT_46_RE = re.compile(
    r"(?<!\d)46(?!\d)(?=\s*(?:добровольц|субъект|рандомиз|участник))",
    re.IGNORECASE,
)
RANDOMIZED_LINE_RE = re.compile(
    r"(Рандомизированн\w*\s+добровольц\w*\s*:\s*)\d+",
    re.IGNORECASE,
)
SCREENED_LINE_RE = re.compile(
    r"(Скринировать\s+до\s*:\s*)\d+",
    re.IGNORECASE,
)
RESERVE_LINE_RE = re.compile(
    r"(Дублеры\s*:\s*)\d+",
    re.IGNORECASE,
)
VOLUNTEERS_PHRASE_RE = re.compile(
    r"(у\s+)46(\s+добровольц)",
    re.IGNORECASE,
)
PARTICIPATION_PHRASE_RE = re.compile(
    r"(участие\s+)46(\s+добровольц)",
    re.IGNORECASE,
)

# Russian T03 labels → fill keys (normalized contains-match used at fill time)
SYNOPSIS_LABEL_KEYS: list[tuple[str, str]] = [
    ("спонсор исследования", "sponsor"),
    ("ответственные лица со стороны спонсора", "sponsor_persons"),
    ("главный исследователь", "investigator"),
    ("исследовательский центр", "clinical_center"),
    ("аналитическая лаборатория", "analytical_lab"),
    ("организация, проводящая клиническую", "key_org"),
]


def _norm(label: str) -> str:
    return (label or "").strip().lower().replace("ё", "е").rstrip(":").replace("\t", " ")


def classify_legacy_46_hit(
    *,
    location: str,
    text: str,
    style: str | None = None,
) -> dict[str, Any]:
    """Classify a bare-token 46 occurrence for audit / gates."""
    style_l = (style or "").lower()
    if style_l.startswith("toc") or "\t46" in text or text.rstrip().endswith("\t46"):
        return {
            "location": location,
            "kind": "TOC_PAGE_NUMBER",
            "subject_related": False,
            "safe_to_preserve": True,
            "must_replace": False,
            "reason": "TOC page number, not SubjectPlan N",
        }
    if SUBJECT_COUNT_46_RE.search(text) or RANDOMIZED_LINE_RE.search(text) and "46" in text:
        if "Рандомизированные добровольцы: 46" in text or SUBJECT_COUNT_46_RE.search(text):
            return {
                "location": location,
                "kind": "SUBJECT_COUNT",
                "subject_related": True,
                "safe_to_preserve": False,
                "must_replace": True,
                "reason": "legacy template subject count",
            }
    if re.fullmatch(r"\s*46\s*", text or ""):
        return {
            "location": location,
            "kind": "CV_OR_BARE_N",
            "subject_related": False,
            "safe_to_preserve": True,
            "must_replace": False,
            "reason": "bare 46 may be CV n_total / unrelated metric — not SubjectPlan gate",
        }
    if SUBJECT_COUNT_46_RE.search(text):
        return {
            "location": location,
            "kind": "SUBJECT_COUNT",
            "subject_related": True,
            "safe_to_preserve": False,
            "must_replace": True,
            "reason": "subject-count phrasing with 46",
        }
    return {
        "location": location,
        "kind": "OTHER",
        "subject_related": False,
        "safe_to_preserve": True,
        "must_replace": False,
        "reason": "46 token not in subject-count pattern",
    }


def build_synopsis_admin_rows(ctx: dict) -> list[list[Any]]:
    """Label/value rows for T03 admin fields from canonical Sponsor/Person/Org."""
    rows: list[list[Any]] = []
    sponsor = resolve_sponsor(ctx)
    if sponsor and sponsor.get("name"):
        parts = [str(sponsor["name"])]
        if sponsor.get("country"):
            parts.append(str(sponsor["country"]))
        rows.append(["Спонсор исследования", ", ".join(parts)])

    persons = sponsor_persons(ctx)
    if persons:
        items = [
            format_person(p) if (p.get("full_name") or p.get("name")) else format_org(p) for p in persons
        ]
        rows.append(["Ответственные лица со стороны Спонсора", "; ".join(items)])

    inv = investigators(ctx)
    if inv:
        p = inv[0]
        name = format_person(p) if (p.get("full_name") or p.get("name")) else format_org(p)
        rows.append(["Главный исследователь", name])

    centers = clinical_centers(ctx)
    if centers:
        rows.append(["Исследовательский центр", format_org(centers[0])])

    labs = analytical_labs(ctx)
    if labs:
        rows.append(["Аналитическая лаборатория", format_org(labs[0])])

    key = key_organizations(ctx)
    if key:
        rows.append(
            [
                "Организация, проводящая клиническую часть исследования, отвечающая за мониторинг",
                format_org(key[0]),
            ]
        )

    study = ctx.get("study") or {}
    if study.get("protocol_number"):
        rows.append(["Протокол", f"№ {study['protocol_number']}"])

    return rows


def build_synopsis_n_metric_rows(ctx: dict, consistency: dict | None = None) -> list[list[Any]]:
    """Metric labels used by STUDY_METADATA / consistency tables (not T03 Russian labels)."""
    consistency = consistency or {}
    subjects_c = get_canonical_subject_counts(ctx)
    eval_n = consistency.get("evaluable_n")
    if eval_n is None:
        eval_n = subjects_c.evaluable_n
    rand_n = consistency.get("randomized_n")
    if rand_n is None:
        rand_n = subjects_c.randomized_n
    screen_n = consistency.get("screened_n")
    if screen_n is None:
        screen_n = subjects_c.screened_n
    return [
        [
            "Оцениваемые",
            eval_n if eval_n is not None else "{{SUBJECTS.EVALUABLE_N}}",
        ],
        [
            "Рандомизированные",
            rand_n if rand_n is not None else "{{SUBJECTS.RANDOMIZED_N}}",
        ],
        [
            "Скрининг",
            screen_n if screen_n is not None else "{{SUBJECTS.SCREENED_N}}",
        ],
    ]


def rewrite_subject_count_text(text: str, *, randomized_n: int | None, screened_n: int | None) -> str:
    """Deterministic rewrite of known subject-count phrases; no global digit scrub."""
    if not text:
        return text
    out = text
    if randomized_n is not None and randomized_n != LEGACY_TEMPLATE_SUBJECT_N:
        out = RANDOMIZED_LINE_RE.sub(rf"\g<1>{randomized_n}", out)
        out = VOLUNTEERS_PHRASE_RE.sub(rf"\g<1>{randomized_n}\g<2>", out)
        out = PARTICIPATION_PHRASE_RE.sub(rf"\g<1>{randomized_n}\g<2>", out)
        out = SUBJECT_COUNT_46_RE.sub(str(randomized_n), out)
    if screened_n is not None:
        out = SCREENED_LINE_RE.sub(rf"\g<1>{screened_n}", out)
        if randomized_n is not None and screened_n >= randomized_n:
            reserve = screened_n - randomized_n
            out = RESERVE_LINE_RE.sub(rf"\g<1>{reserve}", out)
    return out


def apply_synopsis_subject_n_to_table(table, ctx: dict, consistency: dict | None = None) -> list[dict]:
    """Rewrite T03 subject-count cells in place. Returns audit trail of changes."""
    consistency = consistency or {}
    subjects_c = get_canonical_subject_counts(ctx)
    rand_n = consistency.get("randomized_n")
    if rand_n is None:
        rand_n = subjects_c.randomized_n
    screen_n = consistency.get("screened_n")
    if screen_n is None:
        screen_n = subjects_c.screened_n

    audit: list[dict] = []
    if rand_n is None:
        return audit
    if rand_n == LEGACY_TEMPLATE_SUBJECT_N and (
        screen_n is None or screen_n == LEGACY_TEMPLATE_SUBJECT_N
    ):
        return audit

    subject_row_needles = (
        "исследуемая популяция",
        "сбор образцов крови",
    )
    for ri, row in enumerate(table.rows):
        if len(row.cells) < 2:
            continue
        label = _norm(row.cells[0].text or "")
        if not any(n in label for n in subject_row_needles):
            continue
        value_cell = row.cells[1]
        old = value_cell.text or ""
        new = rewrite_subject_count_text(old, randomized_n=rand_n, screened_n=screen_n)
        if new != old:
            # set via caller-provided setter if available — return payload for renderer
            audit.append(
                {
                    "row": ri,
                    "label": (row.cells[0].text or "").strip(),
                    "reason_not_matched_before": "SYNOPSIS_N metric labels ≠ Russian T03 population/sampling labels",
                    "subject_related": True,
                    "safe_to_preserve": False,
                    "must_replace": True,
                    "old_snip": old[:160],
                    "new_snip": new[:160],
                    "new_text": new,
                    "cell": value_cell,
                }
            )
    return audit


def find_legacy_subject_count_46(
    *,
    paragraphs: list[tuple[str, str, str]],
    table_cells: list[tuple[str, str]],
    canonical_randomized_n: int | None,
) -> list[dict]:
    """Find residual subject-count 46 that must block REVIEW/FINAL when N ≠ 46.

    paragraphs: (location, text, style)
    table_cells: (location, text)
    """
    if canonical_randomized_n is None or canonical_randomized_n == LEGACY_TEMPLATE_SUBJECT_N:
        return []
    hits: list[dict] = []
    for loc, text, style in paragraphs:
        if (style or "").lower().startswith("toc"):
            continue
        # TOC-like: "5. Title\t46"
        if re.search(r"\t46\s*$", text or ""):
            continue
        if SUBJECT_COUNT_46_RE.search(text or "") or re.search(
            r"Рандомизированн\w*\s+добровольц\w*\s*:\s*46\b", text or "", re.IGNORECASE
        ):
            hits.append(
                {
                    "location": loc,
                    "kind": "SUBJECT_COUNT",
                    "text_snip": (text or "")[:120],
                }
            )
    for loc, text in table_cells:
        # Skip CV bare-n cells (single token) — not SubjectPlan
        if re.fullmatch(r"\s*46\s*", text or ""):
            continue
        if SUBJECT_COUNT_46_RE.search(text or "") or re.search(
            r"Рандомизированн\w*\s+добровольц\w*\s*:\s*46\b", text or "", re.IGNORECASE
        ):
            hits.append({"location": loc, "kind": "SUBJECT_COUNT", "text_snip": (text or "")[:120]})
    return hits
