"""PlaceholderRegistry — Phase 30.5 deterministic DRAFT/FINAL placeholder policy.

Classifications:
  REQUIRED_DYNAMIC — must be populated for FINAL; DRAFT may keep {{CODE}}
  OPTIONAL_DYNAMIC — may remain in FINAL only if final_policy=ALLOW
  STATIC_TEMPLATE  — should not appear as unresolved (treat as REQUIRED if seen)
  UNKNOWN          — not in registry → always blocks FINAL
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_.]+)\}\}")

# Legacy classification labels (kept for older callers)
ALLOWED_DRAFT = "ALLOWED_DRAFT_PLACEHOLDER"
REQUIRED_FIELD = "REQUIRED_FIELD"
UNRESOLVED_CRITICAL = "UNRESOLVED_CRITICAL"
LEGACY_TEMPLATE = "LEGACY_TEMPLATE_PLACEHOLDER"

# Phase 30.5 taxonomy
REQUIRED_DYNAMIC = "REQUIRED_DYNAMIC"
OPTIONAL_DYNAMIC = "OPTIONAL_DYNAMIC"
STATIC_TEMPLATE = "STATIC_TEMPLATE"
UNKNOWN = "UNKNOWN"

FINAL_BLOCK = "BLOCK"
FINAL_ALLOW = "ALLOW"


@dataclass(frozen=True)
class PlaceholderSpec:
    code: str
    section: str
    classification: str  # REQUIRED_DYNAMIC | OPTIONAL_DYNAMIC | STATIC_TEMPLATE
    source: str
    mapped: bool
    final_policy: str  # BLOCK | ALLOW
    resolve_hint: str
    tab: str = "gaps"


# Complete registry for UPDCB DRAFT residual set + common protocol markers.
# Any code not listed → UNKNOWN → FINAL BLOCK.
PLACEHOLDER_CATALOG: dict[str, PlaceholderSpec] = {
    # --- Sampling / PK / observation (required medical) ---
    "SAMPLING.POINTS": PlaceholderSpec(
        "SAMPLING.POINTS", "4.4.2", REQUIRED_DYNAMIC, "SamplingPlan.points", True, FINAL_BLOCK,
        "Утвердите SamplingPlan (точки отбора)", "decisions",
    ),
    "SAMPLING.POINT": PlaceholderSpec(
        "SAMPLING.POINT", "4.4.2", REQUIRED_DYNAMIC, "SamplingPlan.points", True, FINAL_BLOCK,
        "Утвердите SamplingPlan (точки отбора)", "decisions",
    ),
    "SAMPLING.TIME_H": PlaceholderSpec(
        "SAMPLING.TIME_H", "4.4.2", REQUIRED_DYNAMIC, "SamplingPlan.points", True, FINAL_BLOCK,
        "Утвердите SamplingPlan (время точек)", "decisions",
    ),
    "SAMPLING.VOLUME": PlaceholderSpec(
        "SAMPLING.VOLUME", "4.4.2", REQUIRED_DYNAMIC, "blood_volume / SamplingPlan", True, FINAL_BLOCK,
        "Задайте объём пробы в SamplingPlan или blood_volume", "decisions",
    ),
    "SAMPLING.DEVIATION": PlaceholderSpec(
        "SAMPLING.DEVIATION", "4.4.2", REQUIRED_DYNAMIC, "SamplingPlan.deviation", True, FINAL_BLOCK,
        "Задайте допустимое отклонение точек отбора", "decisions",
    ),
    "SAMPLING.N_POINTS": PlaceholderSpec(
        "SAMPLING.N_POINTS", "4.4.2", REQUIRED_DYNAMIC, "SamplingPlan", True, FINAL_BLOCK,
        "Утвердите SamplingPlan", "decisions",
    ),
    "OBSERVATION.DURATION": PlaceholderSpec(
        "OBSERVATION.DURATION", "4.x", REQUIRED_DYNAMIC, "observation.selected_duration", True, FINAL_BLOCK,
        "Задайте длительность наблюдения из verified planning evidence", "gaps",
    ),
    "SAMPLE_PROCESSING.DEFINITION": PlaceholderSpec(
        "SAMPLE_PROCESSING.DEFINITION", "7.x", REQUIRED_DYNAMIC, "bioanalysis / sample processing", False, FINAL_BLOCK,
        "Введите процедуру обработки проб", "gaps",
    ),
    # --- Bioanalysis ---
    "BIOANALYSIS.METHOD": PlaceholderSpec(
        "BIOANALYSIS.METHOD", "7.x", REQUIRED_DYNAMIC, "bioanalysis_plan.method", True, FINAL_BLOCK,
        "Заполните метод биоанализа", "gaps",
    ),
    "BIOANALYSIS.VALIDATION": PlaceholderSpec(
        "BIOANALYSIS.VALIDATION", "7.x", REQUIRED_DYNAMIC, "bioanalysis_plan.validation", True, FINAL_BLOCK,
        "Заполните валидацию метода", "gaps",
    ),
    "BIOANALYSIS.SAMPLE_ANALYSIS": PlaceholderSpec(
        "BIOANALYSIS.SAMPLE_ANALYSIS", "7.x", REQUIRED_DYNAMIC, "bioanalysis_plan.sample_analysis", True, FINAL_BLOCK,
        "Заполните анализ образцов", "gaps",
    ),
    "BIOANALYSIS.RUN_ACCEPTANCE": PlaceholderSpec(
        "BIOANALYSIS.RUN_ACCEPTANCE", "7.x", REQUIRED_DYNAMIC, "bioanalysis_plan.run_acceptance", True, FINAL_BLOCK,
        "Заполните критерии приемлемости прогона", "gaps",
    ),
    # --- Eligibility ---
    "ELIGIBILITY.INCLUSION": PlaceholderSpec(
        "ELIGIBILITY.INCLUSION", "6.1", REQUIRED_DYNAMIC, "eligibility.inclusion", True, FINAL_BLOCK,
        "Задайте критерии включения", "gaps",
    ),
    "ELIGIBILITY.NON_INCLUSION": PlaceholderSpec(
        "ELIGIBILITY.NON_INCLUSION", "6.2", REQUIRED_DYNAMIC, "eligibility.non_inclusion", True, FINAL_BLOCK,
        "Задайте критерии невключения", "gaps",
    ),
    "ELIGIBILITY.EXCLUSION": PlaceholderSpec(
        "ELIGIBILITY.EXCLUSION", "6.3", REQUIRED_DYNAMIC, "eligibility.exclusion", True, FINAL_BLOCK,
        "Задайте критерии исключения", "gaps",
    ),
    # --- Safety ---
    "SAFETY.PLAN": PlaceholderSpec(
        "SAFETY.PLAN", "8.x", REQUIRED_DYNAMIC, "safety_plan", True, FINAL_BLOCK,
        "Заполните план безопасности (не product-specific invent)", "gaps",
    ),
    "SAFETY.METHODS": PlaceholderSpec(
        "SAFETY.METHODS", "8.x", REQUIRED_DYNAMIC, "safety_plan.methods", True, FINAL_BLOCK,
        "Заполните методы оценки безопасности", "gaps",
    ),
    "SAFETY.LABS": PlaceholderSpec(
        "SAFETY.LABS", "8.x", REQUIRED_DYNAMIC, "safety_plan.labs", True, FINAL_BLOCK,
        "Заполните лабораторный мониторинг", "gaps",
    ),
    "SAFETY.AE": PlaceholderSpec(
        "SAFETY.AE", "8.x", REQUIRED_DYNAMIC, "safety_plan.ae", True, FINAL_BLOCK,
        "Заполните учёт НЯ", "gaps",
    ),
    "SAFETY.FOLLOW_UP": PlaceholderSpec(
        "SAFETY.FOLLOW_UP", "8.x", REQUIRED_DYNAMIC, "safety_plan.follow_up", True, FINAL_BLOCK,
        "Заполните follow-up безопасности", "gaps",
    ),
    "SAFETY.PHYS_EXAM": PlaceholderSpec(
        "SAFETY.PHYS_EXAM", "8.x", REQUIRED_DYNAMIC, "safety_plan.phys_exam", True, FINAL_BLOCK,
        "Заполните физикальный осмотр", "gaps",
    ),
    "SAFETY.PREGNANCY": PlaceholderSpec(
        "SAFETY.PREGNANCY", "8.x", REQUIRED_DYNAMIC, "safety_plan.pregnancy", True, FINAL_BLOCK,
        "Заполните мониторинг беременности", "gaps",
    ),
    "SAFETY.VITALS": PlaceholderSpec(
        "SAFETY.VITALS", "8.x", REQUIRED_DYNAMIC, "safety_plan.vitals", True, FINAL_BLOCK,
        "Заполните мониторинг витальных показателей", "gaps",
    ),
    # --- Evidence / product ---
    "EVIDENCE.PHARMACOLOGY": PlaceholderSpec(
        "EVIDENCE.PHARMACOLOGY", "2.8", REQUIRED_DYNAMIC, "verified pharmacology claims", True, FINAL_BLOCK,
        "Верифицируйте pharmacology evidence", "gaps",
    ),
    "EVIDENCE.CLINICAL_SUMMARY": PlaceholderSpec(
        "EVIDENCE.CLINICAL_SUMMARY", "2.x", REQUIRED_DYNAMIC, "verified clinical evidence", True, FINAL_BLOCK,
        "Верифицируйте клиническое резюме", "gaps",
    ),
    "EVIDENCE.LITERATURE_BASIS": PlaceholderSpec(
        "EVIDENCE.LITERATURE_BASIS", "2.x", REQUIRED_DYNAMIC, "verified literature", True, FINAL_BLOCK,
        "Верифицируйте литературную базу", "gaps",
    ),
    "EVIDENCE.RISK_BENEFIT": PlaceholderSpec(
        "EVIDENCE.RISK_BENEFIT", "2.x", REQUIRED_DYNAMIC, "verified risk/benefit", True, FINAL_BLOCK,
        "Верифицируйте соотношение риск/польза", "gaps",
    ),
    "PRODUCT.STORAGE": PlaceholderSpec(
        "PRODUCT.STORAGE", "2.1.1", REQUIRED_DYNAMIC, "product.storage_conditions", True, FINAL_BLOCK,
        "Задайте условия хранения исследуемого препарата", "gaps",
    ),
    "REFERENCE_PRODUCT.MANUFACTURER": PlaceholderSpec(
        "REFERENCE_PRODUCT.MANUFACTURER", "2.1.2", REQUIRED_DYNAMIC, "reference_product.manufacturer", True, FINAL_BLOCK,
        "Задайте производителя препарата сравнения", "gaps",
    ),
    "STATISTICS.ALPHA": PlaceholderSpec(
        "STATISTICS.ALPHA", "9.7", REQUIRED_DYNAMIC, "APPROVED StatisticsPlan.alpha", True, FINAL_BLOCK,
        "Утвердите статистический план (alpha)", "decisions",
    ),
    "CONTRACEPTION.PERIOD": PlaceholderSpec(
        "CONTRACEPTION.PERIOD", "6.x", REQUIRED_DYNAMIC, "eligibility / contraception rules", False, FINAL_BLOCK,
        "Задайте период контрацепции", "gaps",
    ),
    "CRF.PRIMARY_DATA_LIST": PlaceholderSpec(
        "CRF.PRIMARY_DATA_LIST", "9.x", REQUIRED_DYNAMIC, "data management / CRF", False, FINAL_BLOCK,
        "Задайте перечень первичных данных CRF", "gaps",
    ),
    "DATA.RETENTION_YEARS": PlaceholderSpec(
        "DATA.RETENTION_YEARS", "9.x", REQUIRED_DYNAMIC, "data retention policy", False, FINAL_BLOCK,
        "Задайте срок хранения данных", "gaps",
    ),
    "ETHICS.COMMITTEE": PlaceholderSpec(
        "ETHICS.COMMITTEE", "10.x", REQUIRED_DYNAMIC, "ethics.committee", False, FINAL_BLOCK,
        "Укажите этический комитет", "gaps",
    ),
    # --- Org / signatures: required for FINAL identity ---
    "ANALYTICAL_LAB.DETAILS": PlaceholderSpec(
        "ANALYTICAL_LAB.DETAILS", "1.x", REQUIRED_DYNAMIC, "organizations analytical lab", True, FINAL_BLOCK,
        "Укажите аналитическую лабораторию", "gaps",
    ),
    "INVESTIGATORS.DETAILS": PlaceholderSpec(
        "INVESTIGATORS.DETAILS", "1.x", REQUIRED_DYNAMIC, "persons investigators", True, FINAL_BLOCK,
        "Укажите исследователей", "gaps",
    ),
    "INVESTIGATOR_AGREEMENT.DETAILS": PlaceholderSpec(
        "INVESTIGATOR_AGREEMENT.DETAILS", "1.x", REQUIRED_DYNAMIC, "investigator agreement", False, FINAL_BLOCK,
        "Укажите соглашение исследователя", "gaps",
    ),
    "KEY_ORGS.DETAILS": PlaceholderSpec(
        "KEY_ORGS.DETAILS", "1.x", REQUIRED_DYNAMIC, "organizations", True, FINAL_BLOCK,
        "Укажите ключевые организации", "gaps",
    ),
    "MEDICAL_EXPERT.DETAILS": PlaceholderSpec(
        "MEDICAL_EXPERT.DETAILS", "1.x", REQUIRED_DYNAMIC, "persons medical expert", True, FINAL_BLOCK,
        "Укажите медицинского эксперта", "gaps",
    ),
    "SPONSOR_PERSONS.DETAILS": PlaceholderSpec(
        "SPONSOR_PERSONS.DETAILS", "1.x", REQUIRED_DYNAMIC, "sponsor persons", True, FINAL_BLOCK,
        "Укажите ответственных лиц спонсора", "gaps",
    ),
    "SIGNATURE.INVESTIGATOR": PlaceholderSpec(
        "SIGNATURE.INVESTIGATOR", "1.8", REQUIRED_DYNAMIC, "signatures", True, FINAL_BLOCK,
        "Заполните блок подписи исследователя", "protocol",
    ),
    "SIGNATURE.SPONSOR": PlaceholderSpec(
        "SIGNATURE.SPONSOR", "1.8", REQUIRED_DYNAMIC, "signatures", True, FINAL_BLOCK,
        "Заполните блок подписи спонсора", "protocol",
    ),
    # --- Optional non-medical (explicit FINAL allow) ---
    "PUBLICATION.POLICY": PlaceholderSpec(
        "PUBLICATION.POLICY", "12.x", OPTIONAL_DYNAMIC, "publication policy / STATIC_UNIVERSAL", True, FINAL_ALLOW,
        "Опционально: политика публикаций", "protocol",
    ),
    "SOURCES.LIST": PlaceholderSpec(
        "SOURCES.LIST", "References", OPTIONAL_DYNAMIC, "sources list", True, FINAL_ALLOW,
        "Опционально: список источников", "protocol",
    ),
    "FINANCING.DETAILS": PlaceholderSpec(
        "FINANCING.DETAILS", "11.x", OPTIONAL_DYNAMIC, "financing", False, FINAL_ALLOW,
        "Опционально: финансирование", "gaps",
    ),
    "INSURANCE.DETAILS": PlaceholderSpec(
        "INSURANCE.DETAILS", "11.x", OPTIONAL_DYNAMIC, "insurance", False, FINAL_ALLOW,
        "Опционально: страхование", "gaps",
    ),
    # --- Core identity (always required) ---
    "STUDY.PROTOCOL_NUMBER": PlaceholderSpec(
        "STUDY.PROTOCOL_NUMBER", "Cover", REQUIRED_DYNAMIC, "study.protocol_number", True, FINAL_BLOCK,
        "Задайте номер протокола", "overview",
    ),
    "STUDY.TITLE": PlaceholderSpec(
        "STUDY.TITLE", "Cover", REQUIRED_DYNAMIC, "study.title", True, FINAL_BLOCK,
        "Задайте название исследования", "overview",
    ),
    "TEST_PRODUCT.TRADE_NAME": PlaceholderSpec(
        "TEST_PRODUCT.TRADE_NAME", "2.1.1", REQUIRED_DYNAMIC, "product.trade_name", True, FINAL_BLOCK,
        "Задайте торговое название Т", "gaps",
    ),
    "TEST_PRODUCT.INN": PlaceholderSpec(
        "TEST_PRODUCT.INN", "2.1.1", REQUIRED_DYNAMIC, "product.inn", True, FINAL_BLOCK,
        "Задайте МНН Т", "gaps",
    ),
    "TEST_PRODUCT.DOSAGE": PlaceholderSpec(
        "TEST_PRODUCT.DOSAGE", "2.1.1", REQUIRED_DYNAMIC, "product.dosage", True, FINAL_BLOCK,
        "Задайте дозу Т", "gaps",
    ),
    "TEST_PRODUCT.DOSAGE_FORM": PlaceholderSpec(
        "TEST_PRODUCT.DOSAGE_FORM", "2.1.1", REQUIRED_DYNAMIC, "product.dosage_form", True, FINAL_BLOCK,
        "Задайте лекарственную форму Т", "gaps",
    ),
    "REFERENCE_PRODUCT.TRADE_NAME": PlaceholderSpec(
        "REFERENCE_PRODUCT.TRADE_NAME", "2.1.2", REQUIRED_DYNAMIC, "reference_product.trade_name", True, FINAL_BLOCK,
        "Задайте торговое название R", "gaps",
    ),
    "REFERENCE_PRODUCT.INN": PlaceholderSpec(
        "REFERENCE_PRODUCT.INN", "2.1.2", REQUIRED_DYNAMIC, "reference_product.inn", True, FINAL_BLOCK,
        "Задайте МНН R", "gaps",
    ),
    "SUBJECTS.EVALUABLE_N": PlaceholderSpec(
        "SUBJECTS.EVALUABLE_N", "Synopsis", REQUIRED_DYNAMIC, "CanonicalSubjectCounts", True, FINAL_BLOCK,
        "Задайте число оцениваемых субъектов", "decisions",
    ),
    "SUBJECTS.RANDOMIZED_N": PlaceholderSpec(
        "SUBJECTS.RANDOMIZED_N", "Synopsis", REQUIRED_DYNAMIC, "CanonicalSubjectCounts", True, FINAL_BLOCK,
        "Задайте число рандомизированных субъектов", "decisions",
    ),
    "DESIGN.TYPE": PlaceholderSpec(
        "DESIGN.TYPE", "4.x", REQUIRED_DYNAMIC, "design.type", True, FINAL_BLOCK,
        "Задайте дизайн исследования", "decisions",
    ),
    "FOOD.CONDITION": PlaceholderSpec(
        "FOOD.CONDITION", "4.x", REQUIRED_DYNAMIC, "food.condition", True, FINAL_BLOCK,
        "Задайте условие пищи", "decisions",
    ),
    "UNRESOLVED": PlaceholderSpec(
        "UNRESOLVED", "any", REQUIRED_DYNAMIC, "assembly fallback", False, FINAL_BLOCK,
        "Устраните {{UNRESOLVED}} — источник не найден", "gaps",
    ),
}

# Back-compat aliases used by older gates
CRITICAL_CODES: frozenset[str] = frozenset(
    code for code, spec in PLACEHOLDER_CATALOG.items() if spec.final_policy == FINAL_BLOCK
)

DRAFT_ALLOWED_PREFIXES: tuple[str, ...] = (
    "SPONSOR",
    "SPONSOR_PERSONS",
    "MEDICAL_EXPERT",
    "INVESTIGATORS",
    "ANALYTICAL_LAB",
    "KEY_ORGS",
    "INVESTIGATOR_AGREEMENT",
    "SIGNATURE",
    "FINANCING",
    "INSURANCE",
    "PUBLICATION",
    "CLINICAL_CENTERS",
    "STATISTICS.DROPOUT_PCT",
    "SOURCES",
    "BIOANALYSIS",
    "ELIGIBILITY",
    "SAFETY",
    "EVIDENCE",
    "SAMPLING",
    "OBSERVATION",
    "ETHICS",
    "CRF",
    "DATA",
    "CONTRACEPTION",
    "SAMPLE_PROCESSING",
    "PRODUCT",
    "REFERENCE_PRODUCT",
    "STATISTICS",
)

LEGACY_TOKENS: frozenset[str] = frozenset({"XXX", "ХХ", "TBD", "N/A"})

TOC_VISUAL_VALIDATION = "NOT_EXECUTED"


@dataclass(frozen=True)
class ClassifiedPlaceholder:
    marker: str
    code: str
    classification: str
    blocks_review: bool
    blocks_final: bool
    section: str = ""
    source: str = ""
    resolve_hint: str = ""
    tab: str = "gaps"
    final_policy: str = FINAL_BLOCK
    mapped: bool = False


def _normalize_marker(marker: str) -> tuple[str, str]:
    raw = marker.strip()
    m = PLACEHOLDER_RE.fullmatch(raw) or PLACEHOLDER_RE.search(raw)
    code = m.group(1) if m else raw.replace("{{", "").replace("}}", "").strip()
    return (raw if raw.startswith("{{") else f"{{{{{code}}}}}"), code


def classify_placeholder(marker: str) -> ClassifiedPlaceholder:
    marker_full, code = _normalize_marker(marker)
    if code in LEGACY_TOKENS or "XXX" in code:
        return ClassifiedPlaceholder(
            marker_full, code, LEGACY_TEMPLATE, True, True,
            section="any", source="legacy", resolve_hint="Удалите legacy token",
            final_policy=FINAL_BLOCK,
        )
    spec = PLACEHOLDER_CATALOG.get(code)
    if spec is None:
        return ClassifiedPlaceholder(
            marker_full, code, UNKNOWN, True, True,
            section="unknown", source="unregistered",
            resolve_hint="Зарегистрируйте или устраните неизвестный плейсхолдер",
            tab="protocol", final_policy=FINAL_BLOCK, mapped=False,
        )
    blocks_final = spec.final_policy == FINAL_BLOCK or spec.classification in {
        REQUIRED_DYNAMIC, STATIC_TEMPLATE, UNKNOWN,
    }
    if spec.classification == OPTIONAL_DYNAMIC and spec.final_policy == FINAL_ALLOW:
        blocks_final = False
    return ClassifiedPlaceholder(
        marker_full,
        code,
        spec.classification,
        blocks_review=True,
        blocks_final=blocks_final,
        section=spec.section,
        source=spec.source,
        resolve_hint=spec.resolve_hint,
        tab=spec.tab,
        final_policy=spec.final_policy,
        mapped=spec.mapped,
    )


def classify_placeholders(markers: Iterable[str]) -> list[ClassifiedPlaceholder]:
    return [classify_placeholder(m) for m in sorted(set(markers))]


def extract_placeholders(obj: Any) -> list[str]:
    found: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, str):
            found.extend(f"{{{{{m.group(1)}}}}}" for m in PLACEHOLDER_RE.finditer(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)
    return sorted(set(found))


def review_blocking_placeholders(markers: Iterable[str]) -> list[ClassifiedPlaceholder]:
    return [c for c in classify_placeholders(markers) if c.blocks_review]


def final_blocking_placeholders(markers: Iterable[str]) -> list[ClassifiedPlaceholder]:
    return [c for c in classify_placeholders(markers) if c.blocks_final]


def assess_placeholders_for_mode(markers: Iterable[str], *, mode: str = "DRAFT") -> dict[str, Any]:
    """Deterministic placeholder gate for DRAFT vs FINAL."""
    mode_u = str(mode or "DRAFT").upper()
    classified = classify_placeholders(markers)
    required = [c for c in classified if c.classification == REQUIRED_DYNAMIC]
    optional = [c for c in classified if c.classification == OPTIONAL_DYNAMIC]
    unknown = [c for c in classified if c.classification == UNKNOWN]
    static = [c for c in classified if c.classification == STATIC_TEMPLATE]
    blocking = [c for c in classified if c.blocks_final]

    def _row(c: ClassifiedPlaceholder) -> dict[str, Any]:
        return {
            "placeholder": c.marker,
            "code": c.code,
            "section": c.section,
            "classification": c.classification,
            "source": c.source,
            "mapped": c.mapped,
            "final_policy": c.final_policy,
            "reason": c.resolve_hint,
            "field": c.code,
            "tab": c.tab,
            "how_to_resolve": c.resolve_hint,
        }

    if mode_u == "FINAL":
        ok = len(blocking) == 0
        return {
            "ok": ok,
            "mode": mode_u,
            "code": "UNRESOLVED_TEMPLATE_PLACEHOLDER" if not ok else "PLACEHOLDERS_OK",
            "blocking": [_row(c) for c in blocking],
            "required_count": len(required),
            "unknown_count": len(unknown),
            "optional_allowed": [_row(c) for c in optional if not c.blocks_final],
            "static_count": len(static),
            "toc_visual_validation": TOC_VISUAL_VALIDATION,
            "message": (
                "FINAL placeholders clean"
                if ok
                else f"FINAL blocked: {len(blocking)} required/unknown unresolved placeholders"
            ),
        }

    # DRAFT: allow explicit {{...}} markers; never invent medical prose
    return {
        "ok": True,
        "mode": mode_u,
        "code": "DRAFT_PLACEHOLDERS_ALLOWED",
        "placeholders": [_row(c) for c in classified],
        "required_count": len(required),
        "unknown_count": len(unknown),
        "blocking_for_final": [_row(c) for c in blocking],
        "toc_visual_validation": TOC_VISUAL_VALIDATION,
        "message": (
            f"DRAFT may keep {len(classified)} explicit {{{{…}}}} markers; "
            f"{len(blocking)} would block FINAL"
        ),
    }


def registry_as_list() -> list[dict[str, Any]]:
    return [
        {
            "placeholder": f"{{{{{s.code}}}}}",
            "code": s.code,
            "section": s.section,
            "classification": s.classification,
            "source": s.source,
            "mapped": s.mapped,
            "final_policy": s.final_policy,
            "resolve_hint": s.resolve_hint,
            "tab": s.tab,
        }
        for s in sorted(PLACEHOLDER_CATALOG.values(), key=lambda x: x.code)
    ]
