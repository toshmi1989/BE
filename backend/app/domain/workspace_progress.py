"""Phase 27 — Writer workflow progress derived from authoritative backend state."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.decision_store import list_decisions
from app.domain.sample_size_store import list_calculations
from app.domain.statistics_store import latest_plan as latest_stats_plan
from app.domain.study_workspace import (
    aggregate_conflicts,
    build_preflight,
    build_workspace_summary,
    list_protocol_drafts,
)
from app.domain.workspace_documents import list_study_documents
from app.domain.workspace_protocol import list_artifacts
from app.domain.workspace_snapshots import list_snapshots, latest_snapshot

STEP_IDS = (
    "documents",
    "extraction",
    "decisions",
    "sample_size",
    "statistics",
    "protocol",
    "preflight",
    "docx",
)

STEP_LABELS_RU = {
    "documents": "Документы",
    "extraction": "Извлечение и проверка данных",
    "decisions": "Решения",
    "sample_size": "Sample Size",
    "statistics": "Statistics",
    "protocol": "Протокол",
    "preflight": "Финальная проверка",
    "docx": "DOCX",
}

TAB_FOR_STEP = {
    "documents": "documents",
    "extraction": "data",
    "decisions": "decisions",
    "sample_size": "sample-size",
    "statistics": "statistics",
    "protocol": "protocol",
    "preflight": "preflight",
    "docx": "protocol",
}


def _ss_approved(calc: Any | None) -> bool:
    if calc is None:
        return False
    return str(getattr(calc, "status", "") or "").upper() in {"ACCEPTED", "APPROVED"}


def _st_approved(plan: Any | None) -> bool:
    if plan is None:
        return False
    return str(getattr(plan, "status", "") or "").upper() == "APPROVED"


def _actionable_blockers(
    *,
    study_id: str,
    conflicts: list[dict[str, Any]],
    preflight: dict[str, Any],
    ss: Any | None,
    st: Any | None,
    docs: list[dict[str, Any]],
    facts_count: int,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    if not docs:
        blockers.append(
            {
                "severity": "CRITICAL",
                "code": "NO_DOCUMENTS",
                "what": "Нет исходных документов",
                "why": "Для анализа пакета нужны Checklist, Synopsis/Design и SmPC.",
                "where": "Документы",
                "action_label": "Загрузить документы",
                "tab": "documents",
            }
        )

    for c in conflicts:
        if str(c.get("status") or "").upper() != "OPEN":
            continue
        if str(c.get("severity") or "").upper() != "CRITICAL":
            continue
        field = str(c.get("field") or "field")
        va, vb = c.get("value_a"), c.get("value_b")
        sa, sb = c.get("source_a"), c.get("source_b")
        blockers.append(
            {
                "severity": "CRITICAL",
                "code": "UNRESOLVED_CRITICAL_CONFLICT",
                "what": f"Конфликт: {field}",
                "why": f"{sa or 'Источник A'} и {sb or 'Источник B'} содержат разные значения"
                + (f" ({va} vs {vb})." if va is not None or vb is not None else "."),
                "where": "Решения",
                "action_label": "Разобрать конфликт",
                "tab": "decisions",
                "field": field,
                "detail": c,
            }
        )

    if docs and facts_count == 0:
        blockers.append(
            {
                "severity": "WARNING",
                "code": "NOT_ANALYZED",
                "what": "Пакет не проанализирован",
                "why": "Документы загружены, но извлечение и нормализация ещё не выполнены.",
                "where": "Документы",
                "action_label": "Анализировать пакет",
                "tab": "documents",
            }
        )

    if ss is None or not _ss_approved(ss):
        reasons = []
        if ss is not None:
            reasons = list(getattr(ss, "blocking_reasons", None) or [])
        if not reasons and ss is None:
            reasons = ["MISSING_VERIFIED_CVINTRA"]
        if not _ss_approved(ss):
            blockers.append(
                {
                    "severity": "WARNING" if not any(b.get("code") == "UNRESOLVED_CRITICAL_CONFLICT" for b in blockers) else "INFO",
                    "code": "SAMPLE_SIZE_NOT_APPROVED",
                    "what": "Sample Size недоступен или не утверждён",
                    "why": "; ".join(str(r) for r in reasons) if reasons else f"Статус: {getattr(ss, 'status', 'NO_CALCULATION')}",
                    "where": "Sample Size",
                    "action_label": "Открыть Sample Size",
                    "tab": "sample-size",
                    "resolve_dependency": True,
                }
            )

    if st is None or not _st_approved(st):
        br = list(getattr(st, "blocking_reasons", None) or []) if st else ["PRIMARY_BE_REQUIRES_EXPERT_SELECTION"]
        primary = any("PRIMARY" in str(x).upper() or "REQUIRES_EXPERT" in str(x).upper() for x in br) or st is None
        blockers.append(
            {
                "severity": "CRITICAL" if primary else "WARNING",
                "code": "PRIMARY_BE_NOT_APPROVED" if primary else "STATISTICS_NOT_APPROVED",
                "what": "Выберите основной endpoint анализа биоэквивалентности."
                if primary
                else "Statistics plan не утверждён",
                "why": "; ".join(str(x) for x in br) if br else "Нет утверждённого статистического плана",
                "where": "Statistics" if not primary else "Решения / Statistics",
                "action_label": "Открыть Statistics" if not primary else "Открыть Решения",
                "tab": "statistics" if not primary else "decisions",
            }
        )

    for chk in preflight.get("critical_blockers") or []:
        code = str(chk.get("code") or "")
        if any(b.get("code") == code for b in blockers):
            continue
        tab = "decisions"
        label = "Открыть Решения"
        if "SAMPLE" in code.upper() or "N_" in code.upper():
            tab, label = "sample-size", "Открыть Sample Size"
        elif "STAT" in code.upper() or "PRIMARY_BE" in code.upper():
            tab, label = "statistics", "Открыть Statistics"
        elif "EVIDENCE" in code.upper() or "RESEARCH" in code.upper():
            tab, label = "evidence", "Открыть Research"
        elif "DOC" in code.upper():
            tab, label = "documents", "Открыть Документы"
        blockers.append(
            {
                "severity": str(chk.get("severity") or "CRITICAL"),
                "code": code or "PREFLIGHT_BLOCKER",
                "what": str(chk.get("message") or code or "Блокер preflight"),
                "why": str(chk.get("detail") or chk.get("message") or "Правило безопасности / готовности"),
                "where": label.replace("Открыть ", ""),
                "action_label": label,
                "tab": tab,
            }
        )

    return blockers


def _next_action(steps: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> dict[str, Any]:
    # Prefer critical blocker action
    for b in blockers:
        if str(b.get("severity")).upper() == "CRITICAL":
            return {
                "label": b.get("action_label") or "Устранить блокер",
                "label_ru": _map_primary_ru(b),
                "tab": b.get("tab") or "overview",
                "severity": "critical",
                "code": b.get("code"),
            }

    order = [
        ("documents", "Загрузите документы", "documents"),
        ("extraction", "Проверьте извлечённые данные", "data"),
        ("decisions", "Примите экспертные решения", "decisions"),
        ("sample_size", "Проверьте Sample Size", "sample-size"),
        ("statistics", "Утвердите Statistics", "statistics"),
        ("protocol", "Откройте Preview", "protocol"),
        ("preflight", "Запустите финальную проверку", "preflight"),
        ("docx", "Сгенерируйте DOCX", "protocol"),
    ]
    for sid, label, tab in order:
        step = next((s for s in steps if s["id"] == sid), None)
        if not step:
            continue
        st = step["status"]
        if st in {"NOT_STARTED", "IN_PROGRESS", "BLOCKED", "READY"}:
            if sid == "decisions" and st == "BLOCKED":
                label = "Разрешите критический конфликт"
            if sid == "documents" and st == "READY":
                continue
            if sid == "documents" and st == "IN_PROGRESS":
                label = "Загрузите документы"
            if sid == "extraction" and st == "READY":
                label = "Проверьте извлечённые данные"
            return {"label": label, "label_ru": label, "tab": tab, "severity": "warn" if st == "BLOCKED" else "info", "step": sid}

    return {
        "label": "Сгенерируйте DOCX",
        "label_ru": "Сгенерируйте DOCX",
        "tab": "protocol",
        "severity": "info",
        "step": "docx",
    }


def _map_primary_ru(b: dict[str, Any]) -> str:
    code = str(b.get("code") or "")
    if code == "NO_DOCUMENTS":
        return "Загрузите документы"
    if code == "UNRESOLVED_CRITICAL_CONFLICT":
        return "Разрешите критический конфликт"
    if code == "NOT_ANALYZED":
        return "Анализируйте пакет исследования"
    if "SAMPLE" in code:
        return "Проверьте Sample Size"
    if "PRIMARY_BE" in code or "STAT" in code:
        return "Утвердите Statistics"
    return str(b.get("action_label") or "Продолжите работу")


def compute_writer_progress(
    db: Session,
    study_id: str,
    *,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Derive 8-step progress + single next action from backend state only."""
    docs = list_study_documents(db, study_id)
    summary = build_workspace_summary(study_id, package_id=package_id)
    facts = summary.get("canonical_facts") or []
    cards = summary.get("summary_cards") or {}
    conflicts = aggregate_conflicts(study_id, package_id=package_id)
    open_critical = [c for c in conflicts if c.get("status") == "OPEN" and c.get("severity") == "CRITICAL"]
    decisions = list_decisions(study_id)
    pending_decisions = [
        d
        for d in decisions
        if str(getattr(d, "status", "") or "").upper()
        not in {"APPROVED", "REJECTED", "KEEP_CURRENT", "ACCEPTED", "RESOLVED"}
    ]
    calcs = list_calculations(study_id)
    latest_ss = calcs[-1] if calcs else None
    st = latest_stats_plan(study_id)
    drafts = list_protocol_drafts(study_id)
    pf = build_preflight(study_id, package_id=package_id)
    artifacts = list_artifacts(db, study_id)
    snaps = list_snapshots(db, study_id)
    snap = latest_snapshot(db, study_id)

    required_types = {"CHECKLIST", "SYNOPSIS", "SMPC"}
    present_types = {str(d.get("document_type") or d.get("type") or "").upper() for d in docs}
    if "DESIGN" in present_types or "SYNOPSIS_DESIGN" in present_types:
        present_types.add("SYNOPSIS")
    missing_required = sorted(required_types - present_types)

    # --- step statuses ---
    if not docs:
        doc_status = "NOT_STARTED"
    elif missing_required:
        doc_status = "IN_PROGRESS"
    else:
        doc_status = "COMPLETED"

    if not docs:
        ext_status = "NOT_STARTED"
    elif not facts:
        ext_status = "BLOCKED" if missing_required else "IN_PROGRESS"
    elif open_critical or any(str(f.get("status") or "").upper() in {"REVIEW_REQUIRED", "CONFLICT"} for f in facts):
        ext_status = "READY"  # facts exist; review pending
    else:
        ext_status = "COMPLETED"

    if open_critical:
        dec_status = "BLOCKED"
    elif pending_decisions:
        dec_status = "IN_PROGRESS"
    elif not facts:
        dec_status = "NOT_STARTED"
    elif decisions:
        dec_status = "COMPLETED"
    else:
        dec_status = "READY" if facts else "NOT_STARTED"

    if open_critical:
        ss_status = "BLOCKED"
    elif latest_ss is None:
        ss_status = "NOT_STARTED" if not facts else "BLOCKED"
    elif _ss_approved(latest_ss):
        ss_status = "COMPLETED"
    else:
        ss_status = "READY"

    if open_critical or (st and any("PRIMARY" in str(x).upper() for x in (st.blocking_reasons or []))):
        st_status = "BLOCKED" if (st is None or not _st_approved(st)) else "COMPLETED"
    elif st is None:
        st_status = "NOT_STARTED" if not facts else "BLOCKED"
    elif _st_approved(st):
        st_status = "COMPLETED"
    else:
        st_status = "READY"

    if not drafts:
        proto_status = "NOT_STARTED" if not facts else "READY"
    else:
        proto_status = "COMPLETED" if drafts else "IN_PROGRESS"

    if not drafts and not facts:
        pf_status = "NOT_STARTED"
    elif pf.get("can_finalize") or pf.get("can_generate_docx"):
        pf_status = "COMPLETED" if pf.get("can_generate_docx") else "READY"
    elif pf.get("critical_blockers"):
        pf_status = "BLOCKED"
    else:
        pf_status = "IN_PROGRESS"

    if artifacts:
        docx_status = "COMPLETED"
    elif pf.get("can_generate_docx"):
        docx_status = "READY"
    elif open_critical or pf.get("critical_blockers"):
        docx_status = "BLOCKED"
    elif drafts:
        docx_status = "IN_PROGRESS"
    else:
        docx_status = "NOT_STARTED"

    steps = []
    for sid in STEP_IDS:
        status = {
            "documents": doc_status,
            "extraction": ext_status,
            "decisions": dec_status,
            "sample_size": ss_status,
            "statistics": st_status,
            "protocol": proto_status,
            "preflight": pf_status,
            "docx": docx_status,
        }[sid]
        steps.append(
            {
                "id": sid,
                "label": STEP_LABELS_RU[sid],
                "status": status,
                "tab": TAB_FOR_STEP[sid],
            }
        )

    blockers = _actionable_blockers(
        study_id=study_id,
        conflicts=conflicts,
        preflight=pf,
        ss=latest_ss,
        st=st,
        docs=docs,
        facts_count=len(facts),
    )
    primary = _next_action(steps, blockers)
    secondary = [
        {"label": b["what"], "tab": b["tab"], "severity": b["severity"]}
        for b in blockers
        if b.get("action_label") != primary.get("label") and b.get("code") != primary.get("code")
    ][:5]

    package_checklist = [
        {
            "type": "CHECKLIST",
            "label": "Checklist",
            "state": "PRESENT" if "CHECKLIST" in present_types else "MISSING",
            "required": True,
        },
        {
            "type": "SYNOPSIS",
            "label": "Synopsis/Design",
            "state": "PRESENT" if "SYNOPSIS" in present_types else "MISSING",
            "required": True,
        },
        {
            "type": "SMPC",
            "label": "SmPC",
            "state": "PRESENT" if "SMPC" in present_types else "MISSING",
            "required": True,
        },
        {
            "type": "OTHER",
            "label": "Other",
            "state": "PRESENT" if "OTHER" in present_types else "OPTIONAL",
            "required": False,
        },
    ]

    return {
        "study_id": study_id,
        "steps": steps,
        "primary_next_action": primary,
        "secondary_issues": secondary,
        "blockers": blockers,
        "package_checklist": package_checklist,
        "counts": {
            "documents": len(docs),
            "facts": len(facts),
            "conflicts_open": len([c for c in conflicts if c.get("status") == "OPEN"]),
            "conflicts_critical": len(open_critical),
            "pending_decisions": len(pending_decisions),
            "protocol_drafts": len(drafts),
            "snapshots": len(snaps),
            "docx_artifacts": len(artifacts),
        },
        "versions": {
            "protocol_draft": (drafts[-1].get("version") if drafts else None),
            "snapshot": (snap or {}).get("version"),
            "sample_size": getattr(latest_ss, "id", None) if latest_ss else None,
            "sample_size_status": getattr(latest_ss, "status", None) if latest_ss else None,
            "statistics": getattr(st, "id", None) if st else None,
            "statistics_status": getattr(st, "status", None) if st else None,
            "statistics_version": getattr(st, "version", None) if st else None,
        },
        "preflight": {
            "can_finalize": pf.get("can_finalize"),
            "can_generate_docx": pf.get("can_generate_docx"),
            "message": pf.get("message"),
        },
        "summary_cards": cards,
        "derived_from_backend": True,
        "ui_clicks_do_not_complete_steps": True,
    }


def build_field_detail(
    study_id: str,
    field: str,
    *,
    package_id: str | None = None,
) -> dict[str, Any]:
    """Field inspection payload for writer drawer — no silent mutation."""
    summary = build_workspace_summary(study_id, package_id=package_id)
    facts = summary.get("canonical_facts") or []
    fact = next((f for f in facts if str(f.get("field")) == field), None)
    conflicts = [c for c in aggregate_conflicts(study_id, package_id=package_id) if c.get("field") == field]
    decisions = [d.to_dict(for_ui=True) if hasattr(d, "to_dict") else d for d in list_decisions(study_id)]
    related = [
        d
        for d in decisions
        if field in str(getattr(d, "question", "") or "")
        or field in str((d if isinstance(d, dict) else {}).get("domain", ""))
        or field in str((d if isinstance(d, dict) else {}).get("question", ""))
    ]
    # Prefer dict form
    related_ui = []
    for d in list_decisions(study_id):
        dd = d.to_dict(for_ui=True) if hasattr(d, "to_dict") else {}
        blob = f"{dd.get('domain','')}{dd.get('question','')}{dd.get('id','')}"
        if field.split(".")[-1].lower() in blob.lower() or field.lower() in blob.lower():
            related_ui.append(dd)

    affected = []
    if fact and fact.get("affected_sections"):
        affected = list(fact.get("affected_sections") or [])
    else:
        # Heuristic section mapping without inventing medical content
        if "dose" in field:
            affected = ["7. Dosing", "6. Test/Reference Products"]
        elif "design" in field:
            affected = ["4. Study Design"]
        elif "subject" in field or field.endswith(".n"):
            affected = ["5. Subjects"]
        elif "food" in field:
            affected = ["8. Food"]
        elif "pk" in field or "auc" in field.lower() or "cmax" in field.lower():
            affected = ["10. PK", "11. Statistics"]
        else:
            affected = ["Protocol (related sections)"]

    return {
        "field": field,
        "current_value": None if not fact else fact.get("canonical_value"),
        "status": None if not fact else fact.get("status"),
        "source": {
            "document": None if not fact else fact.get("source"),
            "page_section": None if not fact else fact.get("page") or fact.get("section"),
            "excerpt": None if not fact else fact.get("excerpt") or fact.get("evidence"),
        },
        "evidence": {
            "claim": None if not fact else fact.get("evidence_id") or fact.get("evidence"),
            "confidence": None if not fact else fact.get("confidence"),
            "verification": None if not fact else fact.get("verification_status") or fact.get("status"),
        },
        "decision": {
            "current": related_ui[0] if related_ui else None,
            "status": (related_ui[0] or {}).get("status") if related_ui else None,
            "conflicts": conflicts,
        },
        "affected_protocol_sections": affected,
        "study_mutated": False,
    }


def dependency_impact_for_decision(question: str) -> list[str]:
    q = (question or "").lower()
    impact = []
    if any(k in q for k in ("dose", "design", "cv", "n ", "sample", "subject", "endpoint", "auc", "primary", "be")):
        if any(k in q for k in ("cv", "n ", "sample", "subject", "design", "dose")):
            impact.append("Sample Size")
        if any(k in q for k in ("endpoint", "auc", "primary", "be", "statistic", "pk")):
            impact.append("Statistics")
        impact.append("Protocol")
    if not impact:
        impact = ["Protocol"]
    # unique preserve order
    seen = set()
    out = []
    for x in impact:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
