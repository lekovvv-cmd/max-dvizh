"""Move provider catalogue storage from PostgreSQL to Redis-backed DTO cache.

Existing CandidatePlans keep exactly one copied provider snapshot. Development
databases may instead be reset (`docker compose down -v`) when legacy data is
not valuable; production-like upgrades preserve active plan facts.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260916_0003"
down_revision: str | None = "20260916_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "candidate_plan_source_snapshots" not in tables:
        op.create_table(
            "candidate_plan_source_snapshots",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "candidate_plan_id",
                sa.String(36),
                sa.ForeignKey("candidate_plans.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("provider", sa.String(40), nullable=False),
            sa.Column("provider_item_id", sa.String(100), nullable=False),
            sa.Column("provider_item_type", sa.String(20), nullable=False),
            sa.Column("title", sa.String(250), nullable=False),
            sa.Column("category", sa.String(64), nullable=False),
            sa.Column("venue_name", sa.String(250)),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("latitude", sa.Float()),
            sa.Column("longitude", sa.Float()),
            sa.Column("price_text", sa.String(250)),
            sa.Column("parsed_price", sa.Integer()),
            sa.Column("source_url", sa.Text()),
            sa.Column("image_url", sa.Text()),
            sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index(
            "ix_candidate_plan_source_snapshots_candidate_plan_id",
            "candidate_plan_source_snapshots",
            ["candidate_plan_id"],
        )

    if "leisure_items" not in tables:
        return

    op.execute(
        """
        INSERT INTO candidate_plan_source_snapshots
          (id, candidate_plan_id, provider, provider_item_id, provider_item_type,
           title, category, venue_name, starts_at, ends_at, latitude, longitude,
           price_text, parsed_price, source_url, image_url, source_fetched_at, is_demo)
        SELECT cp.id, cp.id, li.provider, li.provider_id, li.item_type,
               li.title, li.category, li.venue_name, li.starts_at, li.ends_at, li.latitude,
               li.longitude, li.price_text, li.price_min, li.source_url, li.image_url,
               li.source_fetched_at, li.is_demo
        FROM candidate_plans cp JOIN leisure_items li ON li.id = cp.leisure_item_id
        ON CONFLICT (candidate_plan_id) DO NOTHING
        """
    )
    op.drop_constraint(
        "candidate_plans_leisure_item_id_fkey", "candidate_plans", type_="foreignkey"
    )
    op.drop_column("candidate_plans", "leisure_item_id")
    if "provider_snapshots" in tables:
        op.drop_table("provider_snapshots")
    op.drop_index("ix_leisure_city_start", table_name="leisure_items")
    op.drop_table("leisure_items")


def downgrade() -> None:
    # Restore a minimal legacy catalogue from per-plan snapshots. It is only for
    # migration reversibility; the application never reads this table after upgrade.
    if "leisure_items" in _tables():
        return
    op.create_table(
        "leisure_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_id", sa.String(100), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("city_slug", sa.String(64), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("venue_name", sa.String(250)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_text", sa.String(250)),
        sa.Column("price_min", sa.Integer()),
        sa.Column("is_free", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_url", sa.Text()),
        sa.Column("image_url", sa.Text()),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("raw_metadata", sa.JSON()),
        sa.UniqueConstraint("provider", "provider_id"),
    )
    op.create_index("ix_leisure_city_start", "leisure_items", ["city_slug", "starts_at"])
    op.add_column("candidate_plans", sa.Column("leisure_item_id", sa.String(36), nullable=True))
    op.execute(
        """
        INSERT INTO leisure_items
          (id, provider, provider_id, item_type, city_slug, title, category, venue_name,
           latitude, longitude, starts_at, ends_at, price_text, price_min, is_free,
           source_url, image_url, source_fetched_at, is_demo)
        SELECT DISTINCT ON (provider, provider_item_id) candidate_plan_id, provider, provider_item_id,
               provider_item_type, cp.city_slug, title, category, venue_name, latitude, longitude,
               starts_at, ends_at, price_text, parsed_price, parsed_price = 0, source_url,
               image_url, source_fetched_at, is_demo
        FROM candidate_plan_source_snapshots snap JOIN candidate_plans cp ON cp.id = snap.candidate_plan_id
        """
    )
    op.execute(
        """
        UPDATE candidate_plans cp SET leisure_item_id = li.id
        FROM candidate_plan_source_snapshots snap JOIN leisure_items li
          ON li.provider = snap.provider AND li.provider_id = snap.provider_item_id
        WHERE snap.candidate_plan_id = cp.id
        """
    )
    op.alter_column("candidate_plans", "leisure_item_id", nullable=False)
    op.create_foreign_key(
        "candidate_plans_leisure_item_id_fkey",
        "candidate_plans",
        "leisure_items",
        ["leisure_item_id"],
        ["id"],
    )
    op.create_table(
        "provider_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("city_slug", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "city_slug"),
    )
    op.drop_table("candidate_plan_source_snapshots")
