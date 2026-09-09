"""Phase 12B.4 — appendices / conclusion / literature generators.

No invented results, signatures, or citations. Medical rules added = ZERO.
"""

from __future__ import annotations

from typing import Any

from app.domain.appendix_inventory import build_appendix_inventory
from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.display_value_registry import find_raw_enums_in_text, resolve_display
from app.domain.org_render import signature_table_rows
from app.domain.protocol_consistency import find_unresolved_markers
from app.domain.protocol_sections import SectionDef
from app.domain.reference_builder import build_bibliography
from app.domain.static_blocks import STATIC_VERIFIED


def _block(**kwargs: Any) -> dict:
    text = kwargs.get("text")
    unresolved = kwargs.get("unresolved")
    if unresolved is None:
        unresolved = find_unresolved_markers(text) if text else []
    return {
        "type": kwargs.get("type_") or kwargs.get("type") or "TEXT",
        "block_code": kwargs.get("block_code"),
        "text": text,
        "items": kwargs.get("items") or [],
        "table_key": kwargs.get("table_key"),
        "origin": kwargs.get("origin"),
        "rule_id": kwargs.get("rule_id"),
        "source_ids": kwargs.get("source_ids") or [],
        "unresolved": unresolved,
        "target_type": kwargs.get("target_type"),
        "target_id": kwargs.get("target_id"),
        "display_text": kwargs.get("display_text"),
    }


def _enrich(block: dict, *, resolution_status: str, display_as_final: bool, **extra: Any) -> dict:
    block = dict(block)
    block["resolution_status"] = resolution_status
    block["display_as_final"] = display_as_final
    block["content_type"] = block.get("content_type") or (
        "STATIC_VERIFIED"
        if block.get("origin") == "STATIC_VERIFIED"
        else ("CANONICAL_VALUE" if display_as_final else "PLACEHOLDER")
    )
    for k, v in extra.items():
        block[k] = v
    text = block.get("text")
    if text and find_raw_enums_in_text(str(text)):
        block["text"] = "{{DISPLAY.ENUM}}"
        block["unresolved"] = list(set((block.get("unresolved") or []) + ["{{DISPLAY.ENUM}}"]))
        block["resolution_status"] = "UNRESOLVED"
        block["display_as_final"] = False
    scrubbed = []
    for it in list(block.get("items") or []):
        if find_raw_enums_in_text(str(it)):
            block["resolution_status"] = "UNRESOLVED"
            block["display_as_final"] = False
            block["unresolved"] = list(set((block.get("unresolved") or []) + ["{{DISPLAY.ENUM}}"]))
            continue
        scrubbed.append(it)
    if block.get("items") is not None:
        block["items"] = scrubbed
    return block


def _gap(domain: str, question: str, *, importance: str = "HIGH", blocking: bool = True, **extra: Any) -> dict:
    g = {"domain": domain, "question": question, "importance": importance, "blocking": blocking}
    g.update(extra)
    return g


def _product_name(p: dict | None) -> str | None:
    p = p or {}
    name = p.get("trade_name") or p.get("inn")
    return str(name) if name else None


def gen_appendices_12b4(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    inventory = build_appendix_inventory(ctx=ctx)
    blocks: list[dict] = []
    unresolved: list[str] = []
    src: list[str] = []
    gaps: list[dict] = []

    blocks.append(
        _enrich(
            _block(type_="PAGE_BREAK", block_code="APP.PAGE_BREAK", origin="TEMPLATE"),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="STATIC_VERIFIED",
        )
    )

    listing = []
    for item in inventory:
        listing.append(f"{item.block_id or item.title}: {item.type} — {item.source}")
    blocks.append(
        _enrich(
            _block(
                type_="NUMBERED_LIST",
                block_code="APP.INVENTORY",
                items=listing or ["{{APPENDICES.INVENTORY}}"],
                origin="SOURCE_DERIVED",
                unresolved=[] if listing else ["{{APPENDICES.INVENTORY}}"],
            ),
            resolution_status="RESOLVED" if listing else "UNRESOLVED",
            display_as_final=bool(listing),
            content_type="CANONICAL_VALUE" if listing else "PLACEHOLDER",
            appendix_inventory=[i.to_dict() for i in inventory],
        )
    )
    if not listing:
        unresolved.append("{{APPENDICES.INVENTORY}}")

    has_forms = False
    for item in inventory:
        itype = str(item.type)
        if itype in {"STATIC_VERIFIED", "FORM"}:
            if itype == "FORM" or (item.block_id or "").startswith("APP."):
                has_forms = True
            blocks.append(
                _enrich(
                    _block(
                        type_="TEXT",
                        block_code=f"APP.STATIC.{item.block_id or 'BLOCK'}",
                        text=(
                            f"Приложение ({item.block_id or item.title}): содержимое сохранено "
                            f"как STATIC_VERIFIED ({item.source}); форма не переписывается."
                        ),
                        origin=STATIC_VERIFIED,
                    ),
                    resolution_status="RESOLVED",
                    display_as_final=True,
                    content_type="STATIC_VERIFIED",
                    canonical_source=item.source,
                )
            )
        elif item.block_id == "SIGNATURES" or (
            itype == "DYNAMIC_CANONICAL" and (item.render_target or "") == "SIGNATURES"
        ):
            signers = signature_table_rows(ctx)
            persons = list(ctx.get("persons") or [])
            orgs = list(ctx.get("organizations") or [])
            if signers or persons or orgs:
                blocks.append(
                    _enrich(
                        _block(
                            type_="TABLE",
                            block_code="APP.SIGNATURES",
                            table_key="SIGNATURES",
                            origin="SOURCE_DERIVED",
                        ),
                        resolution_status="RESOLVED",
                        display_as_final=True,
                        content_type="CANONICAL_VALUE",
                        canonical_source="StudyAdministration/persons",
                    )
                )
            else:
                unresolved.append("{{SIGNATURES}}")
                gaps.append(
                    _gap(
                        "APPENDICES",
                        "Signature persons/organizations missing — names/dates not invented",
                        importance="HIGH",
                        blocking=True,
                    )
                )
                blocks.append(
                    _enrich(
                        _block(
                            type_="TEXT",
                            block_code="APP.SIGNATURES.MISSING",
                            text="{{SIGNATURES}}",
                            unresolved=["{{SIGNATURES}}"],
                            origin="PLACEHOLDER",
                        ),
                        resolution_status="UNRESOLVED",
                        display_as_final=False,
                        knowledge_gaps=gaps[-1:],
                    )
                )
        elif item.block_id == "STUDY_METADATA":
            # Inventory-only awareness — no invented metadata table rows
            blocks.append(
                _enrich(
                    _block(
                        type_="TEXT",
                        block_code="APP.STUDY_METADATA.NOTE",
                        text="Метаданные исследования: см. канонические поля Study (без выдуманных значений).",
                        origin="SOURCE_DERIVED",
                    ),
                    resolution_status="RESOLVED",
                    display_as_final=True,
                    content_type="CANONICAL_VALUE",
                    canonical_source="study",
                )
            )

    if has_forms:
        blocks.append(
            _enrich(
                _block(
                    type_="REFERENCE",
                    block_code="APP.REF.A",
                    target_type="appendix",
                    target_id="A",
                    display_text="Приложение A",
                    origin="SOURCE_DERIVED",
                ),
                resolution_status="RESOLVED",
                display_as_final=True,
                content_type="REFERENCE",
            )
        )

    return blocks, list(dict.fromkeys(src)), unresolved


def gen_conclusion_12b4(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    test = _product_name(ctx.get("product"))
    ref = _product_name(ctx.get("reference_product"))
    study = ctx.get("study") or {}
    study_title = study.get("title")
    design = ctx.get("design") or {}
    dtype = design.get("type") or consistency.get("design")
    design_disp = None
    if dtype:
        design_disp = resolve_display(str(dtype), context="design", fallback=None)
        if not design_disp or design_disp == str(dtype):
            design_disp = resolve_display(str(dtype), context="design_long", fallback=str(dtype))
        if design_disp and find_raw_enums_in_text(str(design_disp)):
            design_disp = resolve_display(str(dtype), context="design_short", fallback=None)
        if design_disp and find_raw_enums_in_text(str(design_disp)):
            design_disp = None

    # Only if product + design + (reference or study title) resolved
    if not test or not design_disp or not (ref or study_title):
        gap = _gap(
            "CONCLUSION",
            "Critical study identity missing for conclusion — results not invented",
            importance="CRITICAL",
            blocking=True,
        )
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="CONCLUSION.REQUIRED",
                    text="{{CONCLUSION.REQUIRED}}",
                    unresolved=["{{CONCLUSION.REQUIRED}}"],
                    origin="PLACEHOLDER",
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[gap],
            )
        ], [], ["{{CONCLUSION.REQUIRED}}"]

    if ref:
        text = (
            f"В настоящем исследовании планируется оценить биоэквивалентность {test} "
            f"в сравнении с {ref} в дизайне {design_disp}."
        )
    else:
        text = (
            f"В настоящем исследовании «{study_title}» планируется оценить биоэквивалентность "
            f"{test} в дизайне {design_disp}."
        )

    # Periods / food if known (DisplayValueRegistry) — no invention
    periods = design.get("periods")
    if periods is not None:
        text += f" Число периодов: {periods}."

    food_raw = (ctx.get("food") or {}).get("condition") or design.get("food_condition")
    if food_raw:
        food_disp = resolve_display(str(food_raw), context="food", fallback=None)
        if food_disp and not find_raw_enums_in_text(str(food_disp)):
            text += f" Условия приёма пищи: {food_disp}."

    counts = get_canonical_subject_counts(ctx)
    if counts.randomized_n is not None:
        text += f" Планируемое число рандомизированных субъектов: {counts.randomized_n}."

    # MUST NOT invent study results / efficacy / safety / PK outcomes
    return [
        _enrich(
            _block(
                type_="TEXT",
                block_code="CONCLUSION.PLAN",
                text=text,
                origin="SOURCE_DERIVED",
                rule_id="CONCLUSION.DETERMINISTIC",
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="CANONICAL_VALUE",
            canonical_source="product+design+reference|study.title",
        )
    ], [], find_unresolved_markers(text)


def gen_literature_12b4(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    entries = build_bibliography(ctx)
    if not entries:
        gap = _gap(
            "SOURCES",
            "No sources available for literature list — citations not invented",
            importance="HIGH",
            blocking=True,
        )
        return [
            _enrich(
                _block(
                    type_="TEXT",
                    block_code="SOURCES.LIST.MISSING",
                    text="{{SOURCES.LIST}}",
                    unresolved=["{{SOURCES.LIST}}"],
                    origin="PLACEHOLDER",
                ),
                resolution_status="UNRESOLVED",
                display_as_final=False,
                knowledge_gaps=[gap],
            )
        ], [], ["{{SOURCES.LIST}}"]

    items = []
    src_ids: list[str] = []
    for e in entries:
        cite = e.citation or e.title or e.reference_id
        items.append(str(cite))
        if e.source_id:
            src_ids.append(str(e.source_id))

    blocks = [
        _enrich(
            _block(
                type_="NUMBERED_LIST",
                block_code="SOURCES.LIST",
                items=items,
                origin="SOURCE_DERIVED",
                source_ids=list(dict.fromkeys(src_ids)),
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="CANONICAL_VALUE",
            bibliography=[e.to_dict() for e in entries],
        ),
        _enrich(
            _block(
                type_="TABLE",
                block_code="SOURCES.TABLE",
                table_key="SOURCES",
                origin="SOURCE_DERIVED",
                source_ids=list(dict.fromkeys(src_ids)),
            ),
            resolution_status="RESOLVED",
            display_as_final=True,
            content_type="TABLE",
        ),
    ]
    return blocks, list(dict.fromkeys(src_ids)), []


CORE_12B4_GENERATORS: dict[str, Any] = {
    "appendices": gen_appendices_12b4,
    "conclusion": gen_conclusion_12b4,
    "literature": gen_literature_12b4,
}
