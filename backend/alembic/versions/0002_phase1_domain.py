"""Initial Phase 1 domain schema.

Revision ID: 0002_phase1_domain
Revises: 0001_initial
Create Date: 2026-08-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase1_domain"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Expand projects
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("entity_version", sa.Integer(), nullable=False, server_default="1"))

    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_project_id", "organizations", ["project_id"])

    op.create_table(
        "sponsors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_sponsors_project_id"),
    )

    op.create_table(
        "studies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("sponsor_id", sa.Uuid(), nullable=True),
        sa.Column("protocol_number", sa.String(length=128), nullable=True),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("version_date", sa.String(length=32), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("short_title", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("phase", sa.String(length=64), nullable=False),
        sa.Column("study_status", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sponsor_id"], ["sponsors.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_studies_project_id"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("inn", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("manufacturer_country", sa.String(length=128), nullable=True),
        sa.Column("registration_holder", sa.String(length=255), nullable=True),
        sa.Column("registration_number", sa.String(length=128), nullable=True),
        sa.Column("dosage", sa.String(length=128), nullable=True),
        sa.Column("dosage_form", sa.String(length=128), nullable=True),
        sa.Column("route", sa.String(length=128), nullable=True),
        sa.Column("pharmacological_group", sa.String(length=255), nullable=True),
        sa.Column("composition", sa.JSON(), nullable=False),
        sa.Column("storage_conditions", sa.Text(), nullable=True),
        sa.Column("shelf_life", sa.String(length=128), nullable=True),
        sa.Column("batch_number", sa.String(length=128), nullable=True),
        sa.Column("packaging", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_products_project_id"),
    )

    op.create_table(
        "reference_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("inn", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("registration_holder", sa.String(length=255), nullable=True),
        sa.Column("registration_number", sa.String(length=128), nullable=True),
        sa.Column("dosage", sa.String(length=128), nullable=True),
        sa.Column("dosage_form", sa.String(length=128), nullable=True),
        sa.Column("route", sa.String(length=128), nullable=True),
        sa.Column("composition", sa.JSON(), nullable=False),
        sa.Column("storage_conditions", sa.Text(), nullable=True),
        sa.Column("shelf_life", sa.String(length=128), nullable=True),
        sa.Column("registration_status", sa.String(length=128), nullable=True),
        sa.Column("purchased_status", sa.String(length=32), nullable=False),
        sa.Column("batch_number", sa.String(length=128), nullable=True),
        sa.Column("packaging", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_reference_products_project_id"),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("file_id", sa.String(length=255), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_project_id", "sources", ["project_id"])

    op.create_table(
        "project_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("ruleset_version", sa.String(length=32), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_project_versions_number"),
    )
    op.create_index("ix_project_versions_project_id", "project_versions", ["project_id"])


def downgrade() -> None:
    op.drop_table("project_versions")
    op.drop_table("sources")
    op.drop_table("reference_products")
    op.drop_table("products")
    op.drop_table("studies")
    op.drop_table("sponsors")
    op.drop_table("organizations")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("entity_version")
        batch.drop_column("description")
