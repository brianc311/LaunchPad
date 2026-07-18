"""Normalize and format Snapshot Schedule per-card overrides."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

SNAPSHOT_OVERRIDES_SETTING = "snapshot_schedule_overrides"
DEFAULT_CUSTOM_TIME = "02:00"

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{1,2})$")
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def parse_time_hhmm(value: str) -> tuple[int, int] | None:
    text = str(value or "").strip()
    match = _TIME_RE.match(text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def format_time_hhmm(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def parse_date_yyyy_mm_dd(value: str) -> date | None:
    text = str(value or "").strip()
    if not _DATE_RE.match(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_one_off(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    parsed_date = parse_date_yyyy_mm_dd(str(raw.get("date") or ""))
    parsed_time = parse_time_hhmm(str(raw.get("time") or ""))
    if not parsed_date or not parsed_time:
        return None
    label = str(raw.get("label") or "").strip()
    item = {
        "date": parsed_date.isoformat(),
        "time": format_time_hhmm(*parsed_time),
    }
    if label:
        item["label"] = label
    return item


def normalize_override(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    mode = str(raw.get("mode") or "auto").strip().lower()
    if mode not in {"auto", "custom"}:
        mode = "auto"
    held = bool(raw.get("held"))
    try:
        interval_days = int(raw.get("interval_days") or 7)
    except (TypeError, ValueError):
        interval_days = 7
    interval_days = max(2, min(365, interval_days))
    start_raw = str(raw.get("start_date") or "").strip()
    start_date = parse_date_yyyy_mm_dd(start_raw)
    time_raw = str(raw.get("time") or DEFAULT_CUSTOM_TIME).strip()
    parsed_time = parse_time_hhmm(time_raw) or parse_time_hhmm(DEFAULT_CUSTOM_TIME)
    assert parsed_time is not None
    one_offs_raw = raw.get("one_offs") or []
    one_offs: list[dict[str, str]] = []
    if isinstance(one_offs_raw, list):
        for item in one_offs_raw:
            cleaned = _normalize_one_off(item)
            if cleaned:
                one_offs.append(cleaned)
    return {
        "mode": mode,
        "held": held,
        "interval_days": interval_days,
        "start_date": start_date.isoformat() if start_date else "",
        "time": format_time_hhmm(*parsed_time),
        "one_offs": one_offs,
    }


def normalize_overrides_map(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        cleaned = normalize_override(value)
        if cleaned is not None:
            out[str(key)] = cleaned
    return out


def format_one_offs_summary(one_offs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in one_offs or []:
        date_s = str(item.get("date") or "").strip()
        time_s = str(item.get("time") or "").strip()
        label = str(item.get("label") or "").strip()
        if not date_s or not time_s:
            continue
        chunk = f"{date_s} {time_s}"
        if label:
            chunk = f"{chunk} {label}"
        parts.append(chunk)
    return "; ".join(parts)
