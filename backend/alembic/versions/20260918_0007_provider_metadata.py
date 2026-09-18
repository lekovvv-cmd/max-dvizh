"""Persist company timezone and materialized place/price metadata.

Revision ID: 20260918_0007
Revises: 20260918_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260918_0007"
down_revision: str | None = "20260918_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("groups", sa.Column("timezone_name", sa.String(64), nullable=True))
    # Revision 0002 creates tables absent from the old bootstrap using current
    # metadata. On a fresh database the snapshot may already have this column.
    snapshot_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("candidate_plan_source_snapshots")}
    if "source_metadata" not in snapshot_columns:
        op.add_column("candidate_plan_source_snapshots", sa.Column("source_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate_plan_source_snapshots", "source_metadata")
    op.drop_column("groups", "timezone_name")
