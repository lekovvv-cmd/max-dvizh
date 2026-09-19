"""Add non-destructive product fields for batches, open plans and waitlists.

Revision ID: 20260918_0006
Revises: 20260916_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260918_0006"
down_revision: str | None = "20260916_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("address_text", sa.String(250), nullable=True))
    op.add_column("intents", sa.Column("activity_categories", sa.JSON(), nullable=True))
    op.add_column("intents", sa.Column("signal_batch_id", sa.String(36), nullable=True))
    op.create_index("ix_intents_signal_batch_id", "intents", ["signal_batch_id"])
    op.alter_column("intents", "max_people", existing_type=sa.Integer(), nullable=True)
    op.add_column("offers", sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE intents SET activity_categories = json_build_array(activity_category) WHERE activity_categories IS NULL"
    )


def downgrade() -> None:
    op.execute("UPDATE intents SET max_people = 12 WHERE max_people IS NULL")
    op.alter_column("intents", "max_people", existing_type=sa.Integer(), nullable=False)
    op.drop_column("offers", "responded_at")
    op.drop_index("ix_intents_signal_batch_id", table_name="intents")
    op.drop_column("intents", "signal_batch_id")
    op.drop_column("intents", "activity_categories")
    op.drop_column("locations", "address_text")
