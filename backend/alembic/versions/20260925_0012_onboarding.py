"""Remember first display of the introduction per MAX user.

Revision ID: 20260925_0012
Revises: 20260924_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0012"
down_revision: str | None = "20260924_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("onboarding_seen_at", sa.DateTime(timezone=True)))
    # Accounts that existed before this rollout have already entered the app.
    op.execute("UPDATE users SET onboarding_seen_at = CURRENT_TIMESTAMP")


def downgrade() -> None:
    op.drop_column("users", "onboarding_seen_at")
