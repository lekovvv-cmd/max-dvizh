from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator


class SessionOut(BaseModel):
    id: str
    display_name: str
    max_mode: str


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    city_slug: str = Field(min_length=2, max_length=64)


class GroupOut(BaseModel):
    id: str
    name: str
    city_slug: str
    member_count: int
    invite_token: str | None = None
    invite_url: str | None = None


class JoinOut(BaseModel):
    group: GroupOut
    already_member: bool


class LocationIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
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


class IntentIn(BaseModel):
    group_id: str
    city_slug: str
    activity_category: str = Field(min_length=1, max_length=64)
    available_from: datetime | None = None
    available_to: datetime | None = None
    budget_max: int | None = Field(default=None, ge=0, le=100000)
    origin_location_id: str | None = None
    radius_km: float | None = Field(default=None, gt=0, le=100)
    min_people: int = Field(ge=1, le=12)
    max_people: int = Field(ge=1, le=12)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_optional_radius(self) -> IntentIn:
        if self.radius_km is not None and self.origin_location_id is None:
            raise ValueError("Для радиуса выберите точку отправления")
        return self


class AutoSignalIn(IntentIn):
    name: str = Field(min_length=1, max_length=120)
    weekdays: list[int] = Field(min_length=1, max_length=7)
    local_start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    local_end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_recurrence(self) -> AutoSignalIn:
        if any(day < 0 or day > 6 for day in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays):
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
    name: str | None
    city_slug: str
    activity_category: str
    budget_max: int | None
    radius_km: float | None
    min_people: int
    max_people: int
    expires_at: datetime | None


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
    potential_count: int
    required_min_people: int
    required_max_people: int
    expires_at: datetime
    budget_delta: int | None = None


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
    required_min_people: int
    required_max_people: int
    share_text: str


class CityOut(BaseModel):
    slug: str
    name: str
    source: str
    cached: bool = False
