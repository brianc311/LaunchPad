"""Dell Report Admin settings: normalize, load, save enable flag."""

from __future__ import annotations

import json
from typing import Any

DELL_REPORT_SETTING = "dell_report_settings"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_dell_report_settings(raw: Any) -> dict:
    """Return ``{"enabled": bool}``; default enabled True when missing."""
    data = raw if isinstance(raw, dict) else {}
    if "enabled" not in data:
        enabled = True
    else:
        enabled = _as_bool(data.get("enabled"))
    return {"enabled": enabled}


def load_dell_report_settings(db) -> dict:
    raw = db.get_setting(DELL_REPORT_SETTING, "")
    if not raw:
        return normalize_dell_report_settings({})
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return normalize_dell_report_settings({})
    return normalize_dell_report_settings(parsed)


def save_dell_report_settings(db, settings: dict) -> dict:
    normalized = normalize_dell_report_settings(settings)
    db.set_setting(DELL_REPORT_SETTING, json.dumps(normalized))
    return normalized


def is_dell_report_enabled(db) -> bool:
    return bool(load_dell_report_settings(db)["enabled"])
