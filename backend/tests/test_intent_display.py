from app.api.routes.product import recurrence_display_fields


def test_recurrence_display_fields_returns_typed_values() -> None:
    assert recurrence_display_fields(
        {"weekdays": [0, 4], "local_start": "22:00", "local_end": "02:00"}
    ) == ([0, 4], "22:00", "02:00")


def test_recurrence_display_fields_hides_malformed_stored_values() -> None:
    assert recurrence_display_fields(
        {"weekdays": ["4"], "local_start": "24:00", "local_end": 200}
    ) == (None, None, None)
