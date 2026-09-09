"""Phase 11B P0 protocol section generators — canonical-driven, no invented evidence."""

from __future__ import annotations

from typing import Any, Callable

from app.domain.display_value_registry import resolve_display
from app.domain.eligibility_render import render_eligibility_list
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


def _orgs_by_roles(ctx: dict, roles: set[str]) -> list[dict]:
    orgs = ctx.get("organizations") or []
    roles_u = {r.upper() for r in roles}
    return [o for o in orgs if str(o.get("role") or "OTHER").upper() in roles_u]


def _format_org(o: dict) -> str:
    parts = [o.get("name") or "{{ORG.NAME}}"]
    if o.get("address"):
        parts.append(str(o["address"]))
    if o.get("country"):
        parts.append(str(o["country"]))
    contact = []
    if o.get("contact_phone"):
        contact.append(str(o["contact_phone"]))
    if o.get("contact_email"):
        contact.append(str(o["contact_email"]))
    if contact:
        parts.append(", ".join(contact))
    return " — ".join(parts)


def _verified_claims(ctx: dict, field_names: set[str]) -> list[dict]:
    claims = ctx.get("evidence_claims") or []
    wanted = {f.lower() for f in field_names}
    out = []
    for c in claims:
        fn = str(c.get("field_name") or "").lower()
        if fn not in wanted:
            continue
        status = str(c.get("status") or "").upper()
        if status in {"VERIFIED", "EXPERT_VERIFIED", "APPLIED"}:
            out.append(c)
        elif status in {"PROPOSED", "AI_PROPOSED"} and not out:
            # keep proposed only as fallback later
            out.append(c)
    # Prefer verified
    verified = [c for c in out if str(c.get("status") or "").upper() in {"VERIFIED", "EXPERT_VERIFIED", "APPLIED"}]
    return verified if verified else []


def _claims_text(claims: list[dict]) -> tuple[str, list[str]]:
    lines = []
    src: list[str] = []
    for c in claims:
        val = c.get("value") or ""
        if not val:
            continue
        lines.append(str(val).strip())
        for s in c.get("source_ids") or []:
            src.append(str(s))
    return " ".join(lines), sorted(set(src))


def gen_sponsor(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    sponsor = ctx.get("sponsor") or {}
    name = sponsor.get("name") or sponsor.get("legal_name")
    if not name:
        # try org role SPONSOR
        orgs = _orgs_by_roles(ctx, {"SPONSOR"})
        if orgs:
            name = orgs[0].get("name")
            sponsor = {**orgs[0], "name": name}
    if not name:
        return [
            _block(
                type_="TEXT",
                text="{{SPONSOR.NAME}}",
                unresolved=["{{SPONSOR.NAME}}"],
                origin="TEMPLATE",
            )
        ], [], ["{{SPONSOR.NAME}}"]
    parts = [f"Спонсор: {name}"]
    if sponsor.get("address"):
        parts.append(f"Адрес: {sponsor['address']}")
    if sponsor.get("country"):
        parts.append(f"Страна: {sponsor['country']}")
    if sponsor.get("contact_phone"):
        parts.append(f"Тел.: {sponsor['contact_phone']}")
    if sponsor.get("contact_email"):
        parts.append(f"E-mail: {sponsor['contact_email']}")
    text = ". ".join(parts) + "."
    return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED")], [], find_unresolved_markers(text)


def gen_org_section(roles: set[str], placeholder: str):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        orgs = _orgs_by_roles(ctx, roles)
        if not orgs:
            return [
                _block(type_="TEXT", text=placeholder, unresolved=[placeholder], origin="TEMPLATE")
            ], [], [placeholder]
        items = [_format_org(o) for o in orgs]
        return [_block(type_="NUMBERED_LIST", items=items, origin="SOURCE_DERIVED")], [], find_unresolved_markers(items)

    return _inner


def gen_signatures(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    sponsor = ctx.get("sponsor") or {}
    inv = _orgs_by_roles(ctx, {"INVESTIGATOR", "PRINCIPAL_INVESTIGATOR", "CLINICAL_SITE"})
    blocks = [_block(type_="TABLE", table_key="SIGNATURES", origin="SOURCE_DERIVED")]
    unresolved = []
    if sponsor.get("name"):
        blocks.append(
            _block(
                type_="TEXT",
                text=f"Подпись спонсора: {sponsor.get('name')}",
                origin="SOURCE_DERIVED",
            )
        )
    else:
        unresolved.append("{{SIGNATURE.SPONSOR}}")
        blocks.append(
            _block(
                type_="TEXT",
                text="{{SIGNATURE.SPONSOR}}",
                unresolved=["{{SIGNATURE.SPONSOR}}"],
                origin="TEMPLATE",
            )
        )
    if inv:
        blocks.append(
            _block(
                type_="TEXT",
                text=f"Подпись исследователя / центра: {inv[0].get('name')}",
                origin="SOURCE_DERIVED",
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
    return blocks, [], unresolved


def gen_dose_rationale(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    """Dose from Product model first; evidence claims if present; never invent."""
    product = ctx.get("product") or {}
    dosage = product.get("dosage")
    form = product.get("dosage_form")
    claims = _verified_claims(ctx, {"dose", "dosage", "dosing", "dose_rationale"})
    parts = []
    src: list[str] = []
    if dosage:
        line = f"Доза исследуемого препарата: {dosage}"
        if form:
            line += f" ({form})"
        parts.append(line)
        for s in product.get("source_ids") or []:
            src.append(str(s))
    if claims:
        text, claim_src = _claims_text(claims)
        if text:
            parts.append(text)
            src.extend(claim_src)
    if parts:
        return [
            _block(type_="TEXT", text=" ".join(parts), origin="SOURCE_DERIVED", source_ids=sorted(set(src)))
        ], sorted(set(src)), find_unresolved_markers(parts)
    return [
        _block(
            type_="TEXT",
            text="{{EVIDENCE.DOSE_RATIONALE}}",
            unresolved=["{{EVIDENCE.DOSE_RATIONALE}}"],
            origin="TEMPLATE",
        )
    ], [], ["{{EVIDENCE.DOSE_RATIONALE}}"]


def gen_evidence_narrative(field_names: set[str], placeholder: str, heading_hint: str):
    """Evidence-backed narrative; never invent if no verified claims."""

    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        claims = _verified_claims(ctx, field_names)
        if claims:
            text, src = _claims_text(claims)
            if text:
                return [
                    _block(type_="TEXT", text=text, origin="SOURCE_DERIVED", source_ids=src)
                ], src, find_unresolved_markers(text)
        # sources list as weak fallback for literature-like sections only
        if "literature" in field_names or "regulatory" in field_names:
            sources = ctx.get("sources") or []
            if sources:
                items = [
                    f"{s.get('type') or 'Source'}: {s.get('title') or s.get('id')}"
                    for s in sources
                ]
                return [
                    _block(
                        type_="LIST",
                        items=items,
                        origin="SOURCE_DERIVED",
                        source_ids=[str(s.get("id")) for s in sources if s.get("id")],
                    )
                ], [str(s.get("id")) for s in sources if s.get("id")], []
        return [
            _block(
                type_="TEXT",
                text=placeholder,
                unresolved=[placeholder],
                origin="TEMPLATE",
            )
        ], [], [placeholder]

    return _inner


def gen_test_product_details(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    p = ctx.get("product") or {}
    if not p:
        return [
            _block(type_="TEXT", text="{{TEST_PRODUCT.MISSING}}", unresolved=["{{TEST_PRODUCT.MISSING}}"])
        ], [], ["{{TEST_PRODUCT.MISSING}}"]
    lines = [
        f"Название: {p.get('trade_name') or '{{TEST_PRODUCT.TRADE_NAME}}'}",
        f"МНН: {p.get('inn') or '{{TEST_PRODUCT.INN}}'}",
        f"Производитель: {p.get('manufacturer') or '{{TEST_PRODUCT.MANUFACTURER}}'}",
        f"Доза: {p.get('dosage') or '{{TEST_PRODUCT.DOSAGE}}'}",
        f"Форма: {p.get('dosage_form') or '{{TEST_PRODUCT.DOSAGE_FORM}}'}",
        f"Путь введения: {p.get('route') or '{{TEST_PRODUCT.ROUTE}}'}",
    ]
    src = list(p.get("source_ids") or []) if isinstance(p.get("source_ids"), list) else []
    return [
        _block(type_="NUMBERED_LIST", items=lines, origin="SOURCE_DERIVED", source_ids=src),
        _block(type_="TABLE", table_key="TEST_PRODUCT"),
    ], src, find_unresolved_markers(lines)


def gen_stop_rules(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    elig = ctx.get("eligibility") or {}
    excl = render_eligibility_list(elig.get("exclusion") or [], numbered=True)
    if excl and excl != ["{{ELIGIBILITY.EXCLUSION}}"]:
        items = [
            "Исследование может быть остановлено для отдельного субъекта при наступлении критериев исключения:",
            *excl,
        ]
        return [_block(type_="NUMBERED_LIST", items=items, origin="SOURCE_DERIVED")], [], []
    text = (
        "Правила остановки / исключения субъектов определяются критериями исключения "
        "и решением исследователя. {{STUDY.STOP_RULES}}"
    )
    return [_block(type_="TEXT", text=text, unresolved=["{{STUDY.STOP_RULES}}"])], [], ["{{STUDY.STOP_RULES}}"]


def gen_drug_accountability(kind: str):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        if kind == "test":
            p = ctx.get("product") or {}
            label = "тестового"
            name = p.get("trade_name") or p.get("inn") or "{{TEST_PRODUCT.NAME}}"
        elif kind == "reference":
            p = ctx.get("reference_product") or {}
            label = "референтного"
            name = p.get("trade_name") or p.get("inn") or "{{REFERENCE_PRODUCT.NAME}}"
        else:
            p = ctx.get("product") or {}
            r = ctx.get("reference_product") or {}
            text = (
                f"Учёт и хранение препаратов исследования выполняются в соответствии с процедурами центра. "
                f"Тест: {p.get('trade_name') or p.get('inn') or '{{TEST_PRODUCT.NAME}}'}; "
                f"референт: {r.get('trade_name') or r.get('inn') or '{{REFERENCE_PRODUCT.NAME'}}}. "
                f"Условия хранения: {p.get('storage_conditions') or r.get('storage_conditions') or '{{PRODUCT.STORAGE}}'}."
            )
            return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED")], [], find_unresolved_markers(text)
        text = (
            f"Учёт {label} препарата ({name}): получение, хранение, выдача и возврат "
            f"фиксируются в учётной документации центра."
        )
        return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED")], [], find_unresolved_markers(text)

    return _inner


def gen_blinding(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    design = ctx.get("design") or {}
    blinding = design.get("blinding") or design.get("masking")
    if blinding:
        human_b = resolve_display(str(blinding), context="blinding", fallback=None)
        # Never emit raw enum codes into protocol text
        if human_b and human_b != str(blinding):
            text = f"Маскировка / ослепление: {human_b}."
        elif str(blinding).upper() in {"OPEN", "OPEN_LABEL"}:
            text = "Исследование проводится как открытое (без маскировки)."
        else:
            text = "Маскировка / ослепление задаётся дизайном исследования."
        return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED")], [], find_unresolved_markers(text)
    # open-label crossover is common — state from design type without inventing details
    dtype = design.get("type")
    human = resolve_display(dtype, context="design", fallback="")
    text = (
        f"Исследование проводится как открытое ({human or 'дизайн задан в Study Model'}). "
        "Процедуры раскрытия кодов рандомизации применяются при необходимости по SOP центра."
    )
    return [_block(type_="TEXT", text=text, origin="RULE_DERIVED", rule_id="DESIGN.BLINDING")], [], []


def gen_subject_numbering(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    n = variables.get("randomized_n") or "{{SUBJECTS.RANDOMIZED_N}}"
    text = (
        f"Каждому рандомизированному субъекту присваивается индивидуальный номер. "
        f"Планируемое число рандомизированных субъектов: {n}."
    )
    return [_block(type_="TEXT", text=text, origin="CALCULATED")], [], find_unresolved_markers(text)


def gen_primary_data(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    text = (
        "Данные, регистрируемые непосредственно в ИРК без предварительной записи, "
        "определяются процедурами центра и перечнем CRF. {{CRF.PRIMARY_DATA_LIST}}"
    )
    return [
        _block(type_="TEXT", text=text, unresolved=["{{CRF.PRIMARY_DATA_LIST}}"], origin="TEMPLATE")
    ], [], ["{{CRF.PRIMARY_DATA_LIST}}"]


def gen_period(period: int):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        food = variables.get("food_condition") or "{{FOOD.CONDITION}}"
        design = ctx.get("design") or {}
        periods = int(design.get("periods") or 0)
        if period > periods > 0:
            return [
                _block(
                    type_="TEXT",
                    text=f"Период {period} не применим для текущего дизайна ({periods} период(ов)).",
                    origin="RULE_DERIVED",
                )
            ], [], []
        samp = ctx.get("sampling") or {}
        n_pts = samp.get("total_points_per_period") or len(samp.get("points") or [])
        text = (
            f"Период {period}: госпитализация / процедуры приёма препарата, "
            f"отбор крови ({n_pts} точек на период), наблюдение. Условие пищи: {food}."
        )
        blocks = [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED")]
        if period == 1:
            blocks.append(_block(type_="TABLE", table_key="MEAL_TIMING", origin="SOURCE_DERIVED"))
        return blocks, [], find_unresolved_markers(text)

    return _inner


def gen_procedures_overview(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    design = ctx.get("design") or {}
    periods = design.get("periods") or "{{DESIGN.PERIODS}}"
    items = [
        "Скрининг и получение согласия",
        "Рандомизация",
        f"Периоды лечения (число периодов: {periods})",
        "Отбор проб крови для PK",
        "Завершающее обследование",
    ]
    return [
        _block(type_="NUMBERED_LIST", items=items, origin="RULE_DERIVED"),
        _block(type_="TABLE", table_key="SCHEDULE_OF_ASSESSMENTS", origin="SOURCE_DERIVED"),
    ], [], find_unresolved_markers(items)


def gen_screening(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    elig = ctx.get("eligibility") or {}
    incl = render_eligibility_list(elig.get("inclusion") or [], numbered=True)
    text = "На скрининге выполняется проверка критериев включения/невключения и стандартные процедуры центра."
    blocks = [_block(type_="TEXT", text=text, origin="RULE_DERIVED")]
    if incl:
        blocks.append(_block(type_="NUMBERED_LIST", items=["Критерии включения:"] + incl, origin="SOURCE_DERIVED"))
    return blocks, [], []


def gen_static_verified(text: str, block_id: str):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        return [
            _block(
                type_="TEXT",
                text=text,
                origin="TEMPLATE",
                block_code=block_id,
                rule_id="STATIC_VERIFIED",
            )
        ], [], []

    return _inner


def gen_stats_from_config(kind: str):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        cfg = ctx.get("statistical_config") or {}
        if kind == "alpha":
            alpha = cfg.get("alpha")
            if alpha is None:
                alpha = 0.05
            text = (
                f"Уровень значимости α={alpha} (двусторонний) для построения 90% доверительного интервала."
            )
            return [
                _block(type_="TEXT", text=text, origin="RULE_DERIVED", rule_id="STATISTICS.ALPHA")
            ], [], []
        if kind == "be":
            lo = cfg.get("be_lower")
            hi = cfg.get("be_upper")
            if lo is None:
                lo = 0.8
            if hi is None:
                hi = 1.25
            text = f"BE: {float(lo)*100:.2f}% ≤ 90% CI (T/R) ≤ {float(hi)*100:.2f}%"
            return [
                _block(type_="FORMULA", text=text, origin="RULE_DERIVED", rule_id="STATISTICS.BE_LIMITS")
            ], [], []
        if kind == "anova":
            design = variables.get("design_type") or "{{DESIGN.TYPE}}"
            text = (
                f"Дисперсионный анализ (ANOVA) выполняется для логарифмически преобразованных PK-параметров "
                f"в рамках дизайна ({design})."
            )
            return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], find_unresolved_markers(text)
        if kind == "descriptive":
            text = (
                "Описательная статистика включает n, среднее, SD, CV%, медиану, мин/макс "
                "для концентраций и PK-параметров."
            )
            return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []
        if kind == "populations":
            n = variables.get("evaluable_n") or "{{SUBJECTS.EVALUABLE_N}}"
            text = (
                f"Анализ биоэквивалентности выполняется в популяции оцениваемых субъектов (N={n}). "
                "Популяции безопасности и рандомизированных субъектов описываются отдельно."
            )
            return [_block(type_="TEXT", text=text, origin="CALCULATED")], [], find_unresolved_markers(text)
        if kind == "missing":
            text = (
                "Отсутствующие, не подлежащие анализу и фальсифицированные данные учитываются "
                "согласно статистическому плану; решения документируются."
            )
            return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []
        if kind == "deviations":
            text = (
                "Любые отклонения от первоначального статистического плана оформляются "
                "и обосновываются до анализа."
            )
            return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []
        if kind == "stopping_stats":
            text = (
                "Критерии досрочного прекращения исследования определяются протоколом и решением спонсора/"
                "исследователя; промежуточный анализ — при наличии в дизайне."
            )
            return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []
        if kind == "outliers":
            text = (
                "Исключение резко выделяющихся наблюдений выполняется по заранее определённым правилам "
                "и документируется."
            )
            return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []
        if kind == "safety_stats":
            text = "Анализ безопасности носит описательный характер и выполняется на всех подвергшихся воздействию субъектов."
            return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []
        return [_block(type_="TEXT", text="{{STATISTICS.SECTION}}", unresolved=["{{STATISTICS.SECTION}}"])], [], ["{{STATISTICS.SECTION}}"]

    return _inner


def gen_eval_methods(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    obs = variables.get("observation_duration")
    unit = variables.get("observation_unit") or "h"
    n = variables.get("n_points")
    text = (
        f"Оценка PK выполняется по точкам отбора крови ({n} на период) "
        f"в течение {obs} {unit}."
    )
    return [_block(type_="TEXT", text=text, origin="CALCULATED")], [], find_unresolved_markers(text)


def gen_bio_detail(kind: str):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        analytes = ctx.get("analytes") or []
        names = ", ".join(a.get("name") or "?" for a in analytes) or "{{ANALYTES.NAMES}}"
        if kind == "method":
            text = f"Биоаналитическое определение: {names}. Метод: {{BIOANALYSIS.METHOD}}."
            return [_block(type_="TEXT", text=text, unresolved=["{{BIOANALYSIS.METHOD}}"])], [], ["{{BIOANALYSIS.METHOD}}"]
        if kind == "validation":
            return [
                _block(
                    type_="TEXT",
                    text="Валидация биоаналитического метода должна быть завершена до анализа образцов исследования. {{BIOANALYSIS.VALIDATION}}",
                    unresolved=["{{BIOANALYSIS.VALIDATION}}"],
                )
            ], [], ["{{BIOANALYSIS.VALIDATION}}"]
        if kind == "analysis":
            return [
                _block(
                    type_="TEXT",
                    text="Анализ образцов выполняется сериями (analytical runs) в соответствии с валидированным методом.",
                    origin="RULE_DERIVED",
                )
            ], [], []
        if kind == "acceptance":
            return [
                _block(
                    type_="TEXT",
                    text="Критерии приёмки/отклонения аналитических серий задаются SOP лаборатории и валидационным отчётом. {{BIOANALYSIS.RUN_ACCEPTANCE}}",
                    unresolved=["{{BIOANALYSIS.RUN_ACCEPTANCE}}"],
                )
            ], [], ["{{BIOANALYSIS.RUN_ACCEPTANCE}}"]
        return [], [], []

    return _inner


def gen_concomitant(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    text = (
        "Сопутствующая и неотложная терапия допускается по решению исследователя "
        "с фиксацией в ИРК; запрещённые препараты определяются протоколом центра."
    )
    return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []


def gen_restrictions(kind: str):
    def _inner(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
        if kind == "activity":
            text = "Ограничения физической активности задаются для минимизации вариабельности PK и обеспечения безопасности."
        elif kind == "contraception":
            text = "Требования к контрацепции применяются к субъектам детородного потенциала согласно критериям включения."
        elif kind == "compliance":
            text = "Соблюдение процедур контролируется персоналом центра (явка, приём препарата, ограничения)."
        elif kind == "followup":
            text = "За выбывшими добровольцами проводится последующее наблюдение по решению исследователя."
        else:
            text = "Ограничения лечения до/во время исследования определяются протоколом."
        return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []

    return _inner


def gen_sample_prep(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    bv = ctx.get("blood_volume") or {}
    vol = bv.get("blood_volume_per_pk_sample_ml")
    text = (
        f"Подготовка образцов крови для PK выполняется по SOP лаборатории"
        f"{f' (объём на пробу: {vol} мл)' if vol else ''}."
    )
    return [_block(type_="TEXT", text=text, origin="SOURCE_DERIVED")], [], []


def gen_final_exam(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    text = "Завершающее обследование включает клиническую оценку безопасности и необходимые лабораторные исследования."
    return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []


def gen_completion(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    text = "Исследование считается завершённым после выполнения процедур последнего периода и завершающего обследования / досрочного выбытия."
    return [_block(type_="TEXT", text=text, origin="RULE_DERIVED")], [], []


def gen_lab_table(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    return [
        _block(type_="TEXT", text="Лабораторные параметры скрининга/безопасности:", origin="RULE_DERIVED"),
        _block(type_="TABLE", table_key="LAB_PARAMETERS", origin="SOURCE_DERIVED"),
    ], [], []


def gen_safety_methods(section: SectionDef, ctx: dict, variables: dict, consistency: dict):
    text = (
        "Параметры безопасности оцениваются на скрининге, в периоды исследования и при завершении "
        "согласно расписанию процедур."
    )
    return [
        _block(type_="TEXT", text=text, origin="RULE_DERIVED"),
        _block(type_="TABLE", table_key="SCHEDULE_OF_ASSESSMENTS", origin="SOURCE_DERIVED"),
    ], [], []


P0_GENERATORS: dict[str, Callable] = {
    "sponsor": gen_sponsor,
    "sponsor_persons": gen_org_section(
        {"SPONSOR_PERSON", "AUTHORIZED_PERSON", "SPONSOR_SIGNATORY"}, "{{SPONSOR_PERSONS.DETAILS}}"
    ),
    "medical_expert": gen_org_section({"MEDICAL_EXPERT"}, "{{MEDICAL_EXPERT.DETAILS}}"),
    "investigators": gen_org_section(
        {"INVESTIGATOR", "PRINCIPAL_INVESTIGATOR", "CLINICAL_SITE", "CLINICAL_CENTER"},
        "{{INVESTIGATORS.DETAILS}}",
    ),
    "analytical_lab": gen_org_section(
        {"BIOANALYTICAL_LAB", "ANALYTICAL_LAB", "LABORATORY"}, "{{ANALYTICAL_LAB.DETAILS}}"
    ),
    "key_orgs": gen_org_section({"CRO", "KEY", "OTHER", "PHARMACY"}, "{{KEY_ORGS.DETAILS}}"),
    "signatures": gen_signatures,
    "investigator_agreement": gen_org_section(
        {"INVESTIGATOR", "PRINCIPAL_INVESTIGATOR"}, "{{INVESTIGATOR_AGREEMENT.DETAILS}}"
    ),
    "preclinical_clinical_summary": gen_evidence_narrative(
        {"preclinical", "clinical_summary", "efficacy", "clinical"},
        "{{EVIDENCE.CLINICAL_SUMMARY}}",
        "2.2",
    ),
    "risk_benefit": gen_evidence_narrative(
        {"risk", "benefit", "safety_risk", "risk_benefit"},
        "{{EVIDENCE.RISK_BENEFIT}}",
        "2.3",
    ),
    "dose_rationale": gen_dose_rationale,
    "rationale_literature": gen_evidence_narrative(
        {"literature", "regulatory", "guideline"},
        "{{EVIDENCE.LITERATURE_BASIS}}",
        "2.7",
    ),
    "pharmacology": gen_evidence_narrative(
        {"pharmacology", "pk_pd", "mechanism"},
        "{{EVIDENCE.PHARMACOLOGY}}",
        "2.8",
    ),
    "test_product_details": gen_test_product_details,
    "stop_rules": gen_stop_rules,
    "drug_accountability": gen_drug_accountability("both"),
    "drug_accountability_test": gen_drug_accountability("test"),
    "drug_accountability_ref": gen_drug_accountability("reference"),
    "storage_conditions": gen_drug_accountability("both"),
    "randomization_codes": gen_blinding,
    "subject_numbering": gen_subject_numbering,
    "unblinding_sop": gen_blinding,
    "blinding": gen_blinding,
    "primary_data_list": gen_primary_data,
    "procedures_timeline": gen_procedures_overview,
    "screening_procedures": gen_screening,
    "randomization_procedure": lambda s, c, v, cons: (
        [
            _block(
                type_="TEXT",
                text="Рандомизация выполняется до приёма первой дозы; последовательности лечения заданы дизайном.",
                origin="RULE_DERIVED",
            )
        ],
        [],
        [],
    ),
    "period_1": gen_period(1),
    "period_2": gen_period(2),
    "final_exam": gen_final_exam,
    "completion": gen_completion,
    "sample_prep": gen_sample_prep,
    "concomitant_therapy": gen_concomitant,
    "treatment_restrictions": gen_restrictions("treatment"),
    "activity_restrictions": gen_restrictions("activity"),
    "contraception": gen_restrictions("contraception"),
    "compliance": gen_restrictions("compliance"),
    "withdrawal_followup": gen_restrictions("followup"),
    "eval_methods_timing": gen_eval_methods,
    "analytical_method": gen_bio_detail("method"),
    "bio_validation": gen_bio_detail("validation"),
    "sample_analysis": gen_bio_detail("analysis"),
    "run_acceptance": gen_bio_detail("acceptance"),
    "safety_methods": gen_safety_methods,
    "physical_exam": gen_static_verified(
        "Физикальное обследование выполняется на скрининге и по расписанию безопасности.",
        "SAFE.PHYS",
    ),
    "vital_signs": gen_static_verified(
        "Жизненные показатели регистрируются согласно расписанию; критерии отклонений — в таблице протокола.",
        "SAFE.VITALS",
    ),
    "safety_labs": gen_lab_table,
    "ae_framework": gen_static_verified(
        "Регистрация и сообщение о нежелательных явлениях выполняются по стандартным процедурам GCP/протокола.",
        "SAFE.AE",
    ),
    "ae_followup": gen_static_verified(
        "Наблюдение за НЯ продолжается до разрешения или стабилизации по решению исследователя.",
        "SAFE.AE_FU",
    ),
    "pregnancy": gen_static_verified(
        "Случаи беременности подлежат немедленному сообщению и наблюдению по форме протокола.",
        "SAFE.PREG",
    ),
    "alpha": gen_stats_from_config("alpha"),
    "be_criteria": gen_stats_from_config("be"),
    "stopping_rules": gen_stats_from_config("stopping_stats"),
    "missing_data_policy": gen_stats_from_config("missing"),
    "sap_deviations": gen_stats_from_config("deviations"),
    "analysis_populations": gen_stats_from_config("populations"),
    "statistical_analysis": gen_stats_from_config("anova"),
    "descriptive_stats": gen_stats_from_config("descriptive"),
    "anova_methods": gen_stats_from_config("anova"),
    "outliers": gen_stats_from_config("outliers"),
    "safety_analysis": gen_stats_from_config("safety_stats"),
}
