"""Persist the last provider result for honest active Signal empty states.

Revision ID: 20260918_0008
Revises: 20260918_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260918_0008"
down_revision: str | None = "20260918_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "intents",
        sa.Column("provider_state", sa.String(24), server_default="NOT_CHECKED", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("intents", "provider_state")
