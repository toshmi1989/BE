"""Phase 11C administrative entities — Person, StudyAdministration.

Revision ID: 0011_phase11c_admin
Revises: 0010_phase9_docx
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_phase11c_admin"
down_revision: Union[str, None] = "0010_phase9_docx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROVENANCE = [
    sa.Column("entity_version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("origin", sa.String(length=32), nullable=False),
    sa.Column("confidence", sa.Float(), nullable=True),
    sa.Column("source_ids", sa.JSON(), nullable=False),
    sa.Column("extraction_method", sa.String(length=64), nullable=True),
    sa.Column("page_ref", sa.String(length=64), nullable=True),
    sa.Column("section_ref", sa.String(length=128), nullable=True),
    sa.Column("verified_by", sa.String(length=255), nullable=True),
    sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
]


def upgrade() -> None:
    op.create_table(
        "persons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        *_PROVENANCE,
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_persons_project_id", "persons", ["project_id"])

    op.create_table(
        "study_administration",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("insurance_provider", sa.String(length=255), nullable=True),
        sa.Column("insurance_policy", sa.String(length=255), nullable=True),
        sa.Column("insurance_details", sa.Text(), nullable=True),
        sa.Column("financing_source", sa.String(length=255), nullable=True),
        sa.Column("financing_details", sa.Text(), nullable=True),
        sa.Column("publication_policy", sa.Text(), nullable=True),
        sa.Column("publication_contacts", sa.Text(), nullable=True),
        *_PROVENANCE,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_study_administration_project_id"),
    )


def downgrade() -> None:
    op.drop_table("study_administration")
    op.drop_index("ix_persons_project_id", table_name="persons")
    op.drop_table("persons")
