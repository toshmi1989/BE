"""Phase 9 DOCX generation migration.

Revision ID: 0010_phase9_docx
Revises: 0009_phase8_protocol_assembly
Create Date: 2026-08-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_phase9_docx"
down_revision: Union[str, None] = "0009_phase8_protocol_assembly"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generated_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_draft_id", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("template_version", sa.String(length=64), nullable=True),
        sa.Column("protocol_version", sa.String(length=64), nullable=True),
        sa.Column("generator_version", sa.String(length=64), nullable=True),
        sa.Column("profile_version", sa.String(length=64), nullable=True),
        sa.Column("validation_report", sa.JSON(), nullable=True),
        sa.Column("blocking_reasons", sa.JSON(), nullable=False),
        sa.Column("table_numbers", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["protocol_draft_id"], ["protocol_drafts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_documents_project_id", "generated_documents", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_generated_documents_project_id", table_name="generated_documents")
    op.drop_table("generated_documents")
