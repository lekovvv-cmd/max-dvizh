"""Persistence models. Private constraints never leave these records unfiltered."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uid() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    max_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    max_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    default_city_slug: Mapped[str] = mapped_column(String(64))
    timezone_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    invite_token: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: uuid4().hex)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="MEMBER")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(80))
    address_text: Mapped[str | None] = mapped_column(String(250), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    city_slug: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(20), default="SAVED")
    is_ephemeral: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Intent(Base):
    __tablename__ = "intents"
    __table_args__ = (Index("ix_intents_group_active_city", "group_id", "status", "city_slug"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city_slug: Mapped[str] = mapped_column(String(64))
    activity_category: Mapped[str] = mapped_column(String(64))
    activity_categories: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    signal_batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    provider_state: Mapped[str] = mapped_column(String(24), default="NOT_CHECKED")
    available_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recurrence_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    budget_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin_location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    radius_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_people: Mapped[int] = mapped_column(Integer)
    max_people: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidatePlan(Base):
    __tablename__ = "candidate_plans"
    __table_args__ = (Index("ix_candidate_group_status_start", "group_id", "status", "starts_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    city_slug: Mapped[str] = mapped_column(String(64))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estimated_price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_min_people: Mapped[int] = mapped_column(Integer)
    required_max_people: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="COLLECTING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidatePlanSourceSnapshot(Base):
    """Stable provider facts, persisted only after a concrete plan is created."""

    __tablename__ = "candidate_plan_source_snapshots"
    __table_args__ = (UniqueConstraint("candidate_plan_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    candidate_plan_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_plans.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    provider_item_id: Mapped[str] = mapped_column(String(100))
    provider_item_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(250))
    category: Mapped[str] = mapped_column(String(64))
    venue_name: Mapped[str | None] = mapped_column(String(250), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_text: Mapped[str | None] = mapped_column(String(250), nullable=True)
    parsed_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    source_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class CandidatePlanMember(Base):
    __tablename__ = "candidate_plan_members"
    __table_args__ = (UniqueConstraint("candidate_plan_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_plan_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_plans.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("intents.id"))
    compatibility: Mapped[str] = mapped_column(String(20))
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deviations_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    considered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint("candidate_plan_id", "user_id"),
        Index("ix_offers_user_status", "user_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    candidate_plan_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_plans.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    is_near: Mapped[bool] = mapped_column(Boolean, default=False)
    exception_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxNotification(Base):
    __tablename__ = "outbox_notifications"
    __table_args__ = (UniqueConstraint("dedupe_key"), Index("ix_outbox_dispatch", "status", "next_attempt_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(40))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    dedupe_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
