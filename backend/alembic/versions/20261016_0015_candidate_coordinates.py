"""Keep candidate coordinates for map previews.

Revision ID: 20261016_0015
Revises: 20260929_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261016_0015"
down_revision: str | None = "20260929_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dvizh_candidates", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("dvizh_candidates", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("dvizh_candidates", "longitude")
    op.drop_column("dvizh_candidates", "latitude")
