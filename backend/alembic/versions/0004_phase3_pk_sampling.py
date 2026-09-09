"""Phase 3 PK/Sampling engines.

Revision ID: 0004_phase3_pk_sampling
Revises: 0003_phase2_engines
Create Date: 2026-08-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_phase3_pk_sampling"
down_revision: Union[str, None] = "0003_phase2_engines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _prov():
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "analytes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("matrix", sa.String(length=128), nullable=True),
        sa.Column("assay_method", sa.String(length=255), nullable=True),
        sa.Column("lloq", sa.Float(), nullable=True),
        sa.Column("uloq", sa.Float(), nullable=True),
        sa.Column("tmax_min", sa.Float(), nullable=True),
        sa.Column("tmax_max", sa.Float(), nullable=True),
        sa.Column("tmax_unit", sa.String(length=16), nullable=False),
        sa.Column("half_life_min", sa.Float(), nullable=True),
        sa.Column("half_life_max", sa.Float(), nullable=True),
        sa.Column("half_life_unit", sa.String(length=16), nullable=False),
        sa.Column("pk_parameter_codes", sa.JSON(), nullable=False),
        *_prov(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytes_project_id", "analytes", ["project_id"])

    op.create_table(
        "pk_parameters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("analyte_id", sa.Uuid(), nullable=False),
        sa.Column("parameter_code", sa.String(length=64), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("range_min", sa.Float(), nullable=True),
        sa.Column("range_max", sa.Float(), nullable=True),
        sa.Column("calculated_value", sa.Float(), nullable=True),
        sa.Column("reference_text", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        *_prov(),
        sa.ForeignKeyConstraint(["analyte_id"], ["analytes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pk_parameters_project_id", "pk_parameters", ["project_id"])
    op.create_index("ix_pk_parameters_analyte_id", "pk_parameters", ["analyte_id"])

    op.create_table(
        "washout_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("calculated_minimum", sa.Float(), nullable=True),
        sa.Column("selected_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=True),
        sa.Column("rule_ids", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("manual_override", sa.Boolean(), nullable=False),
        sa.Column("requires_washout", sa.Boolean(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        *_prov(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_washout_plans_project_id"),
    )

    op.create_table(
        "observation_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("calculated_minimum", sa.Float(), nullable=True),
        sa.Column("selected_duration", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("final_sampling_time", sa.Float(), nullable=True),
        sa.Column("rule_id", sa.String(length=128), nullable=True),
        sa.Column("rule_ids", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("manual_override", sa.Boolean(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        *_prov(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_observation_plans_project_id"),
    )

    op.create_table(
        "sampling_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("design_id", sa.Uuid(), nullable=True),
        sa.Column("total_points_per_period", sa.Integer(), nullable=True),
        sa.Column("final_observation_h", sa.Float(), nullable=True),
        sa.Column("manual_override", sa.Boolean(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("rule_ids", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("validation_issues", sa.JSON(), nullable=False),
        *_prov(),
        sa.ForeignKeyConstraint(["design_id"], ["designs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_sampling_plans_project_id"),
    )

    op.create_table(
        "sampling_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sampling_plan_id", sa.Uuid(), nullable=False),
        sa.Column("time_h", sa.Float(), nullable=False),
        sa.Column("time_min", sa.Float(), nullable=False),
        sa.Column("window_before_min", sa.Float(), nullable=True),
        sa.Column("window_after_min", sa.Float(), nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("analyte_ids", sa.JSON(), nullable=False),
        *_prov(),
        sa.ForeignKeyConstraint(["sampling_plan_id"], ["sampling_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sampling_points_sampling_plan_id", "sampling_points", ["sampling_plan_id"])

    op.create_table(
        "blood_volume_calculations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("subjects", sa.Integer(), nullable=False),
        sa.Column("periods", sa.Integer(), nullable=False),
        sa.Column("sampling_points_per_period", sa.Integer(), nullable=False),
        sa.Column("blood_volume_per_pk_sample_ml", sa.Float(), nullable=False),
        sa.Column("screening_volume_ml", sa.Float(), nullable=False),
        sa.Column("safety_laboratory_volume_ml", sa.Float(), nullable=False),
        sa.Column("other_blood_volume_ml", sa.Float(), nullable=False),
        sa.Column("reserve_duplicate_factor", sa.Float(), nullable=False),
        sa.Column("pk_volume_ml", sa.Float(), nullable=False),
        sa.Column("screening_total_ml", sa.Float(), nullable=False),
        sa.Column("safety_total_ml", sa.Float(), nullable=False),
        sa.Column("other_total_ml", sa.Float(), nullable=False),
        sa.Column("total_volume_ml", sa.Float(), nullable=False),
        sa.Column("volume_per_subject_ml", sa.Float(), nullable=False),
        sa.Column("volume_per_period_ml", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("sample_count", sa.JSON(), nullable=False),
        *_prov(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_blood_volume_calculations_project_id"),
    )


def downgrade() -> None:
    op.drop_table("blood_volume_calculations")
    op.drop_index("ix_sampling_points_sampling_plan_id", table_name="sampling_points")
    op.drop_table("sampling_points")
    op.drop_table("sampling_plans")
    op.drop_table("observation_plans")
    op.drop_table("washout_plans")
    op.drop_index("ix_pk_parameters_analyte_id", table_name="pk_parameters")
    op.drop_index("ix_pk_parameters_project_id", table_name="pk_parameters")
    op.drop_table("pk_parameters")
    op.drop_index("ix_analytes_project_id", table_name="analytes")
    op.drop_table("analytes")
