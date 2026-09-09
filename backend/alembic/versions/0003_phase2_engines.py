"""Phase 2 domain engines: Design, Food, Eligibility, Subjects, ClientInput.

Revision ID: 0003_phase2_engines
Revises: 0002_phase1_domain
Create Date: 2026-08-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_phase2_engines"
down_revision: Union[str, None] = "0002_phase1_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _provenance_cols():
    return [
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
        "client_inputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("requested_product_name", sa.String(length=255), nullable=True),
        sa.Column("inn", sa.String(length=255), nullable=True),
        sa.Column("dosage", sa.String(length=128), nullable=True),
        sa.Column("dosage_form", sa.String(length=128), nullable=True),
        sa.Column("route", sa.String(length=128), nullable=True),
        sa.Column("requested_subject_count", sa.Integer(), nullable=True),
        *_provenance_cols(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_client_inputs_project_id"),
    )

    op.create_table(
        "designs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("periods", sa.Integer(), nullable=True),
        sa.Column("sequences", sa.JSON(), nullable=False),
        sa.Column("treatments", sa.JSON(), nullable=False),
        sa.Column("randomization", sa.Boolean(), nullable=True),
        sa.Column("blinding", sa.Boolean(), nullable=True),
        sa.Column("food_condition", sa.String(length=32), nullable=True),
        sa.Column("stage_configuration", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("decision_status", sa.String(length=32), nullable=False),
        sa.Column("recommendation_confidence", sa.Float(), nullable=True),
        *_provenance_cols(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_designs_project_id"),
    )

    op.create_table(
        "food_conditions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("condition", sa.String(length=32), nullable=False),
        sa.Column("meal_type", sa.String(length=32), nullable=True),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("fat_percent", sa.Float(), nullable=True),
        sa.Column("composition", sa.JSON(), nullable=False),
        sa.Column("meal_start_offset_min", sa.Integer(), nullable=True),
        sa.Column("dose_after_meal_min", sa.Integer(), nullable=True),
        sa.Column("water_volume_ml", sa.Integer(), nullable=True),
        sa.Column("decision_status", sa.String(length=32), nullable=False),
        *_provenance_cols(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_food_conditions_project_id"),
    )

    op.create_table(
        "eligibility_criteria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        *_provenance_cols(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "category",
            "number",
            name="uq_eligibility_project_category_number",
        ),
    )
    op.create_index("ix_eligibility_criteria_project_id", "eligibility_criteria", ["project_id"])

    op.create_table(
        "subject_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("target_evaluable_n", sa.Integer(), nullable=True),
        sa.Column("planned_randomized_n", sa.Integer(), nullable=True),
        sa.Column("reserve_n", sa.Integer(), nullable=True),
        sa.Column("planned_screened_n", sa.Integer(), nullable=True),
        *_provenance_cols(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_subject_plans_project_id"),
    )


def downgrade() -> None:
    op.drop_table("subject_plans")
    op.drop_index("ix_eligibility_criteria_project_id", table_name="eligibility_criteria")
    op.drop_table("eligibility_criteria")
    op.drop_table("food_conditions")
    op.drop_table("designs")
    op.drop_table("client_inputs")
