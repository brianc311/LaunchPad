"""Capacity email schedule due-window helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from launchpad.capacity_email_settings import normalize_capacity_email_settings


def _parse_last_sent(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def _time_reached(now: datetime, time_local: str) -> bool:
    hour_s, minute_s = time_local.split(":")
    return (now.hour, now.minute) >= (int(hour_s), int(minute_s))


def is_capacity_email_due(settings: dict[str, Any], now: datetime | None = None) -> bool:
    s = normalize_capacity_email_settings(settings)
    if not s["enabled"]:
        return False
    current = now or datetime.now()
    if not _time_reached(current, s["time_local"]):
        return False
    last = _parse_last_sent(s["last_sent_at"])
    last_date = last.date() if last else None
    today = current.date()
    mode = s["mode"]
    if mode == "daily":
        return last_date != today
    if mode == "weekly":
        if current.weekday() != int(s["weekday"]):
            return False
        return last_date != today
    # every_n_days
    if last_date is None:
        return True
    return (today - last_date).days >= int(s["every_n_days"])
