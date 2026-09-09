"""Phase 5 Validation Engine + Evidence Foundation.

Revision ID: 0006_phase5_validation_evidence
Revises: 0005_phase4_statistics
Create Date: 2026-08-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_phase5_validation_evidence"
down_revision: Union[str, None] = "0005_phase4_statistics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("field", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
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
    op.create_index("ix_validation_issues_project_id", "validation_issues", ["project_id"])

    op.create_table(
        "research_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("client_input_id", sa.Uuid(), nullable=True),
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
        sa.UniqueConstraint("project_id", name="uq_research_cases_project_id"),
    )

    op.create_table(
        "research_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_case_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("query_profile", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["research_case_id"], ["research_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_tasks_research_case_id", "research_tasks", ["research_case_id"])

    op.create_table(
        "evidences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_case_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("claim", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("page", sa.String(length=64), nullable=True),
        sa.Column("section", sa.String(length=128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(["research_case_id"], ["research_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidences_research_case_id", "evidences", ["research_case_id"])

    op.create_table(
        "evidence_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("normalized_value", sa.JSON(), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_claims_evidence_id", "evidence_claims", ["evidence_id"])

    op.create_table(
        "evidence_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_case_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(length=255), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["research_case_id"], ["research_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evidence_conflicts_research_case_id", "evidence_conflicts", ["research_case_id"]
    )

    op.create_table(
        "source_ranking_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("source_ranking_configs")
    op.drop_index("ix_evidence_conflicts_research_case_id", table_name="evidence_conflicts")
    op.drop_table("evidence_conflicts")
    op.drop_index("ix_evidence_claims_evidence_id", table_name="evidence_claims")
    op.drop_table("evidence_claims")
    op.drop_index("ix_evidences_research_case_id", table_name="evidences")
    op.drop_table("evidences")
    op.drop_index("ix_research_tasks_research_case_id", table_name="research_tasks")
    op.drop_table("research_tasks")
    op.drop_table("research_cases")
    op.drop_index("ix_validation_issues_project_id", table_name="validation_issues")
    op.drop_table("validation_issues")
