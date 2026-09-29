"""Development seed remains explicit, safe to repeat and unavailable in production."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import Base, Group, GroupMember, User
from scripts import seed_demo


def test_seed_creates_three_users_and_one_company_without_erasing_existing_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(seed_demo, "settings", SimpleNamespace(local_demo_mode=True))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        unrelated = User(max_user_id="unrelated", display_name="Keep me")
        session.add(unrelated)
        session.commit()
        first = seed_demo.seed_demo_data(session)
        second = seed_demo.seed_demo_data(session)
        assert [user.demo_id for user in first.users] == ["anton", "lena", "maxim"]
        assert all(user.created for user in first.users)
        assert all(not user.created for user in second.users)
        assert first.group_created and not second.group_created
        assert first.group_id == second.group_id
        assert [user.user_id for user in first.users] == [user.user_id for user in second.users]
        assert session.scalar(select(func.count()).select_from(User)) == 4
        assert session.scalar(select(func.count()).select_from(Group)) == 1
        assert session.scalar(select(func.count()).select_from(GroupMember)) == 3
        group = session.get(Group, first.group_id)
        assert group is not None
        assert group.name == "Demo company"
        assert group.default_city_slug == "msk"
        assert group.created_by == first.users[0].user_id
        roles = {
            member.user_id: member.role
            for member in session.scalars(
                select(GroupMember).where(GroupMember.group_id == group.id)
            )
        }
        assert roles == {
            first.users[0].user_id: "OWNER",
            first.users[1].user_id: "MEMBER",
            first.users[2].user_id: "MEMBER",
        }
        assert session.scalar(select(User.display_name).where(User.id == unrelated.id)) == "Keep me"
    engine.dispose()


def test_seed_refuses_non_demo_mode_before_touching_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed_demo, "settings", SimpleNamespace(local_demo_mode=False))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(SystemExit, match="APP_ENV=development"):
            seed_demo.seed_demo_data(session)
        assert session.scalar(select(func.count()).select_from(User)) == 0
    engine.dispose()
