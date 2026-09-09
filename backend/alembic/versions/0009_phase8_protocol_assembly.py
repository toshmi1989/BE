"""Phase 8 Protocol Assembly Alembic migration.

Revision ID: 0009_phase8_protocol_assembly
Revises: 0008_phase7_local_ai
Create Date: 2026-08-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_phase8_protocol_assembly"
down_revision: Union[str, None] = "0008_phase7_local_ai"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "protocol_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_version", sa.String(length=64), nullable=False),
        sa.Column("template_version", sa.String(length=64), nullable=False),
        sa.Column("rules_version", sa.String(length=64), nullable=False),
        sa.Column("generator_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("canonical_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("consistency_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protocol_drafts_project_id", "protocol_drafts", ["project_id"])

    op.create_table(
        "protocol_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("protocol_id", sa.Uuid(), nullable=False),
        sa.Column("section_code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("parent_section", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generation_status", sa.String(length=32), nullable=False),
        sa.Column("content_blocks", sa.JSON(), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("template_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protocol_sections_protocol_id", "protocol_sections", ["protocol_id"])

    op.create_table(
        "protocol_tables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("protocol_id", sa.Uuid(), nullable=False),
        sa.Column("section_code", sa.String(length=32), nullable=False),
        sa.Column("table_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("display_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protocol_tables_protocol_id", "protocol_tables", ["protocol_id"])

    op.create_table(
        "protocol_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("protocol_id", sa.Uuid(), nullable=False),
        sa.Column("source_section", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("display_text", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protocol_references_protocol_id", "protocol_references", ["protocol_id"])

    op.create_table(
        "protocol_build_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("protocol_id", sa.Uuid(), nullable=False),
        sa.Column("generated_sections", sa.JSON(), nullable=False),
        sa.Column("unresolved_fields", sa.JSON(), nullable=False),
        sa.Column("blocking_issues", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("calculated_values", sa.JSON(), nullable=False),
        sa.Column("expert_verified_values", sa.JSON(), nullable=False),
        sa.Column("extras", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("protocol_id"),
    )


def downgrade() -> None:
    op.drop_table("protocol_build_reports")
    op.drop_index("ix_protocol_references_protocol_id", table_name="protocol_references")
    op.drop_table("protocol_references")
    op.drop_index("ix_protocol_tables_protocol_id", table_name="protocol_tables")
    op.drop_table("protocol_tables")
    op.drop_index("ix_protocol_sections_protocol_id", table_name="protocol_sections")
    op.drop_table("protocol_sections")
    op.drop_index("ix_protocol_drafts_project_id", table_name="protocol_drafts")
    op.drop_table("protocol_drafts")
