"""Phase 28 — Typed response schemas for critical Writer Workspace endpoints.

Use ConfigDict(extra="allow") so richer existing payloads still validate without
stripping unknown fields from OpenAPI responses.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Flexible(BaseModel):
    """Base for Writer payloads that may grow beyond the documented core fields."""

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Study catalog
# ---------------------------------------------------------------------------


class StudyCatalogItem(_Flexible):
    study_key: str
    study_id: str | None = None
    name: str | None = None
    title: str | None = None
    product: str | None = None
    sponsor: str | None = None
    dose: str | None = None
    status: str | None = None
    lifecycle: str | None = None
    readiness: str | None = None
    readiness_code: str | None = None
    readiness_label: str | None = None
    document_count: int | None = None
    state_version: int | None = None
    organization_id: str | None = None
    created_by_user_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StudyCatalogListResponse(_Flexible):
    studies: list[StudyCatalogItem] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 20
    organization_id: str | None = None


# ---------------------------------------------------------------------------
# Canonical facts
# ---------------------------------------------------------------------------


class CanonicalFactRow(_Flexible):
    field: str
    value: Any = None
    canonical_value: Any = None
    status: str | None = None
    source: str | None = None
    evidence_id: str | None = None
    affected_sections: list[Any] = Field(default_factory=list)


class CanonicalFactDetailResponse(_Flexible):
    """Writer field-detail drawer — core keys plus nested source/evidence/decision."""

    field: str | None = None
    field_path: str | None = None
    study_id: str | None = None
    value: Any = None
    current_value: Any = None
    canonical_value: Any = None
    status: str | None = None
    source: Any = None
    evidence_id: str | None = None
    evidence: Any = None
    decision: Any = None
    affected_sections: list[Any] = Field(default_factory=list)
    affected_protocol_sections: list[Any] = Field(default_factory=list)
    study_mutated: bool | None = None


# ---------------------------------------------------------------------------
# Workspace summary
# ---------------------------------------------------------------------------


class WorkspaceHeader(_Flexible):
    study_id: str | None = None
    sponsor: Any = None
    product: Any = None
    dose: Any = None
    study_status: str | None = None
    protocol_version: int | str | None = None
    overall_readiness: str | None = None
    readiness_code: str | None = None


class WorkspaceSummaryCards(_Flexible):
    documents: int | None = None
    critical_conflicts: int | None = None
    knowledge_gaps: int | None = None
    pending_decisions: int | None = None
    sample_size_status: str | None = None
    statistics_status: str | None = None
    protocol_status: str | None = None


class WorkspaceSummaryResponse(_Flexible):
    study_id: str
    header: WorkspaceHeader | dict[str, Any] | None = None
    nav: list[dict[str, Any]] = Field(default_factory=list)
    summary_cards: WorkspaceSummaryCards | dict[str, Any] | None = None
    readiness: dict[str, Any] | None = None
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    decisions: dict[str, Any] | None = None
    canonical_facts: list[CanonicalFactRow] = Field(default_factory=list)
    recommendation_is_not_approval: bool | None = None
    study_mutated: bool | None = None
    exposes_internal_enums: bool | None = None


# ---------------------------------------------------------------------------
# Writer progress
# ---------------------------------------------------------------------------


class WriterProgressStep(_Flexible):
    id: str
    label: str | None = None
    status: str | None = None
    tab: str | None = None


class WriterProgressResponse(_Flexible):
    study_id: str
    steps: list[WriterProgressStep] = Field(default_factory=list)
    primary_next_action: dict[str, Any] | None = None
    secondary_issues: list[dict[str, Any]] = Field(default_factory=list)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    package_checklist: list[dict[str, Any]] = Field(default_factory=list)
    counts: dict[str, Any] | None = None
    versions: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    summary_cards: dict[str, Any] | None = None
    derived_from_backend: bool | None = None
    ui_clicks_do_not_complete_steps: bool | None = None


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


class DecisionListResponse(_Flexible):
    study_id: str | None = None
    package_id: str | None = None
    fixture_id: str | None = None
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    open_conflicts: list[Any] = Field(default_factory=list)
    study_mutated: bool | None = None
    recommended_is_not_approved: bool | None = None


class DecisionActionResponse(_Flexible):
    """Expert approve / reject / modify / keep-current — shape varies by action."""

    id: str | None = None
    decision_id: str | None = None
    status: str | None = None
    study_id: str | None = None
    study_mutated: bool | None = None


# ---------------------------------------------------------------------------
# Sample size / statistics panels
# ---------------------------------------------------------------------------


class SampleSizePanelResponse(_Flexible):
    section: str | None = "SAMPLE_SIZE"
    study_id: str | None = None
    status: str | None = None
    calculated_n: int | float | None = None
    required_n: int | float | None = None
    latest_calculation_id: str | None = None
    study_mutated: bool | None = None
    calculated_shown_as_approved: bool | None = None


class StatisticsPanelResponse(_Flexible):
    section: str | None = "STATISTICS"
    study_id: str | None = None
    plan_id: str | None = None
    status: str | None = None
    is_approved: bool | None = None
    study_mutated: bool | None = None
    recommendation_shown_as_approved: bool | None = None


class StatisticsStudyResponse(_Flexible):
    study_id: str
    latest: dict[str, Any] | None = None
    panel: StatisticsPanelResponse | dict[str, Any] | None = None
    plans: list[dict[str, Any]] = Field(default_factory=list)
    study_mutated: bool | None = None


# ---------------------------------------------------------------------------
# Protocol preview / drafts / preflight / artifacts
# ---------------------------------------------------------------------------


class StaleDependencyReason(_Flexible):
    code: str | None = None
    field: str | None = None
    expected: Any = None
    actual: Any = None
    message: str | None = None


class StaleDependencies(_Flexible):
    stale: bool = False
    reasons: list[StaleDependencyReason | dict[str, Any]] = Field(default_factory=list)
    draft_version: int | None = None
    draft_protocol_id: str | None = None
    current_snapshot_id: str | None = None
    current_snapshot_version: int | None = None
    code: str | None = None


class PreflightCheck(_Flexible):
    category: str | None = None
    code: str | None = None
    severity: str | None = None
    message: str | None = None
    ok: bool | None = None
    label: str | None = None


class PreflightResponse(_Flexible):
    study_id: str
    categories: list[str] = Field(default_factory=list)
    checks: list[PreflightCheck | dict[str, Any]] = Field(default_factory=list)
    critical_blockers: list[dict[str, Any]] = Field(default_factory=list)
    can_finalize: bool | None = None
    can_generate_docx: bool | None = None
    readiness: str | None = None
    readiness_label: str | None = None
    study_mutated: bool | None = None
    message: str | None = None
    stale_dependencies: StaleDependencies | dict[str, Any] | None = None


class ProtocolDraftSummary(_Flexible):
    protocol_id: str | None = None
    version: int | None = None
    status: str | None = None
    based_on_snapshot: str | None = None
    based_on_decisions: list[str] | None = None
    based_on_statistics: str | None = None
    based_on_sample_size: str | None = None
    based_on_evidence: str | None = None


class ProtocolPreviewResponse(_Flexible):
    study_id: str
    protocol_id: str | None = None
    version: int | None = None
    status: str | None = None
    snapshot_id: str | None = None
    snapshot_version: int | None = None
    toc: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[Any] = Field(default_factory=list)
    field_bindings: dict[str, Any] | None = None
    source: str | None = None
    legacy_project_path: bool | None = None
    stale_template_values: bool | None = None
    stale_dependencies: StaleDependencies | dict[str, Any] | None = None


class ProtocolArtifactItem(_Flexible):
    artifact_id: str
    protocol_id: str | None = None
    study_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size: int | None = None
    sha256: str | None = None
    storage_key: str | None = None
    generated_at: str | None = None
    generated_by: str | None = None
    snapshot_id: str | None = None
    decision_set: list[str] = Field(default_factory=list)
    statistics_version: str | None = None
    sample_size_version: str | None = None
    rebuild_on_download: bool | None = None


class ProtocolArtifactsListResponse(_Flexible):
    study_id: str
    artifacts: list[ProtocolArtifactItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class AuthMeResponse(_Flexible):
    user_id: str
    email: str
    display_name: str | None = None
    organization_id: str | None = None
    role: str | None = None


class AuthLoginResponse(_Flexible):
    user_id: str
    email: str
    display_name: str | None = None
    organization_id: str | None = None
    role: str | None = None
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Workflow run
# ---------------------------------------------------------------------------


class WorkflowRunResponse(_Flexible):
    workflow_id: str
    study_id: str
    package_id: str | None = None
    fixture_id: str | None = None
    steps: list[dict[str, Any]] | None = None
    readiness: dict[str, Any] | None = None
    preflight: PreflightResponse | dict[str, Any] | None = None
    protocol_draft: ProtocolDraftSummary | dict[str, Any] | None = None
    workspace: WorkspaceSummaryResponse | dict[str, Any] | None = None
    persisted: bool | None = None
    legacy_protocol_path: bool | None = None
    db_authoritative: bool | None = None
    idempotent_replay: bool | None = None
    result_summary: dict[str, Any] | None = None
    study_mutated: bool | None = None
    automatic_medical_decisions: int | None = None
    guards: dict[str, Any] | None = None
