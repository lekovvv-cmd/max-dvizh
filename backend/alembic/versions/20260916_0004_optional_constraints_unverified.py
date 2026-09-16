"""Make budget/radius constraints optional and support unverified matching facts."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260916_0004"
down_revision: str | None = "20260916_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("intents", "budget_max", nullable=True)
    op.alter_column("intents", "origin_location_id", nullable=True)
    op.alter_column("intents", "radius_km", nullable=True)
    op.alter_column("candidate_plan_members", "distance_km", nullable=True)


def downgrade() -> None:
    # Nullable records cannot be converted to hard constraints without inventing data.
    raise RuntimeError("Downgrade requires resetting optional-constraint development data")
