"""Phase 28 — workspace integrity: global study_key + catalog fields.

Revision ID: 0016_phase28_workspace_integrity
Revises: 0015_phase17_5_consistency
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_phase28_workspace_integrity"
down_revision: Union[str, None] = "0015_phase17_5_consistency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("workspace_studies") as batch:
        batch.add_column(sa.Column("readiness_code", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("readiness_label", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"))
        batch.drop_constraint("uq_org_study_key", type_="unique")
        batch.create_unique_constraint("uq_workspace_study_key_global", ["study_key"])
        batch.create_index("ix_workspace_studies_lifecycle", ["lifecycle"])
        batch.create_index("ix_workspace_studies_readiness_code", ["readiness_code"])


def downgrade() -> None:
    with op.batch_alter_table("workspace_studies") as batch:
        batch.drop_index("ix_workspace_studies_readiness_code")
        batch.drop_index("ix_workspace_studies_lifecycle")
        batch.drop_constraint("uq_workspace_study_key_global", type_="unique")
        batch.create_unique_constraint("uq_org_study_key", ["organization_id", "study_key"])
        batch.drop_column("document_count")
        batch.drop_column("readiness_label")
        batch.drop_column("readiness_code")
