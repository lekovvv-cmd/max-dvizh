"""Create the three local demo identities and their shared company."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Group, GroupMember, User

DEMO_USERS = ("anton", "lena", "maxim")
DEMO_GROUP_NAME = "Demo company"
DEMO_CITY = "msk"


@dataclass(frozen=True)
class SeededUser:
    demo_id: str
    user_id: str
    created: bool


@dataclass(frozen=True)
class SeedResult:
    users: tuple[SeededUser, ...]
    group_id: str
    group_created: bool


def require_demo_mode() -> None:
    if not settings.local_demo_mode:
        raise SystemExit("Demo seed requires APP_ENV=development and ALLOW_DEMO_AUTH=true")


def seed_demo_data(session: Session) -> SeedResult:
    """Add missing rows only; preserve unrelated local data and dynamic IDs."""
    require_demo_mode()
    seeded_users: list[SeededUser] = []
    users: dict[str, User] = {}
    for demo_id in DEMO_USERS:
        user = session.scalar(select(User).where(User.max_user_id == demo_id))
        created = user is None
        if user is None:
            user = User(max_user_id=demo_id, display_name=f"Демо {demo_id}")
            session.add(user)
            session.flush()
        users[demo_id] = user
        seeded_users.append(SeededUser(demo_id, user.id, created))

    group = session.scalar(
        select(Group)
        .where(
            Group.created_by == users["anton"].id,
            Group.name == DEMO_GROUP_NAME,
            Group.default_city_slug == DEMO_CITY,
        )
        .order_by(Group.created_at, Group.id)
    )
    group_created = group is None
    if group is None:
        group = Group(
            name=DEMO_GROUP_NAME,
            default_city_slug=DEMO_CITY,
            timezone_name="Europe/Moscow",
            created_by=users["anton"].id,
        )
        session.add(group)
        session.flush()

    for demo_id, user in users.items():
        membership = session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group.id,
                GroupMember.user_id == user.id,
            )
        )
        if membership is None:
            session.add(
                GroupMember(
                    group_id=group.id,
                    user_id=user.id,
                    role="OWNER" if demo_id == "anton" else "MEMBER",
                )
            )
        elif demo_id == "anton" and membership.role != "OWNER":
            membership.role = "OWNER"
    session.commit()
    return SeedResult(tuple(seeded_users), group.id, group_created)


def main() -> None:
    require_demo_mode()
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        result = seed_demo_data(session)
    for user in result.users:
        state = "created" if user.created else "existing"
        print(f"demo_id={user.demo_id} user_id={user.user_id} status={state}")
    state = "created" if result.group_created else "existing"
    print(f"company={DEMO_GROUP_NAME} group_id={result.group_id} status={state}")


if __name__ == "__main__":
    main()
