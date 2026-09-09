"""Phase 12A.1 expert knowledge foundation — rules, decisions, gaps, QA, diffs.

Revision ID: 0013_phase12a1_knowledge
Revises: 0012_phase12a_content_foundation
Create Date: 2026-09-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_phase12a1_knowledge"
down_revision: Union[str, None] = "0012_phase12a_content_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIMESTAMPS_VERSIONED = [
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
]

_TIMESTAMPS = [
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
        "regulatory_bases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("document_identifier", sa.String(length=255), nullable=True),
        sa.Column("section_reference", sa.String(length=255), nullable=True),
        sa.Column("page_reference", sa.String(length=64), nullable=True),
        sa.Column("paragraph_reference", sa.String(length=128), nullable=True),
        sa.Column("jurisdiction", sa.String(length=128), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PROPOSED"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_TIMESTAMPS_VERSIONED,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regulatory_bases_project_id", "regulatory_bases", ["project_id"])

    op.create_table(
        "knowledge_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("condition_expression", sa.Text(), nullable=True),
        sa.Column("action_definition", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PROPOSED"),
        sa.Column(
            "requires_expert_confirmation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("regulatory_basis_id", sa.Uuid(), nullable=True),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_claim_ids", sa.JSON(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1"),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        *_TIMESTAMPS_VERSIONED,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["regulatory_basis_id"], ["regulatory_bases.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_code", name="uq_knowledge_rules_rule_code"),
    )
    op.create_index("ix_knowledge_rules_project_id", "knowledge_rules", ["project_id"])
    op.create_index("ix_knowledge_rules_rule_code", "knowledge_rules", ["rule_code"])

    op.create_table(
        "expert_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=True),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("target_entity_type", sa.String(length=64), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_value", sa.JSON(), nullable=False),
        sa.Column("final_value", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PROPOSED"),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_claim_ids", sa.JSON(), nullable=False),
        sa.Column("regulatory_basis_ids", sa.JSON(), nullable=False),
        sa.Column("previous_decision_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1"),
        *_TIMESTAMPS_VERSIONED,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["study_id"], ["studies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["previous_decision_id"], ["expert_decisions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expert_decisions_project_id", "expert_decisions", ["project_id"])

    op.create_table(
        "knowledge_gaps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("question", sa.String(length=1024), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("importance", sa.String(length=32), nullable=False, server_default="MEDIUM"),
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("related_rule_id", sa.String(length=128), nullable=True),
        sa.Column("related_decision_type", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=255), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        *_TIMESTAMPS_VERSIONED,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_gaps_project_id", "knowledge_gaps", ["project_id"])

    op.create_table(
        "previous_protocol_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("previous_protocol_id", sa.String(length=128), nullable=True),
        sa.Column("comparison_version", sa.String(length=64), nullable=False, server_default="1"),
        sa.Column("compared_by", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        *_TIMESTAMPS_VERSIONED,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_previous_protocol_comparisons_project_id",
        "previous_protocol_comparisons",
        ["project_id"],
    )

    op.create_table(
        "protocol_diff_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comparison_id", sa.Uuid(), nullable=False),
        sa.Column("section", sa.String(length=128), nullable=False),
        sa.Column("table_key", sa.String(length=128), nullable=True),
        sa.Column("paragraph_or_field", sa.String(length=255), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=False),
        sa.Column("current_value", sa.Text(), nullable=False),
        sa.Column("diff_type", sa.String(length=64), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="OPEN"),
        *_TIMESTAMPS,
        sa.ForeignKeyConstraint(
            ["comparison_id"], ["previous_protocol_comparisons.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_protocol_diff_items_comparison_id", "protocol_diff_items", ["comparison_id"]
    )

    op.create_table(
        "protocol_qa_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("summary", sa.JSON(), nullable=False),
        *_TIMESTAMPS_VERSIONED,
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protocol_qa_runs_project_id", "protocol_qa_runs", ["project_id"])

    op.create_table(
        "protocol_qa_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("expected", sa.Text(), nullable=True),
        sa.Column("actual", sa.Text(), nullable=True),
        sa.Column("related_canonical_field", sa.String(length=255), nullable=True),
        sa.Column("related_source", sa.String(length=255), nullable=True),
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        *_TIMESTAMPS,
        sa.ForeignKeyConstraint(["run_id"], ["protocol_qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protocol_qa_findings_run_id", "protocol_qa_findings", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_protocol_qa_findings_run_id", table_name="protocol_qa_findings")
    op.drop_table("protocol_qa_findings")
    op.drop_index("ix_protocol_qa_runs_project_id", table_name="protocol_qa_runs")
    op.drop_table("protocol_qa_runs")
    op.drop_index("ix_protocol_diff_items_comparison_id", table_name="protocol_diff_items")
    op.drop_table("protocol_diff_items")
    op.drop_index(
        "ix_previous_protocol_comparisons_project_id",
        table_name="previous_protocol_comparisons",
    )
    op.drop_table("previous_protocol_comparisons")
    op.drop_index("ix_knowledge_gaps_project_id", table_name="knowledge_gaps")
    op.drop_table("knowledge_gaps")
    op.drop_index("ix_expert_decisions_project_id", table_name="expert_decisions")
    op.drop_table("expert_decisions")
    op.drop_index("ix_knowledge_rules_rule_code", table_name="knowledge_rules")
    op.drop_index("ix_knowledge_rules_project_id", table_name="knowledge_rules")
    op.drop_table("knowledge_rules")
    op.drop_index("ix_regulatory_bases_project_id", table_name="regulatory_bases")
    op.drop_table("regulatory_bases")
