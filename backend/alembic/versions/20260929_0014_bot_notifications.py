"""Store the pre-meeting prompt schedule and each participant's second answer.

Revision ID: 20260929_0014
Revises: 20260927_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260929_0014"
down_revision: str | None = "20260927_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dvizh_sessions", sa.Column("premeet_due_at", sa.DateTime(timezone=True)))
    op.add_column("dvizh_sessions", sa.Column("source_rechecked_at", sa.DateTime(timezone=True)))
    op.add_column("dvizh_confirmations", sa.Column("reconfirmed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("dvizh_confirmations", "reconfirmed_at")
    op.drop_column("dvizh_sessions", "source_rechecked_at")
    op.drop_column("dvizh_sessions", "premeet_due_at")
