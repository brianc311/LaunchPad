"""Weekly capacity snapshots for Dell Report week-over-week growth.

Store shape (JSON on disk under APP_DATA_DIR):

    {
      "<card_id>": {
        "<iso_week>": {
          "week": "2026-W32",
          "usable_bytes": 123.0,
          "used_bytes": 45.0,
          "model": "...",
          "facility": "...",
          "family": "ibm" | "hp",
          "array_name": "...",
          "captured_at": "<iso8601>",
        },
        ...
      },
      ...
    }

Each card keeps at most ``DELL_SNAPSHOT_RETENTION_WEEKS`` ISO weeks (newest retained).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from launchpad.config import APP_DATA_DIR

DELL_SNAPSHOT_RETENTION_WEEKS = 12
DELL_SNAPSHOTS_FILENAME = "dell_report_snapshots.json"
DEFAULT_DELL_SNAPSHOTS_PATH = APP_DATA_DIR / DELL_SNAPSHOTS_FILENAME
SNAPSHOT_LAYER_SYSTEM = "system"


def iso_week_key(dt: datetime | None = None) -> str:
    """UTC ISO year-week string, e.g. '2026-W32'."""
    when = dt if dt is not None else datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)
    year, week, _ = when.isocalendar()
    return f"{year}-W{week:02d}"


def _card_key(card_id: int | str) -> str:
    return str(card_id)


def _week_sort_key(week: str) -> tuple[int, int]:
    year_str, week_str = week.split("-W", 1)
    return int(year_str), int(week_str)


def _normalize_store(raw: object) -> dict[str, dict[str, dict]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, dict]] = {}
    for card_id, weeks in raw.items():
        if not isinstance(weeks, dict):
            continue
        card_weeks: dict[str, dict] = {}
        for week, snapshot in weeks.items():
            if not isinstance(week, str) or not isinstance(snapshot, dict):
                continue
            card_weeks[week] = dict(snapshot)
        if card_weeks:
            out[str(card_id)] = card_weeks
    return out


def _trim_card_weeks(weeks: dict[str, dict]) -> dict[str, dict]:
    ordered = sorted(weeks.keys(), key=_week_sort_key)
    if len(ordered) <= DELL_SNAPSHOT_RETENTION_WEEKS:
        return weeks
    keep = set(ordered[-DELL_SNAPSHOT_RETENTION_WEEKS:])
    return {week: weeks[week] for week in ordered if week in keep}


def ordered_weeks_for_cards(store: dict, card_ids: list[int | str]) -> list[str]:
    """Union of ISO weeks across cards, oldest→newest, capped by retention."""
    weeks: set[str] = set()
    normalized = _normalize_store(store)
    for card_id in card_ids:
        card_weeks = normalized.get(_card_key(card_id)) or {}
        weeks.update(card_weeks.keys())
    ordered = sorted(weeks, key=_week_sort_key)
    if len(ordered) > DELL_SNAPSHOT_RETENTION_WEEKS:
        ordered = ordered[-DELL_SNAPSHOT_RETENTION_WEEKS:]
    return ordered


def upsert_week_snapshot(
    store: dict,
    *,
    card_id: int | str,
    week: str,
    usable_bytes: float,
    used_bytes: float,
    model: str,
    facility: str,
    family: str,
    array_name: str,
    captured_at: str,
    layer: str = SNAPSHOT_LAYER_SYSTEM,
) -> dict:
    """Insert/replace that card+week; trim older than retention; return store."""
    out = _normalize_store(store)
    key = _card_key(card_id)
    card_weeks = dict(out.get(key, {}))
    card_weeks[week] = {
        "week": week,
        "usable_bytes": usable_bytes,
        "used_bytes": used_bytes,
        "model": model,
        "facility": facility,
        "family": family,
        "array_name": array_name,
        "captured_at": captured_at,
        "layer": layer,
    }
    out[key] = _trim_card_weeks(card_weeks)
    return out


def snapshots_allow_weekly_growth(
    prior: dict | None, current: dict | None
) -> bool:
    if not prior or not current:
        return False
    return (
        prior.get("layer") == SNAPSHOT_LAYER_SYSTEM
        and current.get("layer") == SNAPSHOT_LAYER_SYSTEM
    )


def has_week_snapshot(store: dict, card_id: int | str, week: str) -> bool:
    card_weeks = _normalize_store(store).get(_card_key(card_id))
    return isinstance(card_weeks, dict) and week in card_weeks


def prior_and_current_for_card(
    store: dict, card_id: int | str, *, current_week: str | None = None
) -> tuple[dict | None, dict | None]:
    """Return (prior_snapshot, current_snapshot) for growth columns."""
    card_weeks = _normalize_store(store).get(_card_key(card_id))
    if not card_weeks:
        return None, None

    ordered = sorted(card_weeks.keys(), key=_week_sort_key)
    if current_week is None:
        current_week = ordered[-1]

    if current_week not in card_weeks:
        return None, None

    current = card_weeks[current_week]
    prior_weeks = [week for week in ordered if _week_sort_key(week) < _week_sort_key(current_week)]
    if not prior_weeks:
        return None, current
    prior = card_weeks[prior_weeks[-1]]
    return prior, current


def weekly_growth_fraction(prior_used: float, current_used: float) -> float | None:
    """(current - prior) / prior if prior > 0 else None."""
    if prior_used <= 0:
        return None
    return (current_used - prior_used) / prior_used


def load_dell_snapshots(path: Path | None = None) -> dict:
    target = DEFAULT_DELL_SNAPSHOTS_PATH if path is None else path
    if not target.exists():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _normalize_store(raw)


def save_dell_snapshots(store: dict, path: Path | None = None) -> None:
    target = DEFAULT_DELL_SNAPSHOTS_PATH if path is None else path
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_store(store)
    target.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
