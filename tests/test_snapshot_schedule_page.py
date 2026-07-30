"""Contract tests for Snapshot Schedule page HTML/JS (mark-day-complete)."""

from launchpad.snapshot_schedule import SNAPSHOT_SCHEDULE_HTML


def test_snapshot_schedule_completed_css_class():
    html = SNAPSHOT_SCHEDULE_HTML
    assert ".cal-cell.completed" in html
    assert "completed" in html


def test_snapshot_schedule_completed_dates_in_overrides():
    html = SNAPSHOT_SCHEDULE_HTML
    assert "completed_dates" in html


def test_snapshot_schedule_toggle_completed_function():
    html = SNAPSHOT_SCHEDULE_HTML
    assert "function toggleCompletedDate" in html


def test_snapshot_schedule_legend_mentions_completed():
    html = SNAPSHOT_SCHEDULE_HTML
    # Hint / legend distinguishes completed days from scheduled gradient
    hint_ok = (
        ("completed" in html.lower() or "done" in html.lower())
        and ("Solid green" in html or "solid green" in html.lower())
    )
    assert hint_ok, "Legend/hint must mention completed/done with solid green"
