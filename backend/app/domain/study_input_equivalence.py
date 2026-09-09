"""Binary vs text semantic equivalence — Phase 14.1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


EQUIV_STATES = (
    "MATCH",
    "BINARY_ONLY",
    "TEXT_ONLY",
    "VALUE_MISMATCH",
    "TYPE_MISMATCH",
    "NOT_COMPARABLE",
)


def _norm(v: Any) -> str:
    if isinstance(v, list):
        return "|".join(_norm(x) for x in v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    s = str(v).strip().lower().replace("мг", "mg").replace("ё", "е")
    for suffix in (", россия", ", russia", ", рф"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    return " ".join(s.split())


@dataclass
class FieldEquivalence:
    field_path: str
    binary_value: Any
    text_value: Any
    state: str
    binary_location: str | None = None
    text_location: str | None = None
    location_level: str = "DOCUMENT_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_candidate_sets(
    *,
    binary_candidates: list[dict[str, Any]],
    text_candidates: list[dict[str, Any]],
    document_type: str | None = None,
) -> list[FieldEquivalence]:
    def filt(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for it in items:
            if document_type and it.get("document_type") != document_type:
                continue
            fp = str(it.get("field_path"))
            # Prefer first; later identical paths overwrite only if same doc
            out[fp] = it
        return out

    bmap = filt(binary_candidates)
    tmap = filt(text_candidates)
    paths = sorted(set(bmap) | set(tmap))
    results: list[FieldEquivalence] = []
    for path in paths:
        b = bmap.get(path)
        t = tmap.get(path)
        if b and not t:
            state = "BINARY_ONLY"
            level = "STRUCTURAL" if (b.get("location") or "").startswith("table=") else "DOCUMENT_ONLY"
            results.append(
                FieldEquivalence(
                    path,
                    b.get("value"),
                    None,
                    state,
                    b.get("location"),
                    None,
                    level,
                )
            )
            continue
        if t and not b:
            results.append(
                FieldEquivalence(
                    path,
                    None,
                    t.get("value"),
                    "TEXT_ONLY",
                    None,
                    t.get("location"),
                    "DOCUMENT_ONLY",
                )
            )
            continue
        assert b is not None and t is not None
        bv, tv = b.get("value"), t.get("value")
        if type(bv) is not type(tv) and not (
            isinstance(bv, (int, float)) and isinstance(tv, (int, float))
        ):
            # bool vs int edge — still compare normalized
            if _norm(bv) == _norm(tv):
                state = "MATCH"
            else:
                state = "TYPE_MISMATCH"
        elif _norm(bv) == _norm(tv):
            state = "MATCH"
        else:
            state = "VALUE_MISMATCH"
        bloc = b.get("location")
        tloc = t.get("location")
        if bloc and str(bloc).startswith(("table=", "page=")):
            level = "EXACT" if bloc == tloc else "STRUCTURAL"
        elif bloc:
            level = "SECTION"
        else:
            level = "DOCUMENT_ONLY"
        results.append(
            FieldEquivalence(path, bv, tv, state, bloc, tloc, level)
        )
    return results


def equivalence_summary(results: list[FieldEquivalence]) -> dict[str, Any]:
    counts = {s: 0 for s in EQUIV_STATES}
    for r in results:
        counts[r.state] = counts.get(r.state, 0) + 1
    # Core fields must MATCH when present on both sides
    mismatches = [r for r in results if r.state in {"VALUE_MISMATCH", "TYPE_MISMATCH"}]
    return {
        "counts": counts,
        "match_count": counts["MATCH"],
        "mismatch_count": len(mismatches),
        "pass": len(mismatches) == 0,
        "results": [r.to_dict() for r in results],
    }
