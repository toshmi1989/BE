"""Phase 30.4 — Visual/semantic acceptance gates (no new medical rules)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings, get_settings
from app.domain.docx_profile import DOCX_GENERATOR_VERSION
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION

ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE = ROOT / "docs" / "phase30_4_data" / "acceptance-latest.json"


def test_version_0354():
    assert Settings().app_version == "0.35.5"
    assert PROTOCOL_GENERATOR_VERSION == "0.35.5"
    assert DOCX_GENERATOR_VERSION == "0.35.5"
    assert get_settings().app_version == "0.35.5"


def test_acceptance_artifact_exists_and_pass_with_blockers():
    assert ACCEPTANCE.is_file(), "Run docs/_phase30_4_acceptance_run.py first"
    data = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    assert data.get("result") in {"PASS", "PASS-WITH-BLOCKERS"}
    assert data.get("gate_bypass") is False
    assert data.get("ai_enabled") is False
    draft = data.get("draft") or {}
    assert draft.get("ok") is True
    flags = data.get("content") or draft.get("content_flags") or {}
    assert flags.get("dosage_form_is_56") is False
    assert flags.get("bosutinib") is False
    assert flags.get("internal_table_id") is False
    assert flags.get("accepted_calculation_enum") is False
    assert flags.get("stale_400") is False
    final = data.get("final") or {}
    assert final.get("blocked") is True or final.get("ok") is True
    if not final.get("ok"):
        assert final.get("blocked") is True


def test_cover_not_subject_count_in_acceptance_cross_section():
    data = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    xs = data.get("cross_section") or {}
    rows = xs.get("cover_rows") or []
    joined = "\n".join(" | ".join(r) for r in rows)
    # dosage form row must not be bare 56
    for row in rows:
        if len(row) >= 2 and "лекарственная форма" in row[0].lower():
            assert row[1].strip() != "56"
            assert "15" in row[1] or "mg" in row[1].lower() or "мг" in row[1].lower() or "tablet" in row[1].lower()
    assert "UPDCB-02-BE-2026" in joined or xs.get("canonical_name")
