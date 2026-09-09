"""Render helpers for Sponsor / Organization / Person protocol sections."""

from __future__ import annotations

from typing import Any

from app.domain.org_roles import (
    CLINICAL_CENTER_ROLES,
    INVESTIGATOR_PERSON_ROLES,
    KEY_ORG_ROLES,
    LAB_ROLES,
    MEDICAL_EXPERT_ROLES,
    ORG_FINANCING,
    ORG_INSURANCE,
    ORG_SPONSOR,
    SIGNATORY_PERSON_ROLES,
    SPONSOR_PERSON_ROLES,
)


def _role_upper(role: str | None) -> str:
    return str(role or "OTHER").upper()


def orgs_by_roles(ctx: dict, roles: set[str]) -> list[dict]:
    roles_u = {_role_upper(r) for r in roles}
    return [o for o in (ctx.get("organizations") or []) if _role_upper(o.get("role")) in roles_u]


def persons_by_roles(ctx: dict, roles: set[str]) -> list[dict]:
    roles_u = {_role_upper(r) for r in roles}
    return [p for p in (ctx.get("persons") or []) if _role_upper(p.get("role")) in roles_u]


def entity_source_ids(entity: dict | None) -> list[str]:
    if not entity:
        return []
    ids: list[str] = []
    if entity.get("id"):
        ids.append(str(entity["id"]))
    prov = entity.get("provenance") or {}
    for sid in prov.get("source_ids") or entity.get("source_ids") or []:
        ids.append(str(sid))
    return sorted(set(ids))


def format_org(org: dict) -> str:
    name = org.get("name")
    if not name:
        return "{{ORG.NAME}}"
    parts = [str(name)]
    if org.get("address"):
        parts.append(str(org["address"]))
    if org.get("country"):
        parts.append(str(org["country"]))
    contact: list[str] = []
    if org.get("contact_phone"):
        contact.append(str(org["contact_phone"]))
    if org.get("contact_email"):
        contact.append(str(org["contact_email"]))
    if contact:
        parts.append(", ".join(contact))
    return " — ".join(parts)


def format_person(person: dict) -> str:
    name = person.get("full_name") or person.get("name")
    if not name:
        return "{{PERSON.NAME}}"
    parts = [str(name)]
    if person.get("title"):
        parts.append(str(person["title"]))
    contact: list[str] = []
    if person.get("phone") or person.get("contact_phone"):
        contact.append(str(person.get("phone") or person.get("contact_phone")))
    if person.get("email") or person.get("contact_email"):
        contact.append(str(person.get("email") or person.get("contact_email")))
    if contact:
        parts.append(", ".join(contact))
    org_name = person.get("organization_name")
    if org_name:
        parts.append(str(org_name))
    return " — ".join(parts)


def resolve_sponsor(ctx: dict) -> dict | None:
    sponsor = ctx.get("sponsor") or {}
    name = sponsor.get("name") or sponsor.get("legal_name")
    if name:
        return {**sponsor, "name": name}
    orgs = orgs_by_roles(ctx, {ORG_SPONSOR})
    if orgs:
        o = orgs[0]
        return {**o, "name": o.get("name"), "legal_name": o.get("name")}
    return None


def sponsor_persons(ctx: dict) -> list[dict]:
    persons = persons_by_roles(ctx, SPONSOR_PERSON_ROLES)
    if persons:
        return persons
    # Legacy: some projects store authorized persons as org rows
    return orgs_by_roles(ctx, SPONSOR_PERSON_ROLES)


def investigators(ctx: dict) -> list[dict]:
    persons = persons_by_roles(ctx, INVESTIGATOR_PERSON_ROLES)
    if persons:
        return persons
    return orgs_by_roles(ctx, INVESTIGATOR_PERSON_ROLES | {"INVESTIGATOR", "PRINCIPAL_INVESTIGATOR"})


def clinical_centers(ctx: dict) -> list[dict]:
    return orgs_by_roles(ctx, CLINICAL_CENTER_ROLES)


def medical_experts(ctx: dict) -> list[dict]:
    persons = persons_by_roles(ctx, MEDICAL_EXPERT_ROLES)
    if persons:
        return persons
    return orgs_by_roles(ctx, MEDICAL_EXPERT_ROLES)


def analytical_labs(ctx: dict) -> list[dict]:
    return orgs_by_roles(ctx, LAB_ROLES)


def key_organizations(ctx: dict) -> list[dict]:
    return orgs_by_roles(ctx, KEY_ORG_ROLES)


def signatories(ctx: dict) -> list[dict]:
    """Persons preferred for signature table; fallback sponsor + PI org/person."""
    persons = persons_by_roles(ctx, SIGNATORY_PERSON_ROLES)
    if persons:
        return persons
    out: list[dict] = []
    sponsor = resolve_sponsor(ctx)
    if sponsor and sponsor.get("name"):
        out.append(
            {
                "full_name": sponsor["name"],
                "title": "Представитель спонсора",
                "phone": sponsor.get("contact_phone"),
                "email": sponsor.get("contact_email"),
                "role": "SPONSOR_SIGNATORY",
            }
        )
    inv = investigators(ctx)
    if inv:
        row = inv[0]
        if row.get("full_name") or row.get("name"):
            out.append(row)
        elif row.get("name"):
            out.append({**row, "full_name": row["name"], "title": "Главный исследователь"})
    return out


def signature_table_rows(ctx: dict) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for p in signatories(ctx):
        name = p.get("full_name") or p.get("name")
        if not name:
            continue
        if p.get("title"):
            rows.append(["Должность", str(p["title"])])
        rows.append(["ФИО", str(name)])
        phone = p.get("phone") or p.get("contact_phone")
        if phone:
            rows.append(["Тел.", str(phone)])
        email = p.get("email") or p.get("contact_email")
        if email:
            rows.append(["E-mail", str(email)])
    return rows


def insurance_block(ctx: dict) -> tuple[str | None, list[str]]:
    admin = ctx.get("study_administration") or {}
    parts: list[str] = []
    src: list[str] = []
    if admin.get("insurance_provider"):
        parts.append(f"Страховая организация: {admin['insurance_provider']}")
    if admin.get("insurance_policy"):
        parts.append(f"Полис/договор: {admin['insurance_policy']}")
    if admin.get("insurance_details"):
        parts.append(str(admin["insurance_details"]))
    src.extend(entity_source_ids(admin))
    if parts:
        return ". ".join(parts) + ".", src
    orgs = orgs_by_roles(ctx, {ORG_INSURANCE})
    if orgs:
        return format_org(orgs[0]) + ".", entity_source_ids(orgs[0])
    return None, []


def financing_block(ctx: dict) -> tuple[str | None, list[str]]:
    admin = ctx.get("study_administration") or {}
    parts: list[str] = []
    src: list[str] = []
    if admin.get("financing_source"):
        parts.append(f"Источник финансирования: {admin['financing_source']}")
    if admin.get("financing_details"):
        parts.append(str(admin["financing_details"]))
    src.extend(entity_source_ids(admin))
    if parts:
        return ". ".join(parts) + ".", src
    orgs = orgs_by_roles(ctx, {ORG_FINANCING})
    if orgs:
        return format_org(orgs[0]) + ".", entity_source_ids(orgs[0])
    return None, []


def publication_block(ctx: dict) -> tuple[str | None, list[str]]:
    admin = ctx.get("study_administration") or {}
    parts: list[str] = []
    src: list[str] = []
    if admin.get("publication_policy"):
        parts.append(str(admin["publication_policy"]))
    if admin.get("publication_contacts"):
        parts.append(f"Контакты: {admin['publication_contacts']}")
    src.extend(entity_source_ids(admin))
    if parts:
        return " ".join(parts), src
    return None, []
