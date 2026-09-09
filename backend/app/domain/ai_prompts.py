"""Versioned AI extraction prompts — not embedded in business services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    prompt_id: str
    version: str
    system: str
    user_template: str

    @property
    def full_id(self) -> str:
        return f"{self.prompt_id}.{self.version}"


_SYSTEM = (
    "You are an assistive evidence extractor for bioequivalence protocol research. "
    "Return ONLY valid JSON matching the requested schema. "
    "Use ONLY facts present in the provided document chunks. "
    "Never invent values. If data is absent, return an empty claims list. "
    "Every claim MUST include evidence_text copied from a chunk, plus source_id, "
    "document_id, page, and chunk_id from that chunk. "
    "status must always be PROPOSED. Do not decide regulatory truth."
)

_USER = (
    "Task: {task_type}\n"
    "Extract structured claims for fields related to: {focus}\n"
    "Chunks (JSON array):\n{chunks_json}\n\n"
    "Respond with JSON object:\n"
    '{{"claims":[{{'
    '"field_name":"...","value":"...","normalized_value":{{}},"unit":null,'
    '"source_id":"...","document_id":"...","page":0,"chunk_id":"...",'
    '"evidence_text":"...","confidence":0.0,"status":"PROPOSED"'
    "}}],\"not_found\":false,\"notes\":null}}\n"
    "If nothing found: {{\"claims\":[],\"not_found\":true,\"notes\":\"NOT_FOUND\"}}"
)

PROMPTS: dict[str, PromptTemplate] = {
    "EXTRACT_REFERENCE": PromptTemplate(
        "EXTRACT_REFERENCE", "v1", _SYSTEM, _USER.replace("{focus}", "reference product / trade name / INN")
    ),
    "EXTRACT_REGISTRATION": PromptTemplate(
        "EXTRACT_REGISTRATION", "v1", _SYSTEM, _USER.replace("{focus}", "registration status / MAH")
    ),
    "EXTRACT_PK": PromptTemplate(
        "EXTRACT_PK", "v1", _SYSTEM, _USER.replace("{focus}", "Tmax, half-life, AUC, Cmax ranges")
    ),
    "EXTRACT_ANALYTES": PromptTemplate(
        "EXTRACT_ANALYTES", "v1", _SYSTEM, _USER.replace("{focus}", "analyte / metabolite names")
    ),
    "EXTRACT_FOOD": PromptTemplate(
        "EXTRACT_FOOD", "v1", _SYSTEM, _USER.replace("{focus}", "fed/fasting food condition")
    ),
    "EXTRACT_DESIGN": PromptTemplate(
        "EXTRACT_DESIGN", "v1", _SYSTEM, _USER.replace("{focus}", "crossover/parallel study design")
    ),
    "EXTRACT_CV": PromptTemplate(
        "EXTRACT_CV", "v1", _SYSTEM, _USER.replace("{focus}", "within-subject CV for Cmax/AUC")
    ),
    "EXTRACT_SAFETY": PromptTemplate(
        "EXTRACT_SAFETY", "v1", _SYSTEM, _USER.replace("{focus}", "safety statements")
    ),
    "FIND_CONFLICTS": PromptTemplate(
        "FIND_CONFLICTS",
        "v1",
        _SYSTEM,
        "Given claims JSON, list conflicting field groups. Return "
        '{{"conflicts":[{{"field_name":"...","values":[]}}]}}'
        "\nClaims:\n{chunks_json}",
    ),
}

SCHEMA_VERSION = "AI.CLAIM.SCHEMA.v1"


def get_prompt(prompt_id: str) -> PromptTemplate:
    if prompt_id not in PROMPTS:
        raise KeyError(prompt_id)
    return PROMPTS[prompt_id]
