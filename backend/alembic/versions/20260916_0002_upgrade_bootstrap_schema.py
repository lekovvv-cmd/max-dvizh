"""Upgrade databases that were initialized by the M0 empty bootstrap revision."""

from collections.abc import Sequence

from alembic import op
from app.db.models import Base

# This revision predates later domain tables. Importing the current ORM
# metadata must not create tables owned by future revisions on a fresh DB.
BOOTSTRAP_TABLES = (
    "users",
    "groups",
    "group_members",
    "locations",
    "intents",
    "candidate_plans",
    "candidate_plan_members",
    "offers",
    "provider_snapshots",
    "outbox_notifications",
)


def bootstrap_tables():
    return [Base.metadata.tables[name] for name in BOOTSTRAP_TABLES if name in Base.metadata.tables]


revision: str = "20260916_0002"
down_revision: str | None = "20260916_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only objects absent from a prior M0 database."""
    Base.metadata.create_all(bind=op.get_bind(), tables=bootstrap_tables(), checkfirst=True)


def downgrade() -> None:
    """M0 carried no domain schema, so it is safe to reverse this compatibility revision."""
    Base.metadata.drop_all(bind=op.get_bind(), tables=bootstrap_tables(), checkfirst=True)
