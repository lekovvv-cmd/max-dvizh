"""Isolated Dvizh lifecycle; preserve legacy plans and durable company data.

Revision ID: 20260924_0011
Revises: 20260918_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260924_0011"
down_revision: str | None = "20260918_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "intents", sa.Column("flow_version", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_table(
        "dvizh_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "signal_id", sa.String(36), sa.ForeignKey("intents.id"), nullable=False, unique=True
        ),
        sa.Column(
            "group_id",
            sa.String(36),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("initiator_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("activity_ids", sa.JSON(), nullable=False),
        sa.Column("min_people", sa.Integer(), nullable=False),
        sa.Column("max_people", sa.Integer(), nullable=False),
        sa.Column("active_candidate_id", sa.String(36)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_dvizh_group_status", "dvizh_sessions", ["group_id", "status"])
    op.create_index("ix_dvizh_sessions_group_id", "dvizh_sessions", ["group_id"])
    op.create_table(
        "dvizh_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("dvizh_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_item_id", sa.String(100), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("activity_ids", sa.JSON(), nullable=False),
        sa.Column("venue_name", sa.String(250)),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_text", sa.String(250)),
        sa.Column("price_min", sa.Integer()),
        sa.Column("distance_km", sa.Float()),
        sa.Column("budget_delta", sa.Integer()),
        sa.Column("compatibility", sa.String(20), nullable=False),
        sa.Column("address_text", sa.String(250)),
        sa.Column("source_url", sa.Text()),
        sa.Column("image_url", sa.Text()),
        sa.Column("seed", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "provider", "provider_item_id", "starts_at"),
    )
    op.create_index("ix_dvizh_candidates_order", "dvizh_candidates", ["session_id", "position"])
    op.create_table(
        "dvizh_reactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("dvizh_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("value", sa.String(16), nullable=False),
        sa.Column("near_consented_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("candidate_id", "user_id"),
    )
    op.create_table(
        "dvizh_confirmations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("dvizh_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("candidate_id", "user_id"),
    )
    op.create_table(
        "max_webhook_events",
        sa.Column("fingerprint", sa.String(128), primary_key=True),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # Retire unfinished legacy discovery without deleting historical offers or confirmed plans.
    # The new UI never exposes the old pending invitation flow.
    op.execute(
        "UPDATE intents SET status = 'CANCELLED' WHERE flow_version = 1 AND status = 'ACTIVE'"
    )
    op.execute(
        "UPDATE offers SET status = 'INVALIDATED' WHERE status IN ('PENDING', 'WAITING_CONDITION', 'WAITLISTED')"
    )
    op.execute("UPDATE candidate_plans SET status = 'CANCELLED' WHERE status = 'COLLECTING'")
    op.execute(
        "UPDATE outbox_notifications SET status = 'FAILED' WHERE status = 'PENDING' AND kind = 'OFFER'"
    )


def downgrade() -> None:
    op.drop_table("max_webhook_events")
    op.drop_table("dvizh_confirmations")
    op.drop_table("dvizh_reactions")
    op.drop_index("ix_dvizh_candidates_order", table_name="dvizh_candidates")
    op.drop_table("dvizh_candidates")
    op.drop_index("ix_dvizh_sessions_group_id", table_name="dvizh_sessions")
    op.drop_index("ix_dvizh_group_status", table_name="dvizh_sessions")
    op.drop_table("dvizh_sessions")
    op.drop_column("intents", "flow_version")
