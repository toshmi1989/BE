"""Phase 11C P1 administrative / organizational protocol generators."""

from __future__ import annotations

from typing import Any, Callable

from app.domain.org_render import (
    analytical_labs,
    clinical_centers,
    entity_source_ids,
    financing_block,
    format_org,
    format_person,
    insurance_block,
    investigators,
    key_organizations,
    medical_experts,
    publication_block,
    resolve_sponsor,
    signature_table_rows,
    sponsor_persons,
)
from app.domain.protocol_consistency import find_unresolved_markers
from app.domain.protocol_sections import SectionDef


def _block(**kwargs) -> dict:
    base = {
        "type": "TEXT",
        "text": None,
        "items": None,
        "table_key": None,
        "target_type": None,
        "target_id": None,
        "display_text": None,
        "unresolved": [],
        "origin": "SOURCE_DERIVED",
        "source_ids": [],
        "block_code": None,
        "rule_id": None,
    }
    base.update(kwargs)
    return base


def _list_or_placeholder(
    items: list[str],
    placeholder: str,
    *,
    source_ids: list[str] | None = None,
) -> tuple[list[dict], list[str], list[str]]:
    if not items:
        return (
            [_block(type_="TEXT", text=placeholder, unresolved=[placeholder], origin="TEMPLATE")],
            [],
            [placeholder],
        )
    return (
        [
            _block(
                type_="NUMBERED_LIST",
                items=items,
                origin="SOURCE_DERIVED",
                source_ids=source_ids or [],
            )
        ],
        source_ids or [],
        find_unresolved_markers(items),
    )


def gen_sponsor(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    sponsor = resolve_sponsor(ctx)
    if not sponsor or not sponsor.get("name"):
        return (
            [_block(type_="TEXT", text="{{SPONSOR.NAME}}", unresolved=["{{SPONSOR.NAME}}"], origin="TEMPLATE")],
            [],
            ["{{SPONSOR.NAME}}"],
        )
    parts = [f"Спонсор: {sponsor['name']}"]
    if sponsor.get("address"):
        parts.append(f"Адрес: {sponsor['address']}")
    if sponsor.get("country"):
        parts.append(f"Страна: {sponsor['country']}")
    if sponsor.get("contact_phone"):
        parts.append(f"Тел.: {sponsor['contact_phone']}")
    if sponsor.get("contact_email"):
        parts.append(f"E-mail: {sponsor['contact_email']}")
    text = ". ".join(parts) + "."
    src = entity_source_ids(sponsor)
    return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED", source_ids=src)], src, find_unresolved_markers(text)


def gen_sponsor_persons(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    rows = sponsor_persons(ctx)
    items = [format_person(p) if p.get("full_name") or p.get("name") else format_org(p) for p in rows]
    src = [sid for p in rows for sid in entity_source_ids(p)]
    return _list_or_placeholder(items, "{{SPONSOR_PERSONS.DETAILS}}", source_ids=src)


def gen_medical_expert(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    rows = medical_experts(ctx)
    items = [format_person(p) if p.get("full_name") else format_org(p) for p in rows]
    src = [sid for p in rows for sid in entity_source_ids(p)]
    return _list_or_placeholder(items, "{{MEDICAL_EXPERT.DETAILS}}", source_ids=src)


def gen_investigators(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks: list[dict] = []
    src: list[str] = []
    unresolved: list[str] = []
    inv = investigators(ctx)
    sites = clinical_centers(ctx)
    if inv:
        items = [format_person(p) if p.get("full_name") or p.get("name") else format_org(p) for p in inv]
        blocks.append(
            _block(type_="TEXT", text="Исследователи:", origin="SOURCE_DERIVED")
        )
        blocks.append(
            _block(type_="NUMBERED_LIST", items=items, origin="SOURCE_DERIVED", source_ids=[])
        )
        for p in inv:
            src.extend(entity_source_ids(p))
    else:
        unresolved.append("{{INVESTIGATORS.DETAILS}}")
        blocks.append(
            _block(
                type_="TEXT",
                text="{{INVESTIGATORS.DETAILS}}",
                unresolved=["{{INVESTIGATORS.DETAILS}}"],
                origin="TEMPLATE",
            )
        )
    if sites:
        site_items = [format_org(o) for o in sites]
        blocks.append(_block(type_="TEXT", text="Клинические центры:", origin="SOURCE_DERIVED"))
        blocks.append(
            _block(type_="NUMBERED_LIST", items=site_items, origin="SOURCE_DERIVED", source_ids=[])
        )
        for o in sites:
            src.extend(entity_source_ids(o))
    elif not inv:
        unresolved.append("{{CLINICAL_CENTERS.DETAILS}}")
    return blocks, sorted(set(src)), unresolved


def gen_analytical_lab(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    rows = analytical_labs(ctx)
    items = [format_org(o) for o in rows]
    src = [sid for o in rows for sid in entity_source_ids(o)]
    return _list_or_placeholder(items, "{{ANALYTICAL_LAB.DETAILS}}", source_ids=src)


def gen_key_orgs(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    rows = key_organizations(ctx)
    items = [format_org(o) for o in rows]
    src = [sid for o in rows for sid in entity_source_ids(o)]
    return _list_or_placeholder(items, "{{KEY_ORGS.DETAILS}}", source_ids=src)


def gen_signatures(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks = [_block(type_="TABLE", table_key="SIGNATURES", origin="SOURCE_DERIVED")]
    unresolved: list[str] = []
    signers = signature_table_rows(ctx)
    sponsor = resolve_sponsor(ctx)
    inv = investigators(ctx)
    if sponsor and sponsor.get("name"):
        blocks.append(
            _block(
                type_="TEXT",
                text=f"Подпись спонсора: {sponsor['name']}",
                origin="SOURCE_DERIVED",
                source_ids=entity_source_ids(sponsor),
            )
        )
    else:
        unresolved.append("{{SIGNATURE.SPONSOR}}")
        blocks.append(
            _block(type_="TEXT", text="{{SIGNATURE.SPONSOR}}", unresolved=["{{SIGNATURE.SPONSOR}}"], origin="TEMPLATE")
        )
    if inv:
        name = inv[0].get("full_name") or inv[0].get("name")
        blocks.append(
            _block(
                type_="TEXT",
                text=f"Подпись исследователя: {name}",
                origin="SOURCE_DERIVED",
                source_ids=entity_source_ids(inv[0]),
            )
        )
    else:
        unresolved.append("{{SIGNATURE.INVESTIGATOR}}")
        blocks.append(
            _block(
                type_="TEXT",
                text="{{SIGNATURE.INVESTIGATOR}}",
                unresolved=["{{SIGNATURE.INVESTIGATOR}}"],
                origin="TEMPLATE",
            )
        )
    if not signers:
        unresolved.append("{{SIGNATURES.TABLE}}")
    return blocks, [], unresolved


def gen_investigator_agreement(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    inv = investigators(ctx)
    if not inv:
        return (
            [
                _block(
                    type_="TEXT",
                    text="{{INVESTIGATOR_AGREEMENT.DETAILS}}",
                    unresolved=["{{INVESTIGATOR_AGREEMENT.DETAILS}}"],
                    origin="TEMPLATE",
                )
            ],
            [],
            ["{{INVESTIGATOR_AGREEMENT.DETAILS}}"],
        )
    name = inv[0].get("full_name") or inv[0].get("name") or "{{INVESTIGATOR.NAME}}"
    text = (
        f"Главный исследователь ({name}) подтверждает ознакомление с протоколом, "
        "обязуется проводить исследование в соответствии с GCP, локальными требованиями "
        "и настоящим протоколом."
    )
    src = entity_source_ids(inv[0])
    return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED", source_ids=src)], src, find_unresolved_markers(text)


def gen_financing_insurance(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    blocks: list[dict] = []
    unresolved: list[str] = []
    src: list[str] = []
    ins_text, ins_src = insurance_block(ctx)
    fin_text, fin_src = financing_block(ctx)
    if ins_text:
        blocks.append(_block(type_="TEXT", text=f"Страхование. {ins_text}", origin="SOURCE_DERIVED", source_ids=ins_src))
        src.extend(ins_src)
    else:
        unresolved.append("{{INSURANCE.DETAILS}}")
        blocks.append(
            _block(type_="TEXT", text="{{INSURANCE.DETAILS}}", unresolved=["{{INSURANCE.DETAILS}}"], origin="TEMPLATE")
        )
    if fin_text:
        blocks.append(_block(type_="TEXT", text=f"Финансирование. {fin_text}", origin="SOURCE_DERIVED", source_ids=fin_src))
        src.extend(fin_src)
    else:
        unresolved.append("{{FINANCING.DETAILS}}")
        blocks.append(
            _block(type_="TEXT", text="{{FINANCING.DETAILS}}", unresolved=["{{FINANCING.DETAILS}}"], origin="TEMPLATE")
        )
    return blocks, sorted(set(src)), unresolved


def gen_publications(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    text, src = publication_block(ctx)
    if not text:
        return (
            [
                _block(
                    type_="TEXT",
                    text="{{PUBLICATION.POLICY}}",
                    unresolved=["{{PUBLICATION.POLICY}}"],
                    origin="TEMPLATE",
                )
            ],
            [],
            ["{{PUBLICATION.POLICY}}"],
        )
    return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED", source_ids=src)], src, find_unresolved_markers(text)


P1_GENERATORS: dict[str, Callable] = {
    "sponsor": gen_sponsor,
    "sponsor_persons": gen_sponsor_persons,
    "medical_expert": gen_medical_expert,
    "investigators": gen_investigators,
    "analytical_lab": gen_analytical_lab,
    "key_orgs": gen_key_orgs,
    "signatures": gen_signatures,
    "investigator_agreement": gen_investigator_agreement,
    "financing_insurance": gen_financing_insurance,
    "publications": gen_publications,
}

# Export for protocol_tables signature rows
build_signature_table_rows = signature_table_rows
