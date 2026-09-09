"""Deterministic eligibility list rendering — Eligibility is the only source."""

from __future__ import annotations

from typing import Any, Iterable


def _sorted_criteria(items: Iterable[dict]) -> list[dict]:
    def key(c: dict) -> tuple:
        order = c.get("sort_order")
        if order is None:
            order = c.get("order")
        if order is None:
            order = 10_000
        return (int(order), str(c.get("id") or ""), str(c.get("text") or c.get("criterion_text") or ""))

    return sorted(list(items), key=key)


def render_eligibility_list(
    criteria: list[dict] | None,
    *,
    numbered: bool = True,
    empty_placeholder: str | None = None,
    category: str | None = None,
) -> list[str]:
    """
    Render inclusion / non_inclusion / exclusion criteria as ordered strings.

    Empty collection → empty list (caller may insert placeholder).
    Does not invent criteria.
    """
    items = _sorted_criteria(criteria or [])
    if not items:
        if empty_placeholder:
            return [empty_placeholder]
        return []

    lines: list[str] = []
    for i, c in enumerate(items, start=1):
        text = (c.get("text") or c.get("criterion_text") or "").strip()
        if not text:
            continue
        if numbered:
            lines.append(f"{i}. {text}")
        else:
            lines.append(text)
    if not lines and empty_placeholder:
        return [empty_placeholder]
    return lines


def eligibility_from_ctx(ctx: dict) -> dict[str, list[dict]]:
    el = ctx.get("eligibility") or {}
    return {
        "inclusion": list(el.get("inclusion") or []),
        "non_inclusion": list(el.get("non_inclusion") or []),
        "exclusion": list(el.get("exclusion") or []),
    }


def render_eligibility_bundle(ctx: dict, *, numbered: bool = True) -> dict[str, list[str]]:
    bun = eligibility_from_ctx(ctx)
    return {
        "inclusion": render_eligibility_list(
            bun["inclusion"],
            numbered=numbered,
            empty_placeholder="{{ELIGIBILITY.INCLUSION}}",
            category="inclusion",
        ),
        "non_inclusion": render_eligibility_list(
            bun["non_inclusion"],
            numbered=numbered,
            empty_placeholder="{{ELIGIBILITY.NON_INCLUSION}}",
            category="non_inclusion",
        ),
        "exclusion": render_eligibility_list(
            bun["exclusion"],
            numbered=numbered,
            empty_placeholder="{{ELIGIBILITY.EXCLUSION}}",
            category="exclusion",
        ),
    }
