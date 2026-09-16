"""Record the initial technical bootstrap revision.

Revision ID: 20260916_0001
Revises:
Create Date: 2026-09-16 00:00:00
"""

from collections.abc import Sequence

revision: str = "20260916_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reserve the migration lineage before domain tables are introduced."""
    pass


def downgrade() -> None:
    """The bootstrap revision contains no schema objects."""
    pass
