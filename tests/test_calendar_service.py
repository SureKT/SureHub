from app.services.calendar import _event_body, CALENDAR_COLORS


def test_timed_event_body_uses_datetime_and_color():
    body = _event_body("Pádel", "2026-06-20T18:00:00", "2026-06-20T19:30:00", False, "padel")
    assert body["summary"] == "Pádel"
    assert body["colorId"] == CALENDAR_COLORS["padel"]
    assert body["start"]["dateTime"] == "2026-06-20T18:00:00"
    assert body["end"]["dateTime"] == "2026-06-20T19:30:00"
    assert "timeZone" in body["start"]


def test_all_day_event_body_uses_exclusive_end_date():
    body = _event_body("Cumple", "2026-06-25", "2026-06-25", True, "social")
    assert body["start"]["date"] == "2026-06-25"
    # Google all-day end es exclusivo → +1 día
    assert body["end"]["date"] == "2026-06-26"
    assert body["colorId"] == CALENDAR_COLORS["social"]


def test_unknown_theme_falls_back_to_default_color():
    body = _event_body("X", "2026-06-25", "2026-06-25", True, "inexistente")
    assert body["colorId"] == CALENDAR_COLORS["default"]
