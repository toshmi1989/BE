"""Phase 17 — persistent workspace, auth, org isolation, artifacts.

Revision ID: 0014_phase17_workspace
Revises: 0013_phase12a1_knowledge
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_phase17_workspace"
down_revision: Union[str, None] = "0013_phase12a1_knowledge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = [
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
]


def upgrade() -> None:
    op.create_table(
        "workspace_organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_workspace_organizations_slug", "workspace_organizations", ["slug"])

    op.create_table(
        "user_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_user_accounts_email", "user_accounts", ["email"])

    op.create_table(
        "org_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        *_TS,
        sa.ForeignKeyConstraint(["organization_id"], ["workspace_organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_membership"),
    )

    op.create_table(
        "workspace_studies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("sponsor", sa.String(length=255), nullable=True),
        sa.Column("product", sa.String(length=255), nullable=True),
        sa.Column("dose", sa.String(length=64), nullable=True),
        sa.Column("lifecycle", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_TS,
        sa.ForeignKeyConstraint(["organization_id"], ["workspace_organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "study_key", name="uq_org_study_key"),
    )
    op.create_index("ix_workspace_studies_study_key", "workspace_studies", ["study_key"])

    op.create_table(
        "workspace_state_bags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("package_payload", sa.JSON(), nullable=True),
        sa.Column("decisions_payload", sa.JSON(), nullable=False),
        sa.Column("context_payload", sa.JSON(), nullable=True),
        sa.Column("sample_size_payload", sa.JSON(), nullable=False),
        sa.Column("statistics_payload", sa.JSON(), nullable=False),
        sa.Column("research_payload", sa.JSON(), nullable=True),
        sa.Column("workspace_meta", sa.JSON(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_key", name="uq_workspace_state_study"),
    )

    op.create_table(
        "workspace_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("based_on_decision_ids", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id"),
        sa.UniqueConstraint("study_key", "version", name="uq_snapshot_study_version"),
    )

    op.create_table(
        "workspace_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("selected_option", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_decision_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_id", "version", name="uq_ws_decision_ver"),
    )

    op.create_table(
        "workspace_evidence_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_key", sa.String(length=128), nullable=False),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("document_id", sa.String(length=128), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("page", sa.String(length=64), nullable=True),
        sa.Column("chunk", sa.String(length=128), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("applicability", sa.String(length=64), nullable=True),
        sa.Column("claim_type", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_key", name="uq_ws_claim_key"),
    )

    op.create_table(
        "workspace_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("safe_storage_name", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.String(length=255), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingestion_status", sa.String(length=32), nullable=False),
        sa.Column("classification_status", sa.String(length=32), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_ws_document_id"),
    )

    op.create_table(
        "workspace_protocol_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("protocol_id", sa.String(length=64), nullable=False),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("preflight_status", sa.String(length=64), nullable=True),
        sa.Column("based_on", sa.JSON(), nullable=False),
        sa.Column("sections_payload", sa.JSON(), nullable=False),
        sa.Column("preview_payload", sa.JSON(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("protocol_id"),
        sa.UniqueConstraint("study_key", "version", name="uq_ws_protocol_ver"),
    )

    op.create_table(
        "workspace_protocol_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("protocol_id", sa.String(length=64), nullable=False),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "mime_type",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=128), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("generated_by", sa.String(length=255), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("decision_set", sa.JSON(), nullable=False),
        sa.Column("statistics_version", sa.String(length=64), nullable=True),
        sa.Column("sample_size_version", sa.String(length=64), nullable=True),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id", name="uq_ws_artifact_id"),
    )

    op.create_table(
        "workspace_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("who", sa.String(length=255), nullable=True),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )

    op.create_table(
        "workspace_workflow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("study_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        *_TS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", name="uq_ws_workflow_id"),
    )


def downgrade() -> None:
    for t in (
        "workspace_workflow_runs",
        "workspace_audit_events",
        "workspace_protocol_artifacts",
        "workspace_protocol_drafts",
        "workspace_documents",
        "workspace_evidence_claims",
        "workspace_decisions",
        "workspace_snapshots",
        "workspace_state_bags",
        "workspace_studies",
        "org_memberships",
        "user_accounts",
        "workspace_organizations",
    ):
        op.drop_table(t)
