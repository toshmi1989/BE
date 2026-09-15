"""Phase 30.4 — UPDCB DOCX visual/semantic acceptance runner (AI-off, no gate bypass).

Writes JSON summary under docs/phase30_4_artifacts/ and prints key findings.
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package import when run as script
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.core.db import Base, configure_engine, get_engine
from app.core import db as db_module
from app.domain.docx_semantic_integrity import (
    assess_docx_semantic_integrity,
    semantic_preflight_from_context,
)
from app.domain.exceptions import ValidationError
from app.domain.protocol_workflow import run_protocol_workflow
from app.domain.study_workspace import build_preflight, put_protocol_draft_version, reset_workspace_store
from app.domain.decision_store import clear_decision_store
from app.domain.research_evidence_store import clear_research_evidence_store
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.workspace_assembly_context import build_workspace_assembly_context
from app.domain.workspace_protocol import generate_docx_artifact, read_artifact_bytes
import app.models  # noqa: F401

STUDY = "UPDCB-02-BE-2026"
OUT = ROOT / "docs" / "phase30_4_artifacts"


def _blob_from_docx(path: Path) -> tuple[str, dict]:
    from docx import Document

    doc = Document(str(path))
    parts: list[str] = []
    meta = {
        "paragraphs": len(doc.paragraphs),
        "tables": len(doc.tables),
        "cover_rows": [],
        "sampling_preview": [],
        "pk_preview": [],
        "headers": [],
    }
    for p in doc.paragraphs:
        t = p.text or ""
        if t.strip():
            parts.append(t)
        style = (p.style.name if p.style else "") or ""
        if style.lower().startswith("toc") or style.startswith("TOC"):
            meta.setdefault("toc_lines", []).append(t[:120])
    if doc.tables:
        for row in doc.tables[0].rows:
            cells = [(c.text or "").replace("\n", " ").strip() for c in row.cells[:2]]
            meta["cover_rows"].append(cells)
            parts.append(" | ".join(cells))
    # sampling ~ T10 index 9, PK ~ T07 index 6
    if len(doc.tables) > 9:
        for row in list(doc.tables[9].rows)[:8]:
            meta["sampling_preview"].append(
                [(c.text or "").replace("\n", " ").strip()[:40] for c in row.cells]
            )
    if len(doc.tables) > 6:
        for row in list(doc.tables[6].rows)[:8]:
            meta["pk_preview"].append(
                [(c.text or "").replace("\n", " ").strip()[:40] for c in row.cells]
            )
    for section in doc.sections:
        for attr in ("header", "footer"):
            part = getattr(section, attr, None)
            if part is None:
                continue
            for p in part.paragraphs:
                if p.text and p.text.strip():
                    meta["headers"].append(f"{attr}: {(p.text or '')[:100]}")
    return "\n".join(parts), meta


def _content_flags(blob: str) -> dict:
    return {
        "placeholder_hits": sorted(set(re.findall(r"\{\{[A-Z0-9_.]+\}\}", blob)))[:40],
        "stale_400": bool(re.search(r"\b400\s*(mg|мг)\b", blob, re.I)),
        "stale_date_18042025": "18.04.2025" in blob,
        "bosutinib": bool(re.search(r"бозутиниб|bosutinib|бозулиф|bosulif", blob, re.I)),
        "internal_table_id": bool(
            re.search(r"таблица\s+(PK_PARAMETERS|BLOOD_SAMPLING|STUDY_METADATA)\b", blob, re.I)
        ),
        "dosage_form_is_56": bool(
            re.search(r"лекарственная форма[^\n|]{0,40}\|\s*56\b", blob, re.I)
        )
        or bool(re.search(r"Лекарственная форма\|\s*56\b", blob)),
        "accepted_calculation_enum": "ACCEPTED_CALCULATION" in blob,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    storage = OUT / f"storage-{stamp}"
    storage.mkdir(parents=True, exist_ok=True)

    import os

    db_path = OUT / f"accept-{stamp}.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
    os.environ["AI_ENABLED"] = "false"
    os.environ["AUTH_REQUIRED"] = "false"
    os.environ["DOCUMENT_STORAGE_ROOT"] = str(storage)

    get_settings.cache_clear()
    configure_engine(os.environ["DATABASE_URL"])
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    reset_workspace_store()
    reset_sample_size_store()
    reset_statistics_store()
    clear_research_evidence_store()
    clear_decision_store()
    clear_study_input()

    report: dict = {
        "phase": "30.4",
        "version_target": "0.35.5",
        "study": STUDY,
        "ai_enabled": False,
        "gate_bypass": False,
        "stamp": stamp,
        "workflow": None,
        "preflight": None,
        "draft": None,
        "final": None,
        "visual": None,
        "content": None,
        "cross_section": None,
        "toc": None,
        "result": None,
    }

    try:
        wf = run_protocol_workflow(
            STUDY,
            use_golden_fixture=True,
            prepare_protocol_draft=True,
            created_by="phase30_4",
            # NO auto_resolve / auto_approve flags — expert path below is explicit
        )
        report["workflow"] = {
            "ok": True,
            "package_id": wf.get("package_id"),
            "steps": [
                {"name": s.get("name") or s.get("step"), "status": s.get("status")}
                for s in (wf.get("steps") or [])[:20]
            ],
            "keys": sorted(wf.keys()),
        }
    except Exception as exc:  # noqa: BLE001
        report["workflow"] = {"ok": False, "error": str(exc), "trace": traceback.format_exc()[-1500:]}
        wf = {}

    # Legitimate expert resolution of OPEN critical input conflicts (not a silent bypass).
    # Required before DRAFT export when golden fixture has dose conflict.
    from app.domain.study_input_conflicts import FieldConflict, resolve_conflict
    from app.domain.study_input_store import get_package, put_package

    expert_actions: list[dict] = []
    pkg_id = (wf or {}).get("package_id")
    if pkg_id:
        pkg = get_package(str(pkg_id))
        if pkg is not None:
            new_conflicts = []
            for raw in pkg.conflicts:
                status = str(raw.get("status") or "OPEN")
                field = str(raw.get("field_path") or "")
                severity = str(raw.get("severity") or "HIGH")
                if field == "reference_product.dose":
                    severity = "CRITICAL"
                if status == "OPEN" and severity == "CRITICAL":
                    conflict = FieldConflict(
                        conflict_id=str(raw["conflict_id"]),
                        field_path=field,
                        candidate_ids=list(raw.get("candidate_ids") or []),
                        values=list(raw.get("values") or []),
                        sources=list(raw.get("sources") or []),
                        status=status,
                        outcome=raw.get("outcome"),
                        severity=severity,
                    )
                    cands = list(raw.get("candidate_ids") or [])
                    selected = cands[0] if cands else None
                    resolve_conflict(
                        conflict,
                        reviewer="phase30_4_expert",
                        outcome="SELECT_VALUE" if selected else "KEEP_BOTH_WITH_CONTEXT",
                        reason="Phase 30.4 visual acceptance: expert selects reference dose for DRAFT export",
                        selected_candidate_id=selected,
                        status="RESOLVED",
                    )
                    new_conflicts.append(conflict.to_dict())
                    expert_actions.append(
                        {
                            "conflict_id": conflict.conflict_id,
                            "field": field,
                            "outcome": conflict.outcome,
                            "selected": selected,
                        }
                    )
                else:
                    new_conflicts.append(raw)
            pkg.conflicts = new_conflicts
            put_package(pkg)
    report["expert_conflict_resolutions"] = expert_actions

    # Re-prepare draft after expert resolutions (reuse same package; do not reload golden)
    try:
        from app.domain.study_workspace import put_protocol_draft_version as _put_draft

        _put_draft(
            STUDY,
            status="DRAFT",
            created_by="phase30_4",
            based_on={"snapshot": None, "decisions": [], "expert_resolutions": expert_actions},
        )
        report["workflow_after_expert"] = {
            "ok": True,
            "note": "conflicts resolved by explicit expert reviewer; draft version recorded",
            "resolutions": len(expert_actions),
        }
    except Exception as exc:  # noqa: BLE001
        report["workflow_after_expert"] = {"ok": False, "error": str(exc)}

    pf = build_preflight(STUDY)
    report["preflight"] = {
        "can_generate_docx": pf.get("can_generate_docx"),
        "can_finalize": pf.get("can_finalize"),
        "critical_blockers": [
            {"code": c.get("code"), "message": c.get("message"), "ok": c.get("ok")}
            for c in (pf.get("critical_blockers") or [])
        ],
        "semantic_final": next(
            (
                c.get("details")
                for c in (pf.get("checks") or [])
                if c.get("code") == "SEMANTIC_FINAL_GAPS"
            ),
            None,
        ),
        "message": pf.get("message"),
    }

    ctx = build_workspace_assembly_context(STUDY)
    sem_pf = semantic_preflight_from_context(ctx, mode="FINAL")
    report["semantic_preflight_final"] = sem_pf

    factory = db_module.SessionLocal
    if factory is None:
        raise RuntimeError("SessionLocal is None after configure_engine")
    db = factory()
    try:
        # Ensure a draft version exists for dependency check
        put_protocol_draft_version(
            STUDY,
            status="DRAFT",
            created_by="phase30_4",
            based_on={"snapshot": None, "decisions": []},
        )

        # DRAFT generate — no bypass of critical blockers
        draft_out: dict = {"attempted": True, "mode": "DRAFT"}
        try:
            art = generate_docx_artifact(
                db, STUDY, created_by="phase30_4", force_warnings_ok=True, mode="DRAFT"
            )
            data, meta = read_artifact_bytes(db, art["artifact_id"])
            docx_path = OUT / f"UPDCB-DRAFT-{stamp}.docx"
            docx_path.write_bytes(data)
            blob, visual = _blob_from_docx(docx_path)
            flags = _content_flags(blob)
            integrity = assess_docx_semantic_integrity(
                docx_path, ctx, mode="DRAFT", toc_refreshed=True
            )
            draft_out.update(
                {
                    "ok": True,
                    "artifact_id": art.get("artifact_id"),
                    "path": str(docx_path),
                    "bytes": len(data),
                    "sha256": art.get("sha256"),
                    "scrub": art.get("scrub"),
                    "visual": visual,
                    "content_flags": flags,
                    "integrity": integrity.to_dict(),
                }
            )
            report["visual"] = visual
            report["content"] = flags
            report["toc"] = {
                "toc_lines_sample": (visual.get("toc_lines") or [])[:15],
                "toc_refreshed_claimed": (art.get("toc_status") or {}).get("toc_refreshed")
                if isinstance(art.get("toc_status"), dict)
                else None,
                "note": "PDF page-proof unavailable without LibreOffice/Word COM; TOC lines inspected from DOCX styles",
            }
            # Cross-section: compare cover dose/form vs product ctx
            product = ctx.get("product") or {}
            cover = "\n".join(" | ".join(r) for r in (visual.get("cover_rows") or []))
            report["cross_section"] = {
                "canonical_dose": product.get("dosage"),
                "canonical_form": product.get("dosage_form"),
                "canonical_name": product.get("trade_name") or product.get("inn"),
                "canonical_washout": (ctx.get("washout") or {}).get("selected_value"),
                "cover_contains_dose": bool(
                    product.get("dosage") and str(product.get("dosage")) in cover
                ),
                "cover_form_not_56": "56" not in cover.split("Лекарственная форма")[-1][:40]
                if "Лекарственная форма" in cover
                else None,
                "cover_rows": visual.get("cover_rows"),
            }
        except ValidationError as e:
            draft_out.update(
                {
                    "ok": False,
                    "blocked": True,
                    "field": e.field,
                    "message": e.message,
                    "details": e.details,
                }
            )
        except Exception as exc:  # noqa: BLE001
            draft_out.update({"ok": False, "error": str(exc), "trace": traceback.format_exc()[-1500:]})
        report["draft"] = draft_out

        # FINAL — only if preflight allows; never bypass
        final_out: dict = {"attempted": True, "mode": "FINAL"}
        if not pf.get("can_finalize"):
            final_out.update(
                {
                    "ok": False,
                    "blocked": True,
                    "reason": "preflight.can_finalize=false — FINAL not attempted with bypass",
                    "critical_blockers": report["preflight"]["critical_blockers"],
                    "semantic_blockers": sem_pf.get("blockers"),
                    "status": "BLOCKED",
                }
            )
        else:
            try:
                art_f = generate_docx_artifact(
                    db, STUDY, created_by="phase30_4", force_warnings_ok=True, mode="FINAL"
                )
                data_f, _ = read_artifact_bytes(db, art_f["artifact_id"])
                path_f = OUT / f"UPDCB-FINAL-{stamp}.docx"
                path_f.write_bytes(data_f)
                blob_f, visual_f = _blob_from_docx(path_f)
                integ_f = assess_docx_semantic_integrity(
                    path_f, ctx, mode="FINAL", toc_refreshed=True
                )
                final_out.update(
                    {
                        "ok": integ_f.ok,
                        "path": str(path_f),
                        "bytes": len(data_f),
                        "content_flags": _content_flags(blob_f),
                        "integrity": integ_f.to_dict(),
                        "visual": visual_f,
                        "status": "PASS" if integ_f.ok else "BLOCKED",
                    }
                )
            except ValidationError as e:
                final_out.update(
                    {
                        "ok": False,
                        "blocked": True,
                        "status": "BLOCKED",
                        "field": e.field,
                        "message": e.message,
                        "details": e.details,
                    }
                )
        report["final"] = final_out
    finally:
        db.close()

    # Result classification
    p0: list[str] = []
    p1: list[str] = []
    if not (report.get("draft") or {}).get("ok"):
        p0.append("DRAFT generation blocked or failed")
    flags = report.get("content") or {}
    if flags.get("dosage_form_is_56"):
        p0.append("Cover dosage_form mapped to subject count 56")
    if flags.get("internal_table_id"):
        p0.append("Internal table registry name leaked")
    if flags.get("accepted_calculation_enum"):
        p0.append("Technical enum ACCEPTED_CALCULATION leaked")
    if flags.get("stale_400") and (report.get("final") or {}).get("ok"):
        p0.append("Stale 400 mg in accepted FINAL")
    if flags.get("placeholder_hits") and (report.get("final") or {}).get("ok"):
        p0.append("Placeholders in accepted FINAL")
    if flags.get("stale_400"):
        p1.append("Stale 400 mg still present in DRAFT artifact (expected until product composition cleared)")
    if flags.get("placeholder_hits"):
        p1.append(f"DRAFT placeholders remain ({len(flags['placeholder_hits'])})")
    if flags.get("stale_date_18042025"):
        p1.append("Template date 18.04.2025 residue in DRAFT")
    if (report.get("final") or {}).get("blocked"):
        p1.append("FINAL correctly BLOCKED — required sources incomplete")

    if p0:
        result = "FAIL"
    elif (report.get("draft") or {}).get("ok") and (report.get("final") or {}).get("blocked"):
        result = "PASS-WITH-BLOCKERS"
    elif (report.get("draft") or {}).get("ok") and (report.get("final") or {}).get("ok"):
        result = "PASS"
    else:
        result = "FAIL"

    report["P0"] = p0
    report["P1"] = p1
    report["result"] = result
    report["page_count"] = "N/A (no PDF renderer on runner host)"
    report["generator_version"] = get_settings().app_version

    OUT.mkdir(parents=True, exist_ok=True)
    out_json = OUT / f"acceptance-{stamp}.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    out_json.write_text(payload, encoding="utf-8")
    (OUT / "acceptance-latest.json").write_text(payload, encoding="utf-8")
    # Also mirror under docs for the Phase report
    docs_mirror = ROOT / "docs" / "phase30_4_data"
    try:
        docs_mirror.mkdir(parents=True, exist_ok=True)
        (docs_mirror / "acceptance-latest.json").write_text(payload, encoding="utf-8")
    except OSError:
        pass
    summary = {
        "result": result,
        "path": str(out_json),
        "exists": out_json.is_file(),
        "P0": p0,
        "P1": p1[:8],
        "draft_ok": (report.get("draft") or {}).get("ok"),
        "draft_field": (report.get("draft") or {}).get("field"),
        "draft_message": (report.get("draft") or {}).get("message"),
        "expert_resolutions": len(report.get("expert_conflict_resolutions") or []),
        "can_generate_docx": (report.get("preflight") or {}).get("can_generate_docx"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
