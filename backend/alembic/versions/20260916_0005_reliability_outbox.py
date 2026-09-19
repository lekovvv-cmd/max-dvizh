"""Add durable outbox claim/retry state for independent notification workers.

Revision ID: 20260916_0005
Revises: 20260916_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260916_0005"
down_revision: str | None = "20260916_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outbox_notifications", sa.Column("dedupe_key", sa.String(180), nullable=True))
    op.add_column(
        "outbox_notifications",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_notifications", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint(
        "uq_outbox_notifications_dedupe_key", "outbox_notifications", ["dedupe_key"]
    )
    op.create_index("ix_outbox_dispatch", "outbox_notifications", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_dispatch", table_name="outbox_notifications")
    op.drop_constraint("uq_outbox_notifications_dedupe_key", "outbox_notifications", type_="unique")
    op.drop_column("outbox_notifications", "locked_at")
    op.drop_column("outbox_notifications", "next_attempt_at")
    op.drop_column("outbox_notifications", "dedupe_key")
