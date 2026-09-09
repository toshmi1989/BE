"""AI provider abstraction — Local AI is assistive only, never source of truth."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from app.domain.ai_prompts import PromptTemplate, get_prompt
from app.domain.ai_schemas import AIClaimDraft, AIExtractionResult, AIProviderStatus, ChunkContext
from app.domain.exceptions import ValidationError
from app.domain.evidence_normalize import normalize_claim_value


def _normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def evidence_grounded(evidence_text: str, chunk_text: str) -> bool:
    ev = _normalize_ws(evidence_text)
    ch = _normalize_ws(chunk_text)
    if not ev or not ch:
        return False
    return ev in ch


def validate_claims_against_chunks(
    result: AIExtractionResult, chunks: list[ChunkContext]
) -> AIExtractionResult:
    """Reject claims without grounding; never invent data."""
    by_chunk = {c.chunk_id: c for c in chunks}
    kept: list[AIClaimDraft] = []
    for claim in result.claims:
        chunk = by_chunk.get(claim.chunk_id)
        if chunk is None:
            continue
        if str(claim.document_id) != str(chunk.document_id):
            continue
        if str(claim.source_id) != str(chunk.source_id):
            continue
        if not evidence_grounded(claim.evidence_text, chunk.text):
            continue
        # re-normalize deterministically when possible
        try:
            nv = normalize_claim_value(claim.field_name, claim.value or claim.evidence_text)
            claim = claim.model_copy(
                update={
                    "normalized_value": nv.normalized,
                    "unit": claim.unit or nv.unit,
                    "status": "PROPOSED",
                }
            )
        except ValidationError:
            claim = claim.model_copy(update={"status": "PROPOSED"})
        kept.append(claim)
    not_found = result.not_found or len(kept) == 0
    return AIExtractionResult(claims=kept, not_found=not_found, notes=result.notes)


def parse_extraction_json(raw: str) -> AIExtractionResult:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid AI JSON: {exc}", field="ai_output") from exc
    return AIExtractionResult.model_validate(data)


class AIProvider(ABC):
    name: str

    @abstractmethod
    def status(self) -> AIProviderStatus:
        raise NotImplementedError

    @abstractmethod
    def extract_evidence(
        self, *, task_type: str, chunks: list[ChunkContext], prompt: PromptTemplate
    ) -> AIExtractionResult:
        raise NotImplementedError

    def extract_product_data(self, chunks: list[ChunkContext]) -> AIExtractionResult:
        return self.extract_evidence(
            task_type="EXTRACT_PRODUCT_DATA", chunks=chunks, prompt=get_prompt("EXTRACT_REFERENCE")
        )

    def extract_pk_data(self, chunks: list[ChunkContext]) -> AIExtractionResult:
        return self.extract_evidence(
            task_type="EXTRACT_PK_DATA", chunks=chunks, prompt=get_prompt("EXTRACT_PK")
        )

    def extract_analytes(self, chunks: list[ChunkContext]) -> AIExtractionResult:
        return self.extract_evidence(
            task_type="EXTRACT_ANALYTES", chunks=chunks, prompt=get_prompt("EXTRACT_ANALYTES")
        )

    def extract_food_condition(self, chunks: list[ChunkContext]) -> AIExtractionResult:
        return self.extract_evidence(
            task_type="EXTRACT_FOOD_CONDITION", chunks=chunks, prompt=get_prompt("EXTRACT_FOOD")
        )

    def extract_study_design(self, chunks: list[ChunkContext]) -> AIExtractionResult:
        return self.extract_evidence(
            task_type="EXTRACT_STUDY_DESIGN", chunks=chunks, prompt=get_prompt("EXTRACT_DESIGN")
        )

    def extract_cv_data(self, chunks: list[ChunkContext]) -> AIExtractionResult:
        return self.extract_evidence(
            task_type="EXTRACT_CV", chunks=chunks, prompt=get_prompt("EXTRACT_CV")
        )

    def find_conflicts(self, claims_json: str) -> dict[str, Any]:
        return {"conflicts": []}


class DisabledAIProvider(AIProvider):
    name = "disabled"

    def status(self) -> AIProviderStatus:
        return AIProviderStatus(
            enabled=False, provider=self.name, model=None, available=False, detail="AI_ENABLED=false"
        )

    def extract_evidence(
        self, *, task_type: str, chunks: list[ChunkContext], prompt: PromptTemplate
    ) -> AIExtractionResult:
        raise ValidationError("AI is disabled", field="ai_enabled")


class MockAIProvider(AIProvider):
    """Deterministic extractor for tests — no network."""

    name = "mock"

    def __init__(self, model: str = "mock-extractor") -> None:
        self.model = model

    def status(self) -> AIProviderStatus:
        return AIProviderStatus(
            enabled=True, provider=self.name, model=self.model, available=True, detail="mock"
        )

    def extract_evidence(
        self, *, task_type: str, chunks: list[ChunkContext], prompt: PromptTemplate
    ) -> AIExtractionResult:
        claims: list[AIClaimDraft] = []
        for ch in chunks:
            text = ch.text
            low = text.lower()

            def add(field: str, value: str, evidence: str, conf: float = 0.9) -> None:
                if evidence.lower() not in low and evidence not in text:
                    # require evidence substring
                    if _normalize_ws(evidence) not in _normalize_ws(text):
                        return
                claims.append(
                    AIClaimDraft(
                        field_name=field,
                        value=value,
                        source_id=ch.source_id,
                        document_id=ch.document_id,
                        page=ch.page,
                        chunk_id=ch.chunk_id,
                        evidence_text=evidence,
                        confidence=conf,
                        status="PROPOSED",
                    )
                )

            if "extract_pk" in prompt.prompt_id.lower() or "PK" in task_type:
                for m in re.finditer(
                    r"(Tmax[^\n.]{0,60}?(\d+(?:[.,]\d+)?(?:\s*[–\-—to]+\s*\d+(?:[.,]\d+)?)?\s*(?:h|hours?|час[аов]*)))",
                    text,
                    re.I,
                ):
                    add("tmax", m.group(2), m.group(1), 0.94)
                for m2 in re.finditer(
                    r"((?:half[- ]?life|период полувыведения)[^\n.]{0,60}?"
                    r"(\d+(?:[.,]\d+)?\s*[–\-—to]+\s*\d+(?:[.,]\d+)?\s*(?:h|hours?|час[аов]*)))",
                    text,
                    re.I,
                ):
                    add("half_life", m2.group(2), m2.group(1), 0.93)

            if "EXTRACT_CV" in prompt.prompt_id or "CV" in task_type:
                m = re.search(
                    r"((?:within-subject|CVintra|coefficient of variation)[^\n.]{0,80}?"
                    r"(Cmax)[^\n.]{0,40}?(\d+(?:[.,]\d+)?\s*%))",
                    text,
                    re.I,
                )
                if m:
                    add("cv_cmax", m.group(3), m.group(1), 0.91)

            if "EXTRACT_FOOD" in prompt.prompt_id or "FOOD" in task_type:
                if re.search(r"with food|fed|после еды|с пищей", text, re.I):
                    m = re.search(r"([^\n.]{0,80}(?:with food|fed|после еды|с пищей)[^\n.]{0,40})", text, re.I)
                    if m:
                        add("food_condition", "FED", m.group(1).strip(), 0.9)

            if "EXTRACT_REFERENCE" in prompt.prompt_id or "PRODUCT" in task_type:
                m = re.search(r"(reference product[^\n.]{0,60})", text, re.I)
                if m:
                    add("reference_product", m.group(1), m.group(1), 0.85)

        result = AIExtractionResult(claims=claims, not_found=len(claims) == 0, notes=None)
        return validate_claims_against_chunks(result, chunks)


class LocalAIProvider(AIProvider):
    """Ollama-compatible REST provider (/api/chat). Failures are non-fatal to the app."""

    name = "local"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

    def status(self) -> AIProviderStatus:
        try:
            import httpx

            r = httpx.get(f"{self.base_url}/api/tags", timeout=min(5.0, self.timeout))
            ok = r.status_code == 200
            return AIProviderStatus(
                enabled=True,
                provider=self.name,
                model=self.model,
                available=ok,
                detail=None if ok else f"HTTP {r.status_code}",
            )
        except Exception as exc:  # noqa: BLE001
            return AIProviderStatus(
                enabled=True,
                provider=self.name,
                model=self.model,
                available=False,
                detail=str(exc)[:200],
            )

    def extract_evidence(
        self, *, task_type: str, chunks: list[ChunkContext], prompt: PromptTemplate
    ) -> AIExtractionResult:
        import httpx

        chunks_json = json.dumps([c.model_dump() for c in chunks], ensure_ascii=False)
        user = prompt.user_template.format(
            task_type=task_type, chunks_json=chunks_json, focus=""
        )
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": user},
            ],
        }
        last_err: Exception | None = None
        for _ in range(2):
            try:
                r = httpx.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                body = r.json()
                content = body.get("message", {}).get("content") or body.get("response") or ""
                parsed = parse_extraction_json(content)
                return validate_claims_against_chunks(parsed, chunks)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
        raise ValidationError(
            f"Local AI extraction failed: {last_err}", field="ai_provider"
        ) from last_err


def get_ai_provider(
    *,
    enabled: bool,
    provider: str,
    base_url: str,
    model: str,
    timeout: float,
    max_tokens: int,
    temperature: float,
    force_mock: bool = False,
) -> AIProvider:
    if force_mock:
        return MockAIProvider(model=model or "mock-extractor")
    if not enabled:
        return DisabledAIProvider()
    if provider in {"mock", "test"}:
        return MockAIProvider(model=model or "mock-extractor")
    if provider in {"local", "ollama"}:
        return LocalAIProvider(
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    # External intentionally not implemented
    return DisabledAIProvider()
