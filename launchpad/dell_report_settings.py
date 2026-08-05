"""Dell Report Admin settings: enable, overrides, include_card_ids."""

from __future__ import annotations

import json
from typing import Any

DELL_REPORT_SETTING = "dell_report_settings"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_overrides(raw: Any) -> dict[str, dict[str, str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for card_id, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        cleaned: dict[str, str] = {}
        for key in ("facility", "array_name", "model"):
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                cleaned[key] = val.strip()
        if cleaned:
            out[str(card_id)] = cleaned
    return out


def _normalize_include_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if item is None or item == "":
            continue
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def normalize_dell_report_settings(raw: Any) -> dict:
    """Return enabled, card_overrides, include_card_ids; enabled defaults True."""
    data = raw if isinstance(raw, dict) else {}
    if "enabled" not in data:
        enabled = True
    else:
        enabled = _as_bool(data.get("enabled"))
    return {
        "enabled": enabled,
        "card_overrides": _normalize_overrides(data.get("card_overrides")),
        "include_card_ids": _normalize_include_ids(data.get("include_card_ids")),
    }


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


def is_dell_report_include_card(settings: dict, card_id: int | str) -> bool:
    ids = settings.get("include_card_ids") or []
    return str(card_id) in {str(x) for x in ids}
