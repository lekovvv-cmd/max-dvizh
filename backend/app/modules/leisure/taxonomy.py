"""Product taxonomy and deterministic KudaGo classification (single source of truth)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Activity:
    id: str
    label: str
    directions: tuple[str, ...]
    place_categories: tuple[str, ...] = ()
    event_categories: tuple[str, ...] = ()
    search: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    supported: bool = True


DIRECTIONS = (
    ("games", "Игры"),
    ("active", "Активный отдых"),
    ("culture", "Культура"),
    ("evening", "Музыка и вечер"),
    ("relax", "Релакс"),
)

ACTIVITIES = (
    Activity(
        "pc_club",
        "ПК-клуб",
        ("games",),
        search=("компьютерный клуб", "киберспортивный клуб"),
        keywords=("компьютерный клуб", "киберспортивный клуб", "cyber club", "computer club"),
        supported=False,
    ),
    Activity(
        "quest",
        "Квест",
        ("games",),
        place_categories=("questroom",),
        event_categories=("quest",),
        keywords=("квест",),
    ),
    Activity(
        "anticafe", "Антикафе", ("games",), place_categories=("anticafe",), keywords=("антикафе",)
    ),
    Activity("bowling", "Боулинг", ("games", "active"), search=("боулинг",), keywords=("боулинг",)),
    Activity("billiards", "Бильярд", ("games",), search=("бильярд",), keywords=("бильярд",)),
    Activity(
        "vr",
        "VR",
        ("games",),
        search=("виртуальная реальность",),
        keywords=("виртуальная реальность", "vr-клуб", "vr клуб"),
    ),
    Activity(
        "board_games",
        "Настольные игры",
        ("games",),
        search=("настольные игры",),
        keywords=("настольные игры", "настолки"),
    ),
    Activity("karting", "Картинг", ("active",), search=("картинг",), keywords=("картинг",)),
    Activity(
        "trampoline",
        "Батуты",
        ("active",),
        search=("батут",),
        keywords=("батут", "батутный центр", "батутные центры"),
    ),
    Activity("climbing", "Скалодром", ("active",), search=("скалодром",), keywords=("скалодром",)),
    Activity(
        "ropes_course",
        "Верёвочный парк",
        ("active",),
        search=("веревочный парк",),
        keywords=("верёвочный парк", "веревочный парк"),
    ),
    Activity(
        "horse_riding",
        "Конные прогулки",
        ("active",),
        place_categories=("stable",),
        keywords=("конные прогулки", "конюшня"),
    ),
    Activity("museum", "Музей", ("culture",), place_categories=("museums",), keywords=("музей",)),
    Activity(
        "exhibition",
        "Выставка",
        ("culture",),
        event_categories=("exhibition",),
        keywords=("выставка",),
    ),
    Activity(
        "theater",
        "Театр",
        ("culture",),
        place_categories=("theatre",),
        event_categories=("theater",),
        keywords=("театр",),
    ),
    Activity(
        "tour", "Экскурсия", ("culture",), event_categories=("tour",), keywords=("экскурсия",)
    ),
    Activity(
        "concert", "Концерт", ("evening",), event_categories=("concert",), keywords=("концерт",)
    ),
    Activity(
        "party", "Вечеринка", ("evening",), event_categories=("party",), keywords=("вечеринка",)
    ),
    Activity(
        "sauna",
        "Баня или сауна",
        ("relax",),
        search=("сауна", "баня"),
        keywords=("сауна", "баня", "бани", "банный комплекс"),
    ),
    Activity("spa", "SPA", ("relax",), search=("спа",), keywords=("spa", "спа")),
    Activity(
        "thermal",
        "Термы",
        ("relax",),
        search=("термы",),
        keywords=("термы", "термальный"),
        supported=False,
    ),
)
BY_ID = {activity.id: activity for activity in ACTIVITIES}
DIRECTION_IDS = {item[0] for item in DIRECTIONS}
CONFIDENCE_ORDER = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


def taxonomy_out() -> dict[str, object]:
    return {
        "directions": [{"id": key, "label": label} for key, label in DIRECTIONS],
        "activities": [
            {"id": a.id, "label": a.label, "directions": a.directions}
            for a in ACTIVITIES
            if a.supported
        ],
    }


def expand(selection: list[str] | tuple[str, ...]) -> set[str]:
    result: set[str] = set()
    for item in selection:
        if item.endswith("/*") and item[:-2] in DIRECTION_IDS:
            result.update(a.id for a in ACTIVITIES if a.supported and item[:-2] in a.directions)
        elif item in BY_ID and BY_ID[item].supported:
            result.add(item)
    return result


def valid_selection(selection: list[str]) -> bool:
    return (
        bool(selection)
        and len(selection) <= 12
        and len(set(selection)) == len(selection)
        and all(
            item in BY_ID
            and BY_ID[item].supported
            or item.endswith("/*")
            and item[:-2] in DIRECTION_IDS
            for item in selection
        )
    )


def _matches(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(phrase.casefold()) + r"(?!\w)", text))


def classify(raw: dict[str, Any], item_type: str) -> dict[str, str]:
    """Description-only matches are LOW and never become actionable filters."""
    categories = set(raw.get("categories") or [])
    tags = " ".join(str(tag) for tag in raw.get("tags") or []).casefold()
    title = str(raw.get("title") or "").casefold()
    description = str(raw.get("description") or "").casefold()
    found: dict[str, str] = {}
    for activity in ACTIVITIES:
        native = activity.place_categories if item_type == "PLACE" else activity.event_categories
        if categories.intersection(native):
            found[activity.id] = "HIGH"
        elif any(_matches(tags, word) or _matches(title, word) for word in activity.keywords):
            found[activity.id] = "HIGH"
        elif any(_matches(description, word) for word in activity.keywords):
            found[activity.id] = "LOW"
    return found


def retrieval(selection: list[str] | tuple[str, ...]) -> tuple[set[str], set[str], set[str]]:
    activities = expand(selection)
    places = {category for aid in activities for category in BY_ID[aid].place_categories}
    events = {category for aid in activities for category in BY_ID[aid].event_categories}
    searches = {query for aid in activities for query in BY_ID[aid].search}
    return places, events, searches
