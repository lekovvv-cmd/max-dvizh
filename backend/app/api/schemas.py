from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator


class SessionOut(BaseModel):
    id: str
    display_name: str
    max_mode: str
    max_chat_id: str | None = None
    onboarding_seen: bool = False


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    city_slug: str = Field(min_length=2, max_length=64)
    bind_current_chat: bool = False


class GroupOut(BaseModel):
    id: str
    name: str
    city_slug: str
    member_count: int
    invite_token: str | None = None
    invite_url: str | None = None
    max_chat_bound: bool = False


class GroupMemberOut(BaseModel):
    id: str
    display_name: str
    is_me: bool


class GroupCityUpdateIn(BaseModel):
    city_slug: str = Field(min_length=2, max_length=64)


class GroupCityUpdateOut(BaseModel):
    group: GroupOut
    cancelled_signals: int
    paused_autosignals: int
    cancelled_plans: int
    invalidated_offers: int


class JoinOut(BaseModel):
    group: GroupOut
    already_member: bool


class LocationIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    address_text: str | None = Field(default=None, max_length=250)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    city_slug: str = Field(min_length=2, max_length=64)
    kind: str = Field(default="SAVED", pattern="^(SAVED|CURRENT|MANUAL)$")
    is_ephemeral: bool = False


class LocationOut(BaseModel):
    id: str
    label: str
    city_slug: str
    kind: str
    address_text: str | None = None
    is_default: bool = False


class LocationRenameIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)


class IntentIn(BaseModel):
    group_id: str
    city_slug: str | None = None
    activity_category: str = Field(default="any", min_length=1, max_length=64)
    activity_categories: list[str] | None = None
    available_from: datetime | None = None
    available_to: datetime | None = None
    budget_max: int | None = Field(default=None, ge=0, le=100000)
    origin_location_id: str | None = None
    radius_km: float | None = Field(default=None, gt=0, le=100)
    min_people: int = Field(ge=2, le=12)
    max_people: int | None = Field(default=None, ge=2, le=12)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_optional_radius(self) -> IntentIn:
        if self.radius_km is not None and self.origin_location_id is None:
            raise ValueError("Для радиуса выберите точку отправления")
        if self.max_people is not None and self.min_people > self.max_people:
            raise ValueError("Минимум участников больше максимума")
        if self.activity_categories is not None and (
            not self.activity_categories
            or len(self.activity_categories) > 12
            or any(not item or len(item) > 64 for item in self.activity_categories)
        ):
            raise ValueError("Выберите категории")
        return self


class SignalBatchIn(BaseModel):
    group_ids: list[str] = Field(min_length=1, max_length=12)
    activity_categories: list[str] = Field(
        default_factory=lambda: ["any"], min_length=1, max_length=12
    )
    available_from: datetime
    available_to: datetime
    budget_max: int | None = Field(default=None, ge=0, le=100000)
    origin_location_id: str | None = None
    radius_km: float | None = Field(default=None, gt=0, le=100)
    min_people: int = Field(default=2, ge=2, le=12)
    max_people: int | None = Field(default=None, ge=2, le=12)

    @model_validator(mode="after")
    def validate_batch(self) -> SignalBatchIn:
        if len(set(self.group_ids)) != len(self.group_ids):
            raise ValueError("Компания выбрана несколько раз")
        if self.available_from >= self.available_to:
            raise ValueError("Укажите корректное окно времени")
        if self.max_people is not None and self.max_people < self.min_people:
            raise ValueError("Минимум участников больше максимума")
        if self.radius_km is not None and not self.origin_location_id:
            raise ValueError("Для радиуса выберите место")
        return self


class SignalBatchOut(BaseModel):
    signal_batch_id: str
    intents: list[IntentOut]


class AutoSignalIn(IntentIn):
    name: str = Field(min_length=1, max_length=120)
    weekdays: list[int] = Field(min_length=1, max_length=7)
    local_start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    local_end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_recurrence(self) -> AutoSignalIn:
        if any(day < 0 or day > 6 for day in self.weekdays) or len(set(self.weekdays)) != len(
            self.weekdays
        ):
            raise ValueError("Дни недели должны быть уникальными числами от 0 до 6")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Укажите IANA timezone, например Asia/Yekaterinburg") from error
        return self


class IntentOut(BaseModel):
    id: str
    type: str
    status: str
    provider_state: str
    name: str | None
    city_slug: str
    activity_category: str
    activity_categories: list[str]
    signal_batch_id: str | None
    group_id: str
    group_name: str | None = None
    budget_max: int | None
    radius_km: float | None
    origin_location_id: str | None = None
    min_people: int
    max_people: int | None
    available_from: datetime | None = None
    available_to: datetime | None = None
    expires_at: datetime | None
    weekdays: list[int] | None = None
    local_start: str | None = None
    local_end: str | None = None


class OfferOut(BaseModel):
    id: str
    status: str
    is_near: bool
    group_id: str
    group_name: str
    title: str
    venue_name: str | None
    starts_at: datetime
    ends_at: datetime
    price_text: str | None
    price_min: int | None
    is_demo: bool
    source_url: str | None
    source_fetched_at: datetime
    distance_km: float | None
    required_min_people: int
    required_max_people: int
    expires_at: datetime
    budget_delta: int | None = None
    accepted_count: int = 0
    conditional_count: int = 0
    effective_max: int = 0
    remaining_to_confirm: int = 0
    remaining_capacity: int = 0
    waitlist_count: int = 0
    can_waitlist: bool = False
    can_accept: bool = True
    price_kind: str = "UNKNOWN"
    opening_hours_unverified: bool = False
    address_text: str | None = None


class OfferAction(BaseModel):
    confirm_near_exception: bool = False


class PlanOut(BaseModel):
    id: str
    status: str
    title: str
    venue_name: str | None
    starts_at: datetime
    ends_at: datetime
    price_text: str | None
    source_url: str | None
    participant_count: int
    conditional_count: int = 0
    personal_response_count: int | None = None
    personal_required_min: int | None = None
    required_min_people: int
    required_max_people: int
    share_text: str
    group_id: str
    group_name: str
    remaining_to_confirm: int = 0
    remaining_capacity: int = 0
    participants: list[PlanParticipantOut] = []
    my_offer_id: str | None = None
    my_status: str | None = None
    price_kind: str = "UNKNOWN"
    opening_hours_unverified: bool = False
    address_text: str | None = None


class PlanParticipantOut(BaseModel):
    id: str
    display_name: str


class CityOut(BaseModel):
    slug: str
    name: str
    source: str
    cached: bool = False
