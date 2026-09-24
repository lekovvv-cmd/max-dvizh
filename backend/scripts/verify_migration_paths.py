"""CI probes for upgrading persisted data and creating a fresh database."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url


def seed_legacy(engine: Engine) -> None:
    """Write rows using only columns available at revision 20260916_0005."""
    current = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, max_user_id, display_name) VALUES ('legacy-user', 'legacy-user', 'Legacy user')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO groups (id, name, default_city_slug, created_by, invite_token) VALUES ('legacy-group', 'Legacy friends', 'ekb', 'legacy-user', 'legacy-invite')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO group_members (group_id, user_id, role) VALUES ('legacy-group', 'legacy-user', 'OWNER')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO locations (id, user_id, label, latitude, longitude, city_slug, kind, is_ephemeral) VALUES ('legacy-location', 'legacy-user', 'Home', 56.84, 60.61, 'ekb', 'SAVED', false)"
            )
        )
        connection.execute(
            text("""INSERT INTO intents (id, user_id, group_id, type, status, city_slug, activity_category, available_from, available_to, budget_max, origin_location_id, radius_km, min_people, max_people)
                    VALUES ('legacy-intent', 'legacy-user', 'legacy-group', 'ONE_TIME', 'ACTIVE', 'ekb', 'games', :starts_at, :ends_at, 500, 'legacy-location', 5, 3, 5)"""),
            {"starts_at": current + timedelta(hours=1), "ends_at": current + timedelta(hours=5)},
        )


def verify_upgrade(engine: Engine) -> None:
    """Assert the new nullable fields and category backfill preserved old data."""
    with engine.connect() as connection:
        row = (
            connection.execute(
                text("""SELECT i.activity_category, i.activity_categories, i.signal_batch_id, i.provider_state, i.budget_max, i.max_people,
                       i.status, i.flow_version,
                       g.name AS group_name, g.timezone_name, g.invite_expires_at, l.label AS location_label, l.address_text, l.is_default
                    FROM intents AS i JOIN groups AS g ON g.id = i.group_id
                    JOIN locations AS l ON l.id = i.origin_location_id
                    WHERE i.id = 'legacy-intent'""")
            )
            .mappings()
            .one()
        )
        assert row["activity_category"] == "games"
        assert row["activity_categories"] == ["games"]
        assert row["signal_batch_id"] is None
        assert row["provider_state"] == "NOT_CHECKED"
        assert row["budget_max"] == 500 and row["max_people"] == 5
        assert row["status"] == "CANCELLED" and row["flow_version"] == 1
        assert row["group_name"] == "Legacy friends" and row["location_label"] == "Home"
        assert row["timezone_name"] is None and row["invite_expires_at"] is None
        assert row["address_text"] is None
        assert row["is_default"] is False
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260924_0011"
        assert (
            connection.scalar(text("SELECT to_regclass('public.dvizh_sessions')"))
            == "dvizh_sessions"
        )


def create_clean_database(database_url: str) -> None:
    admin_url = make_url(database_url).set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql("CREATE DATABASE max_dvizh_clean")
    finally:
        admin_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("seed-legacy", "verify-upgrade", "create-clean-database")
    )
    action = parser.parse_args().action
    database_url = os.environ["DATABASE_URL"]
    if action == "create-clean-database":
        create_clean_database(database_url)
        return
    engine = create_engine(database_url)
    try:
        if action == "seed-legacy":
            seed_legacy(engine)
        else:
            verify_upgrade(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
