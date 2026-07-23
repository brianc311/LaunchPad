from datetime import datetime

from launchpad.capacity_email_scheduler import is_capacity_email_due
from launchpad.capacity_email_settings import normalize_capacity_email_settings


def _settings(**kwargs):
    base = {
        "enabled": True,
        "mode": "daily",
        "time_local": "08:00",
        "weekday": 0,
        "every_n_days": 7,
        "last_sent_at": "",
    }
    base.update(kwargs)
    return normalize_capacity_email_settings(base)


def test_disabled_never_due():
    assert not is_capacity_email_due(_settings(enabled=False), datetime(2026, 7, 21, 9, 0))


def test_daily_due_once_per_day_after_time():
    s = _settings(mode="daily", time_local="08:00")
    assert not is_capacity_email_due(s, datetime(2026, 7, 21, 7, 59))
    assert is_capacity_email_due(s, datetime(2026, 7, 21, 8, 0))
    s["last_sent_at"] = "2026-07-21T08:05:00"
    assert not is_capacity_email_due(s, datetime(2026, 7, 21, 18, 0))
    assert is_capacity_email_due(s, datetime(2026, 7, 22, 8, 0))


def test_weekly_monday_only():
    s = _settings(mode="weekly", weekday=0, time_local="08:00")  # 2026-07-20 is Monday
    assert is_capacity_email_due(s, datetime(2026, 7, 20, 8, 0))
    assert not is_capacity_email_due(s, datetime(2026, 7, 21, 8, 0))  # Tuesday


def test_every_n_days():
    s = _settings(mode="every_n_days", every_n_days=3, time_local="08:00", last_sent_at="2026-07-18T08:00:00")
    assert not is_capacity_email_due(s, datetime(2026, 7, 20, 8, 0))  # 2 days
    assert is_capacity_email_due(s, datetime(2026, 7, 21, 8, 0))  # 3 days
