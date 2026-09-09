"""Phase 7 AI provider / grounding unit tests — no real LLM."""

from __future__ import annotations

import pytest

from app.domain.ai_provider import (
    DisabledAIProvider,
    MockAIProvider,
    evidence_grounded,
    parse_extraction_json,
    validate_claims_against_chunks,
)
from app.domain.ai_prompts import get_prompt
from app.domain.ai_schemas import AIClaimDraft, AIExtractionResult, ChunkContext
from app.domain.exceptions import ValidationError


def _chunk(**kwargs) -> ChunkContext:
    base = dict(
        source_id="src-1",
        document_id="doc-1",
        page=1,
        chunk_id="chk-1",
        text="Tmax was 2-3 hours after dosing. Half-life ranged from 35 to 50 hours.",
    )
    base.update(kwargs)
    return ChunkContext(**base)


def test_parse_valid_json() -> None:
    raw = """
    {"claims":[{"field_name":"tmax","value":"2-3 h","source_id":"s","document_id":"d",
    "page":1,"chunk_id":"c","evidence_text":"2-3 h","confidence":0.9,"status":"VERIFIED"}],
    "not_found":false}
    """
    result = parse_extraction_json(raw)
    assert result.claims[0].status == "PROPOSED"  # forced


def test_parse_invalid_json() -> None:
    with pytest.raises(ValidationError):
        parse_extraction_json("not-json")


def test_missing_evidence_rejected() -> None:
    with pytest.raises(Exception):
        AIClaimDraft(
            field_name="tmax",
            value="2 h",
            source_id="s",
            document_id="d",
            page=1,
            chunk_id="c",
            evidence_text="",
            confidence=0.9,
        )


def test_grounding_and_ungrounded_drop() -> None:
    chunk = _chunk()
    bad = AIExtractionResult(
        claims=[
            AIClaimDraft(
                field_name="tmax",
                value="99 h",
                source_id="src-1",
                document_id="doc-1",
                page=1,
                chunk_id="chk-1",
                evidence_text="invented text not in chunk",
                confidence=0.99,
            ),
            AIClaimDraft(
                field_name="tmax",
                value="2-3 hours",
                source_id="src-1",
                document_id="doc-1",
                page=1,
                chunk_id="chk-1",
                evidence_text="Tmax was 2-3 hours",
                confidence=0.94,
            ),
        ]
    )
    cleaned = validate_claims_against_chunks(bad, [chunk])
    assert len(cleaned.claims) == 1
    assert cleaned.claims[0].normalized_value["min"] == 2
    assert cleaned.claims[0].normalized_value["max"] == 3


def test_evidence_grounded() -> None:
    assert evidence_grounded("2-3 hours", "Tmax was 2-3 hours after")
    assert not evidence_grounded("fabricated", "Tmax was 2-3 hours")


def test_mock_pk_cv_food_extraction() -> None:
    provider = MockAIProvider()
    chunks = [
        _chunk(
            text=(
                "Tmax was 2-3 hours. Elimination half-life ranged from 35 to 50 hours. "
                "Within-subject coefficient of variation for Cmax was 28.4%. "
                "The reference product should be administered with food."
            )
        )
    ]
    pk = provider.extract_pk_data(chunks)
    assert any(c.field_name == "tmax" for c in pk.claims)
    assert any(c.field_name == "half_life" for c in pk.claims)
    assert all(c.status == "PROPOSED" for c in pk.claims)

    cv = provider.extract_cv_data(chunks)
    assert any(c.field_name == "cv_cmax" for c in cv.claims)

    food = provider.extract_food_condition(chunks)
    assert any(c.field_name == "food_condition" for c in food.claims)


def test_disabled_provider() -> None:
    p = DisabledAIProvider()
    assert p.status().available is False
    with pytest.raises(ValidationError):
        p.extract_pk_data([_chunk()])


def test_prompt_versioning() -> None:
    p = get_prompt("EXTRACT_PK")
    assert p.full_id == "EXTRACT_PK.v1"
    assert "PROPOSED" in p.system


def test_multiple_tmax_claims_remain_proposed() -> None:
    provider = MockAIProvider()
    chunks = [
        ChunkContext(
            source_id="src-a",
            document_id="doc-a",
            page=1,
            chunk_id="c1",
            text="Tmax was 2-3 hours after dosing.",
        ),
        ChunkContext(
            source_id="src-b",
            document_id="doc-b",
            page=2,
            chunk_id="c2",
            text="In another study Tmax was 4 hours under fed conditions.",
        ),
    ]
    result = provider.extract_pk_data(chunks)
    tmax = [c for c in result.claims if c.field_name == "tmax"]
    assert len(tmax) >= 2
    assert all(c.status == "PROPOSED" for c in tmax)
    # no auto-pick: both values preserved
    values = {c.value for c in tmax}
    assert any("2" in v for v in values)
    assert any("4" in v for v in values)
