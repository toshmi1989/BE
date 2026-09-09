"""Phase 4 Statistics / CV / Sample size.

Revision ID: 0005_phase4_statistics
Revises: 0004_phase3_pk_sampling
Create Date: 2026-08-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_phase4_statistics"
down_revision: Union[str, None] = "0004_phase3_pk_sampling"
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
        "cv_studies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("study_name", sa.String(length=255), nullable=True),
        sa.Column("publication_title", sa.String(length=512), nullable=True),
        sa.Column("analyte_id", sa.Uuid(), nullable=False),
        sa.Column("parameter", sa.String(length=64), nullable=False),
        sa.Column("design", sa.String(length=64), nullable=True),
        sa.Column("condition", sa.String(length=64), nullable=True),
        sa.Column("dose", sa.String(length=128), nullable=True),
        sa.Column("n_total", sa.Integer(), nullable=True),
        sa.Column("n_be_analysis", sa.Integer(), nullable=True),
        sa.Column("cv_value", sa.Float(), nullable=False),
        sa.Column("cv_unit", sa.String(length=32), nullable=False),
        sa.Column("cv_type", sa.String(length=64), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        *_prov(),
        sa.ForeignKeyConstraint(["analyte_id"], ["analytes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cv_studies_project_id", "cv_studies", ["project_id"])
    op.create_index("ix_cv_studies_analyte_id", "cv_studies", ["analyte_id"])

    op.create_table(
        "cv_pools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=128), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("pooled_cv", sa.Float(), nullable=True),
        sa.Column("confidence_interval", sa.JSON(), nullable=True),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("cv_study_ids", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("mismatches", sa.JSON(), nullable=False),
        sa.Column("parameter", sa.String(length=64), nullable=True),
        *_prov(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cv_pools_project_id", "cv_pools", ["project_id"])

    op.create_table(
        "cv_selections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("selected_cv", sa.Float(), nullable=True),
        sa.Column("cv_unit", sa.String(length=32), nullable=False),
        sa.Column("selection_method", sa.String(length=64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("source_study_ids", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("parameter", sa.String(length=64), nullable=True),
        sa.Column("analyte_id", sa.String(length=64), nullable=True),
        *_prov(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_cv_selections_project_id"),
    )

    op.create_table(
        "statistical_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("power", sa.Float(), nullable=False),
        sa.Column("be_lower", sa.Float(), nullable=False),
        sa.Column("be_upper", sa.Float(), nullable=False),
        sa.Column("expected_ratio", sa.Float(), nullable=False),
        sa.Column("analysis_method", sa.String(length=128), nullable=False),
        sa.Column("transformation", sa.String(length=64), nullable=False),
        sa.Column("software", sa.String(length=128), nullable=True),
        sa.Column("algorithm_version", sa.String(length=64), nullable=True),
        sa.Column("rule_id", sa.String(length=128), nullable=True),
        sa.Column("defaults_source", sa.Text(), nullable=True),
        *_prov(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_statistical_configs_project_id"),
    )

    op.create_table(
        "sample_size_calculations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("design_type", sa.String(length=64), nullable=False),
        sa.Column("selected_cv", sa.Float(), nullable=True),
        sa.Column("parameter", sa.String(length=64), nullable=True),
        sa.Column("evaluable_n", sa.Integer(), nullable=True),
        sa.Column("randomized_n", sa.Integer(), nullable=True),
        sa.Column("screened_n", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(length=128), nullable=False),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("software_version", sa.String(length=128), nullable=True),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("achieved_power", sa.Float(), nullable=True),
        sa.Column("inputs_snapshot", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("reserve_formula", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        *_prov(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sample_size_calculations_project_id", "sample_size_calculations", ["project_id"]
    )

    op.create_table(
        "subject_reserve_calculations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("sample_size_calculation_id", sa.Uuid(), nullable=True),
        sa.Column("evaluable_n", sa.Integer(), nullable=False),
        sa.Column("dropout_pct", sa.Float(), nullable=False),
        sa.Column("reserve_pct", sa.Float(), nullable=False),
        sa.Column("screen_failure_pct", sa.Float(), nullable=False),
        sa.Column("randomized_n", sa.Integer(), nullable=False),
        sa.Column("screened_n", sa.Integer(), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("rounding_rule_id", sa.String(length=128), nullable=False),
        *_prov(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["sample_size_calculation_id"],
            ["sample_size_calculations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subject_reserve_calculations_project_id",
        "subject_reserve_calculations",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_subject_reserve_calculations_project_id", table_name="subject_reserve_calculations")
    op.drop_table("subject_reserve_calculations")
    op.drop_index("ix_sample_size_calculations_project_id", table_name="sample_size_calculations")
    op.drop_table("sample_size_calculations")
    op.drop_table("statistical_configs")
    op.drop_table("cv_selections")
    op.drop_index("ix_cv_pools_project_id", table_name="cv_pools")
    op.drop_table("cv_pools")
    op.drop_index("ix_cv_studies_analyte_id", table_name="cv_studies")
    op.drop_index("ix_cv_studies_project_id", table_name="cv_studies")
    op.drop_table("cv_studies")
