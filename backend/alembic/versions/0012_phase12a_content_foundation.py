"""Phase 12A content foundation — ProcedureSchedule, Bioanalysis, Safety, ExpertRule.

Revision ID: 0012_phase12a_content_foundation
Revises: 0011_phase11c_admin
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_phase12a_content_foundation"
down_revision: Union[str, None] = "0011_phase11c_admin"
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
        "procedure_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("dependency_trace", sa.JSON(), nullable=False),
        sa.Column("composition_notes", sa.Text(), nullable=True),
        *_PROVENANCE,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_procedure_schedules_project_id"),
    )

    op.create_table(
        "procedure_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("period", sa.Integer(), nullable=True),
        sa.Column("relative_time_min", sa.Float(), nullable=True),
        sa.Column("duration_min", sa.Float(), nullable=True),
        sa.Column("sequence_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("condition", sa.String(length=255), nullable=True),
        sa.Column("rule_ids", sa.JSON(), nullable=False),
        *_PROVENANCE,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_id"], ["procedure_schedules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "code", name="uq_procedure_definitions_project_code"),
    )
    op.create_index("ix_procedure_definitions_project_id", "procedure_definitions", ["project_id"])

    op.create_table(
        "bioanalysis_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("matrix", sa.String(length=128), nullable=True),
        sa.Column("tube_type", sa.String(length=128), nullable=True),
        sa.Column("anticoagulant", sa.String(length=128), nullable=True),
        sa.Column("sample_volume_ml", sa.Float(), nullable=True),
        sa.Column("centrifugation", sa.String(length=255), nullable=True),
        sa.Column("centrifugation_temperature", sa.String(length=64), nullable=True),
        sa.Column("centrifugation_time", sa.String(length=64), nullable=True),
        sa.Column("aliquot_count", sa.Integer(), nullable=True),
        sa.Column("aliquot_volume_ml", sa.Float(), nullable=True),
        sa.Column("storage_temperature", sa.String(length=64), nullable=True),
        sa.Column("storage_duration", sa.String(length=64), nullable=True),
        sa.Column("shipment_conditions", sa.Text(), nullable=True),
        sa.Column("analytical_method", sa.Text(), nullable=True),
        sa.Column("sample_preparation", sa.Text(), nullable=True),
        sa.Column("internal_standard", sa.String(length=255), nullable=True),
        sa.Column("calibration_range", sa.String(length=255), nullable=True),
        sa.Column("lloq", sa.String(length=128), nullable=True),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.String(length=64), nullable=True),
        sa.Column("field_sources", sa.JSON(), nullable=False),
        *_PROVENANCE,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_bioanalysis_plans_project_id"),
    )

    op.create_table(
        "safety_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("physical_exam", sa.JSON(), nullable=True),
        sa.Column("vital_signs", sa.JSON(), nullable=True),
        sa.Column("ECG", sa.JSON(), nullable=True),
        sa.Column("laboratory_tests", sa.JSON(), nullable=True),
        sa.Column("AE", sa.JSON(), nullable=True),
        sa.Column("SAE", sa.JSON(), nullable=True),
        sa.Column("pregnancy", sa.JSON(), nullable=True),
        sa.Column("follow_up", sa.JSON(), nullable=True),
        sa.Column("safety_periods", sa.JSON(), nullable=False),
        sa.Column("static_verified_refs", sa.JSON(), nullable=False),
        *_PROVENANCE,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_safety_plans_project_id"),
    )

    op.create_table(
        "expert_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("applies_to", sa.JSON(), nullable=False),
        sa.Column("expression", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=512), nullable=True),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1"),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("entity_version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expert_rules_project_id", "expert_rules", ["project_id"])
    op.create_index("ix_expert_rules_rule_id", "expert_rules", ["rule_id"])


def downgrade() -> None:
    op.drop_index("ix_expert_rules_rule_id", table_name="expert_rules")
    op.drop_index("ix_expert_rules_project_id", table_name="expert_rules")
    op.drop_table("expert_rules")
    op.drop_table("safety_plans")
    op.drop_table("bioanalysis_plans")
    op.drop_index("ix_procedure_definitions_project_id", table_name="procedure_definitions")
    op.drop_table("procedure_definitions")
    op.drop_table("procedure_schedules")
