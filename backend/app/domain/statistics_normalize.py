"""Phase 15.5 — Parameter identity normalization."""

from __future__ import annotations

import re
import unicodedata

from app.domain.statistics_engine_classes import SUPPORTED_PARAMETERS

# Map normalized keys → canonical vocabulary id
_ALIASES: dict[str, str] = {
    "cmax": "Cmax",
    "c_max": "Cmax",
    "c-max": "Cmax",
    "auc0-t": "AUC0-t",
    "auc0t": "AUC0-t",
    "auc(0-t)": "AUC0-t",
    "auc0-inf": "AUC0-inf",
    "auc0inf": "AUC0-inf",
    "auc0-∞": "AUC0-inf",
    "auc(0-∞)": "AUC0-inf",
    "auc(0-inf)": "AUC0-inf",
    "auc0-72": "AUC0-72",
    "auc072": "AUC0-72",
    "auc(0-72)": "AUC0-72",
    "auc0–72": "AUC0-72",
    "auc 0-72": "AUC0-72",
    "auc 0–72": "AUC0-72",
    "auc0-x": "AUC0-x",
    "auc0x": "AUC0-x",
    "tmax": "Tmax",
    "t_max": "Tmax",
    "t-max": "Tmax",
    "t1/2": "t1/2",
    "t½": "t1/2",
    "t1/2": "t1/2",
    "thalf": "t1/2",
    "t_half": "t1/2",
    "kel": "kel",
    "ke": "kel",
    "aucextr": "AUCextr",
    "auc_extr": "AUCextr",
    "auc%extr": "AUCextr",
}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("–", "-").replace("—", "-").replace("∞", "inf")
    s = s.replace("½", "1/2").replace("¼", "1/4")
    s = s.replace("\u2044", "/")  # fraction slash from NFKC of ½
    s = re.sub(r"\s+", " ", s.strip().lower())
    s = s.replace(" ", "")
    return s


def normalize_parameter(raw: str) -> tuple[str | None, str]:
    """Return (canonical_id | None, original_wording).

    Unsupported parameters return (None, original) — never silently invent.
    """
    original = str(raw).strip()
    if not original:
        return None, original
    key = _fold(original)
    # try direct alias
    if key in _ALIASES:
        return _ALIASES[key], original
    # try with separators normalized
    key2 = key.replace("_", "-")
    if key2 in _ALIASES:
        return _ALIASES[key2], original
    # t½ / t1/2 variants after fold
    if key in {"t1/2", "t½", "thalf", "t_half"} or key.replace("1/2", "half") == "thalf":
        return "t1/2", original
    # already canonical?
    if original in SUPPORTED_PARAMETERS:
        return original, original
    return None, original


def normalize_parameter_list(values: list[str] | tuple[str, ...] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for v in values or []:
        canon, orig = normalize_parameter(str(v))
        if canon and canon not in seen:
            seen.add(canon)
            out.append({"canonical": canon, "original": orig})
        elif not canon:
            out.append({"canonical": "", "original": orig, "unsupported": "true"})
    return out


def parse_acceptance_interval(text: str | None) -> tuple[float, float] | None:
    if not text:
        return None
    m = re.search(
        r"(80(?:[.,]00)?)\s*[–\-—]\s*(125(?:[.,]00)?)\s*%?",
        str(text),
        re.I,
    )
    if not m:
        m2 = re.search(r"(\d+(?:[.,]\d+)?)\s*[–\-—]\s*(\d+(?:[.,]\d+)?)\s*%?", str(text))
        if not m2:
            return None
        lo = float(m2.group(1).replace(",", "."))
        hi = float(m2.group(2).replace(",", "."))
        # store as ratio scale if given as percent > 1
        if lo > 1:
            lo /= 100.0
        if hi > 1:
            hi /= 100.0
        return lo, hi
    return 0.80, 1.25


def parse_confidence_level(text: str | float | int | None) -> float | None:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        v = float(text)
        if v > 1:
            v = v / 100.0
        if 0 < v < 1:
            return v
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%?", str(text))
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    if v > 1:
        v = v / 100.0
    if 0 < v < 1:
        return v
    return None
