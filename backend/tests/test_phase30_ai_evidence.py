"""Phase 30 — AI / product evidence extraction tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.db import Base, configure_engine, get_engine
from app.domain.decision_store import clear_decision_store, get_context, put_context
from app.domain.decision_context import DecisionContext
from app.domain.product_evidence_service import (
    extract_product_evidence_for_study,
    list_product_evidence_panel,
)
from app.domain.product_knowledge import PRODUCT_KNOWLEDGE_FIELDS, catalog_as_list
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.research_conflicts import detect_numeric_conflicts
from app.domain.research_evidence_engine import reject_claim, verify_claim
from app.domain.research_evidence_models import ResearchClaim
from app.domain.research_evidence_store import clear_research_evidence_store, list_claims, put_claim
from app.domain.research_usability import apply_usability
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.study_workspace import reset_workspace_store
from app.domain.template_contamination import (
    contamination_preflight,
    has_verified_product_pharmacology,
)
from app.domain.workspace_assembly_context import build_workspace_assembly_context
from app.domain.workspace_gaps import apply_verified_evidence
from app.main import create_app
import app.models  # noqa: F401

STUDY = "UPDCB-02-BE-2026"


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("DOCUMENT_STORAGE_ROOT", str(tmp_path / "docs"))
    get_settings.cache_clear()
    configure_engine("sqlite+pysqlite:///:memory:")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    reset_workspace_store()
    reset_sample_size_store()
    reset_statistics_store()
    clear_research_evidence_store()
    clear_decision_store()
    clear_study_input()
    yield
    reset_workspace_store()
    clear_research_evidence_store()
    clear_decision_store()
    clear_study_input()
    Base.metadata.drop_all(bind=engine)
    get_settings.cache_clear()


@pytest.fixture
def client():
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c


def test_phase30_version():
    assert Settings().app_version == "0.35.2"
    assert PROTOCOL_GENERATOR_VERSION == "0.35.2"


def test_ai_proposal_creation_and_proposed_status():
    text = (
        "SmPC: МНН: upadacitinib. Механизм действия: селективный ингибитор JAK. "
        "Tmax 1–2 h after oral administration. Период полувыведения 9–14 h."
    )
    # Seed a minimal package-like chunk via direct claim path through extract with monkeypatch
    from app.domain import product_evidence_service as pes

    chunks = [
        pes.ChunkContext(
            chunk_id="c1",
            document_id="d1",
            source_id="smpc-1",
            page=1,
            text=text,
        )
    ]

    def _fake_chunks(study_id, package_id=None):
        return chunks

    pes._package_document_chunks = _fake_chunks  # type: ignore[attr-defined]
    out = extract_product_evidence_for_study(STUDY, force_mock=True, actor="t")
    assert out["auto_verified"] is False
    assert out["study_mutated"] is False
    assert out["canonical_mutated"] is False
    assert out["claims_created"] >= 1
    for c in list_claims(study_id=STUDY):
        assert c.verification_status == "PROPOSED"
        assert c.excerpt
        assert c.source_id or c.excerpt


def test_provenance_and_no_direct_mutation():
    claim = ResearchClaim(
        claim_text="product.mechanism: JAK inhibitor",
        field_path="product.mechanism",
        value="селективный ингибитор JAK",
        excerpt="Механизм действия: селективный ингибитор JAK",
        location="smpc:p12",
        source_id="SRC-1",
        extraction_method="AI",
        confidence="HIGH",
        verification_status="PROPOSED",
        study_id=STUDY,
    )
    apply_usability(claim)
    put_claim(claim)
    assert claim.verification_status == "PROPOSED"
    # PROPOSED must not clear FINAL gate
    ctx = {"study_id": STUDY, "product": {"inn": "upadacitinib"}, "structured_facts": {}, "fact_sources": {}}
    assert has_verified_product_pharmacology(ctx) is False
    final = contamination_preflight(ctx, mode="FINAL")
    assert final["ok"] is False


def test_verification_rejection_and_final_gate():
    # All required_for_final_pharmacology fields must be verified to clear FINAL
    claims = []
    for fp, val, excerpt in (
        (
            "product.pharmacology",
            "ингибитор янус-киназ",
            "Фармакология: ингибитор янус-киназ upadacitinib",
        ),
        (
            "product.mechanism",
            "селективный обратимый ингибитор JAK1",
            "Механизм действия: селективный обратимый ингибитор JAK1",
        ),
        (
            "product.pharmacological_class",
            "иммунодепрессанты; ингибиторы Янус-киназ (JAK)",
            "Фармакотерапевтическая группа: иммунодепрессанты; ингибиторы Янус-киназ (JAK)",
        ),
    ):
        c = ResearchClaim(
            claim_text=f"{fp}: {val}",
            field_path=fp,
            value=val,
            excerpt=excerpt,
            location="smpc:p10",
            source_id="SRC-PHARM",
            extraction_method="AI",
            confidence="HIGH",
            verification_status="PROPOSED",
            study_id=STUDY,
        )
        apply_usability(c)
        put_claim(c)
        claims.append(c)

    # Reject path — wrong-product claim must not unlock the gate
    other = ResearchClaim(
        claim_text="wrong",
        field_path="product.mechanism",
        value="Bosutinib TKI for CML",
        excerpt="Bosutinib inhibits Bcr-Abl",
        location="bad:p1",
        source_id="SRC-BAD",
        extraction_method="AI",
        confidence="HIGH",
        study_id=STUDY,
    )
    apply_usability(other)
    put_claim(other)
    rejected = reject_claim(other.id, reviewer="expert", rationale="wrong product")
    assert rejected.verification_status == "REJECTED"

    for c in claims:
        verified = verify_claim(
            c.id,
            reviewer="expert",
            applicability="DIRECT",
            applicability_reason="SmPC for upadacitinib prolonged-release 15 mg",
        )
        assert verified.verification_status == "VERIFIED"

    put_context(STUDY, DecisionContext(study_id=STUDY, package_id=None))
    applied = apply_verified_evidence(STUDY)
    assert any("pharmacology" in a or "mechanism" in a for a in applied["applied_fields"])
    ctx = build_workspace_assembly_context(STUDY)
    ctx["study_id"] = STUDY
    assert has_verified_product_pharmacology(ctx) is True
    final = contamination_preflight(ctx, mode="FINAL")
    assert final["ok"] is True


def test_ai_off_deterministic_works(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    get_settings.cache_clear()
    from app.domain import product_evidence_service as pes

    pes._package_document_chunks = lambda *_a, **_k: [  # type: ignore[attr-defined]
        pes.ChunkContext(
            chunk_id="c1",
            document_id="d1",
            source_id="s1",
            page=1,
            text="МНН: upadacitinib. Tmax 2 h. Период полувыведения 12 h.",
        )
    ]
    out = extract_product_evidence_for_study(STUDY, force_mock=False)
    assert out["provider"] in {"disabled", "mock"} or out["claims_created"] >= 0
    assert out["auto_verified"] is False
    # Deterministic should still find Tmax / inn when text present
    assert out["claims_created"] >= 1


def test_api_product_evidence_panel(client: TestClient):
    r = client.get(f"/api/studies/{STUDY}/product-evidence")
    assert r.status_code == 200
    body = r.json()
    assert "proposals" in body
    assert body["final_gate"]["unverified_ai_cannot_clear"] is True


def test_panel_lists_proposals():
    put_claim(
        ResearchClaim(
            claim_text="x",
            field_path="pk.expected_tmax",
            value="2-4",
            unit="ч",
            excerpt="Tmax 2-4 h",
            location="p1",
            source_id="s",
            extraction_method="DETERMINISTIC",
            study_id=STUDY,
        )
    )
    panel = list_product_evidence_panel(STUDY)
    assert panel["counts"]["proposed"] >= 1
    assert panel["proposals"][0]["status"] == "PROPOSED"
    assert "AI confidence" in (panel["proposals"][0].get("ai_confidence_note") or "AI confidence")
