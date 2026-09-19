"""Represent expired invitations without imposing an undocumented default TTL.

Revision ID: 20260918_0009
Revises: 20260918_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260918_0009"
down_revision: str | None = "20260918_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "groups", sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("groups", "invite_expires_at")
