"""Upgrade databases that were initialized by the M0 empty bootstrap revision."""

from collections.abc import Sequence

from alembic import op
from app.db.models import Base

revision: str = "20260916_0002"
down_revision: str | None = "20260916_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only objects absent from a prior M0 database."""
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """M0 carried no domain schema, so it is safe to reverse this compatibility revision."""
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
