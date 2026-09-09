"""Protocol assembly constants and content-block types."""

from __future__ import annotations

PROTOCOL_TEMPLATE_VERSION = "BE_Protocol_Template_v2.0"
PROTOCOL_GENERATOR_VERSION = "0.33.0"
PROTOCOL_SCHEMA_VERSION = "PROTOCOL.DRAFT.v1"

PROTOCOL_STATUSES = frozenset(
    {"DRAFT", "READY_FOR_REVIEW", "BLOCKED", "GENERATED", "APPROVED"}
)

SECTION_STATUSES = frozenset({"DRAFT", "GENERATED", "UNRESOLVED", "SKIPPED", "BLOCKED"})
GENERATION_STATUSES = frozenset({"PENDING", "OK", "UNRESOLVED", "SKIPPED", "FAILED"})

CONTENT_TYPES = frozenset(
    {
        "TEXT",
        "TABLE",
        "LIST",
        "NUMBERED_LIST",
        "REFERENCE",
        "FORMULA",
        "SIGNATURE",
        "PAGE_BREAK",
        "CONDITIONAL",
    }
)

# Forbidden invented placeholders — never emit these
FORBIDDEN_PLACEHOLDER_TOKENS = frozenset(
    {"хх", "xxx", "примерно", "approx", "tbd", "n/a", "???", "…"}
)

UNRESOLVED_MARKER_RE = r"\{\{[A-Z0-9_.]+\}\}"
