"""Record the initial technical bootstrap revision.

Revision ID: 20260916_0001
Revises:
Create Date: 2026-09-16 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260916_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the modular-monolith MVP schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("max_user_id", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_max_user_id", "users", ["max_user_id"])
    op.create_table(
        "groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("max_chat_id", sa.String(64), unique=True),
        sa.Column("default_city_slug", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invite_token", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id",
            sa.String(36),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("group_id", "user_id"),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"])
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])
    op.create_table(
        "locations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("city_slug", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("is_ephemeral", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_locations_user_id", "locations", ["user_id"])
    op.create_table(
        "intents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "group_id",
            sa.String(36),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120)),
        sa.Column("city_slug", sa.String(64), nullable=False),
        sa.Column("activity_category", sa.String(64), nullable=False),
        sa.Column("available_from", sa.DateTime(timezone=True)),
        sa.Column("available_to", sa.DateTime(timezone=True)),
        sa.Column("recurrence_json", sa.JSON()),
        sa.Column("budget_max", sa.Integer(), nullable=False),
        sa.Column(
            "origin_location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=False
        ),
        sa.Column("radius_km", sa.Float(), nullable=False),
        sa.Column("min_people", sa.Integer(), nullable=False),
        sa.Column("max_people", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_intents_group_active_city", "intents", ["group_id", "status", "city_slug"])
    op.create_index("ix_intents_user_id", "intents", ["user_id"])
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
        sa.Column("is_free", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("image_url", sa.Text()),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("raw_metadata", sa.JSON()),
        sa.UniqueConstraint("provider", "provider_id"),
    )
    op.create_index("ix_leisure_city_start", "leisure_items", ["city_slug", "starts_at"])
    op.create_table(
        "candidate_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "group_id",
            sa.String(36),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "leisure_item_id", sa.String(36), sa.ForeignKey("leisure_items.id"), nullable=False
        ),
        sa.Column("city_slug", sa.String(64), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_price_min", sa.Integer()),
        sa.Column("required_min_people", sa.Integer(), nullable=False),
        sa.Column("required_max_people", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_candidate_group_status_start", "candidate_plans", ["group_id", "status", "starts_at"]
    )
    op.create_table(
        "candidate_plan_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_plan_id",
            sa.String(36),
            sa.ForeignKey("candidate_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("intent_id", sa.String(36), sa.ForeignKey("intents.id"), nullable=False),
        sa.Column("compatibility", sa.String(20), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("budget_delta", sa.Integer()),
        sa.Column("deviations_json", sa.JSON()),
        sa.Column("considered_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("candidate_plan_id", "user_id"),
    )
    op.create_table(
        "offers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_plan_id",
            sa.String(36),
            sa.ForeignKey("candidate_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_near", sa.Boolean(), nullable=False),
        sa.Column("exception_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("candidate_plan_id", "user_id"),
    )
    op.create_index("ix_offers_user_status", "offers", ["user_id", "status"])
    op.create_table(
        "provider_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("city_slug", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "city_slug"),
    )
    op.create_table(
        "outbox_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    """Drop MVP data in reverse dependency order."""
    for table in (
        "outbox_notifications",
        "provider_snapshots",
        "offers",
        "candidate_plan_members",
        "candidate_plans",
        "leisure_items",
        "intents",
        "locations",
        "group_members",
        "groups",
        "users",
    ):
        op.drop_table(table)
