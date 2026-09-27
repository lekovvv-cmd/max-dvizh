"""Persist missing event times without inventing historical measurements.

Revision ID: 20260927_0013
Revises: 20260925_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0013"
down_revision: str | None = "20260925_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dvizh_sessions", sa.Column("launched_at", sa.DateTime(timezone=True)))
    op.add_column("outbox_notifications", sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.add_column("dvizh_confirmations", sa.Column("confirmed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("dvizh_confirmations", "confirmed_at")
    op.drop_column("outbox_notifications", "sent_at")
    op.drop_column("dvizh_sessions", "launched_at")
