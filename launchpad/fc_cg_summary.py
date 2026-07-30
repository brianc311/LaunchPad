"""Shared FlashCopy consistency-group summary helpers."""

from __future__ import annotations

from launchpad.fc_consistgrp_ops import format_cg_total_size, sum_source_size_bytes

_POLICY_KEYS = (
    "copy_rate",
    "autodelete",
    "relationship",
    "starting_status",
    "policy",
)


def format_cg_policy(record_fields: dict[str, str]) -> str:
    """Join non-empty known policy fields with middle-dot separators."""
    parts: list[str] = []
    for key in _POLICY_KEYS:
        value = str(record_fields.get(key) or "").strip()
        if value:
            parts.append(value)
    return " · ".join(parts)


def schedule_interval_days(used_pct: float, threshold: float = 80.0) -> int:
    """Mirror Snapshot Schedule interval: max(2, round(2 + clamped_ratio * 19))."""
    if threshold:
        ratio = max(0.0, min(1.0, used_pct / threshold))
    else:
        ratio = 1.0
    return max(2, round(2 + ratio * 19))


def snaps_per_week_from_days(days: int) -> float:
    """Approximate weekly snap rate from interval days (minimum 1 day)."""
    safe_days = max(1, int(days))
    return round(7 / safe_days, 2)


def _frequency_label(days: int) -> str:
    if days == 7:
        return "WEEKLY"
    if days == 14:
        return "BIWEEKLY"
    return f"EVERY {days} DAYS"


def schedule_context_from_capacity(
    *,
    used_pct: float | None,
    threshold: float = 80.0,
    override: dict | None = None,
) -> dict:
    """Build ``{days, held, label}`` from pool used% and optional schedule override."""
    ov = override if isinstance(override, dict) else None
    if ov and ov.get("held"):
        return {"days": None, "held": True, "label": "HOLD — EXPAND FIRST"}
    if ov and str(ov.get("mode") or "").strip().lower() == "custom":
        try:
            days = int(ov.get("interval_days") or 7)
        except (TypeError, ValueError):
            days = 7
        days = max(2, min(365, days))
        return {"days": days, "held": False, "label": _frequency_label(days)}

    if used_pct is None:
        return {"days": None, "held": True, "label": "NO CAPACITY DATA"}

    pct = float(used_pct)
    if pct >= threshold:
        return {"days": None, "held": True, "label": "HOLD — EXPAND FIRST"}

    days = schedule_interval_days(pct, threshold)
    return {"days": days, "held": False, "label": _frequency_label(days)}


def count_host_maps_for_targets(
    host_maps: list[dict], target_volumes: set[str]
) -> int:
    """Count host-map rows whose volume/vdisk name is in target_volumes."""
    count = 0
    for row in host_maps:
        volume = (
            str(row.get("volume") or row.get("vdisk") or row.get("vdisk_name") or "")
            .strip()
        )
        if volume and volume in target_volumes:
            count += 1
    return count


def _member_maps_for_group(maps: list[dict], group_name: str) -> list[dict]:
    members: list[dict] = []
    for mapping in maps:
        consistgrp = str(mapping.get("consistgrp") or "").strip()
        if consistgrp == group_name:
            members.append(mapping)
    return members


def _parse_map_progress(raw: object) -> float | int | None:
    text = str(raw or "").strip()
    if text.endswith("%"):
        text = text[:-1].strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value == int(value):
        return int(value)
    return value


def _member_progress_values(maps: list[dict]) -> list[float | int]:
    values: list[float | int] = []
    for mapping in maps:
        parsed = _parse_map_progress(mapping.get("progress"))
        if parsed is not None:
            values.append(parsed)
    return values


def min_map_progress_pct(maps: list[dict], *, status: str) -> float | int | None:
    """Resolve CG progress for the summary row.

    - idle_or_copied / idle_copied → 100 (background copy finished)
    - copying → minimum parseable member map progress
    - stopped / stopping / suspended → minimum when maps report progress, else None
    """
    normalized = str(status or "").strip().lower().replace(" ", "_")
    if normalized in {"idle_or_copied", "idle_copied"}:
        return 100
    values = _member_progress_values(maps)
    if normalized == "copying":
        return min(values) if values else None
    if normalized in {"stopped", "stopping", "suspended"}:
        return min(values) if values else None
    return None


def _target_volumes(maps: list[dict]) -> set[str]:
    targets: set[str] = set()
    for mapping in maps:
        target = str(mapping.get("target") or "").strip()
        if target:
            targets.add(target)
    return targets


def _resolve_snaps(
    group: dict, schedule: dict | None
) -> tuple[float | str | None, str]:
    raw = group.get("snaps_per_week")
    if raw is not None and str(raw).strip() != "":
        try:
            return float(raw), "array"
        except (TypeError, ValueError):
            pass

    if schedule is None:
        return None, "none"

    held = bool(schedule.get("held"))
    days = schedule.get("days")
    label = str(schedule.get("label") or "")
    if held or days is None:
        return label, "schedule"

    return snaps_per_week_from_days(int(days)), "schedule"


def build_cg_summaries(
    *,
    groups: list[dict],
    maps: list[dict],
    host_maps: list[dict],
    schedule: dict | None,
) -> list[dict]:
    """Build per-CG summary rows for FlashCopy CGs and Contingency pages."""
    rows: list[dict] = []
    for group in groups:
        name = str(group.get("name") or "")
        members = _member_maps_for_group(maps, name)
        targets = _target_volumes(members)
        snaps_per_week, snaps_source = _resolve_snaps(group, schedule)
        status = str(group.get("status") or "")
        rows.append(
            {
                "name": name,
                "status": status,
                "flash_time": str(group.get("flash_time") or ""),
                "progress_pct": min_map_progress_pct(members, status=status),
                "policy": group.get("policy") or "",
                "fc_map_count": len(members),
                "host_map_count": count_host_maps_for_targets(host_maps, targets),
                "total_size": format_cg_total_size(members),
                "total_size_bytes": sum_source_size_bytes(members),
                "snaps_per_week": snaps_per_week,
                "snaps_source": snaps_source,
            }
        )
    return rows
