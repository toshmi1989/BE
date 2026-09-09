"""Phase 17.5 — multi-worker consistency columns.

Revision ID: 0015_phase17_5_consistency
Revises: 0014_phase17_workspace
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_phase17_5_consistency"
down_revision: Union[str, None] = "0014_phase17_workspace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("workspace_studies") as batch:
        batch.add_column(sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"))

    with op.batch_alter_table("workspace_snapshots") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch.create_index("ix_workspace_snapshots_idempotency_key", ["idempotency_key"])

    with op.batch_alter_table("workspace_workflow_runs") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch.create_index("ix_workspace_workflow_runs_idempotency_key", ["idempotency_key"])


def downgrade() -> None:
    with op.batch_alter_table("workspace_workflow_runs") as batch:
        batch.drop_index("ix_workspace_workflow_runs_idempotency_key")
        batch.drop_column("idempotency_key")
    with op.batch_alter_table("workspace_snapshots") as batch:
        batch.drop_index("ix_workspace_snapshots_idempotency_key")
        batch.drop_column("idempotency_key")
    with op.batch_alter_table("workspace_studies") as batch:
        batch.drop_column("state_version")
