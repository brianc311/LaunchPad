"""Parse FlashCopy consistency group inventory and build preview/run CLI steps."""

from __future__ import annotations

import re
from collections.abc import Callable

from launchpad.contingency_snap_create import SnapStep, cli_token
from launchpad.flashsystem_fc import _get, _table_records, parse_lsvdisk_volumes
from launchpad.flashsystem_parse import (
    _format_bytes,
    _parse_key_values,
    _parse_size_bytes,
)
from launchpad.storage_presets import is_svc_fc_profile

ACTIONS = frozenset(
    {"create_group", "assign_maps", "remove_maps", "start_group", "delete_group"}
)

_STANDALONE_CONSISTGRP = frozenset({"", "0", "no", "none"})

_STATUS_BUCKET_ALIASES: dict[str, str] = {
    "idle_or_copied": "idle_or_copied",
    "idle or copied": "idle_or_copied",
    "stopped": "stopped",
    "copying": "copying",
}


def _card_field(card: dict | object, key: str, default: object = "") -> object:
    if isinstance(card, dict):
        return card.get(key, default)
    return getattr(card, key, default)


def normalize_fc_cg_status_bucket(status: str) -> str:
    """Map raw lsfcconsistgrp status to a Status tab bucket, or empty when unknown."""
    normalized = str(status or "").strip().lower().replace("_", " ")
    normalized = " ".join(normalized.split())
    key = normalized.replace(" ", "_")
    if key in _STATUS_BUCKET_ALIASES:
        return _STATUS_BUCKET_ALIASES[key]
    if normalized in _STATUS_BUCKET_ALIASES:
        return _STATUS_BUCKET_ALIASES[normalized]
    return ""


def is_fc_consistgrp_status_eligible(card: dict | object) -> bool:
    """Return True for monitor-on SSH FlashSystem/SVC cards eligible for Status scan."""
    if not bool(_card_field(card, "monitor_on")):
        return False
    if str(_card_field(card, "card_type") or "").lower() != "ssh":
        return False
    profile = str(_card_field(card, "device_profile") or "")
    return is_svc_fc_profile(profile)


def _normalize_map_count(value: str | int | None) -> str | int:
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    return text


def format_flash_time_display(raw: str) -> str:
    """Format IBM FlashCopy timestamps for display (GUI-style US date/time).

    Compact CLI values like ``260502060129`` (YYMMDDHHMMSS) become
    ``5/2/2026 6:01:29 AM``. Already-readable strings are returned as-is when
    they cannot be parsed as a 12- or 14-digit timestamp.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    try:
        if len(digits) == 12:
            year = 2000 + int(digits[0:2])
            month = int(digits[2:4])
            day = int(digits[4:6])
            hour = int(digits[6:8])
            minute = int(digits[8:10])
            second = int(digits[10:12])
        elif len(digits) == 14:
            year = int(digits[0:4])
            month = int(digits[4:6])
            day = int(digits[6:8])
            hour = int(digits[8:10])
            minute = int(digits[10:12])
            second = int(digits[12:14])
        else:
            return text
        if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23):
            return text
        if not (0 <= minute <= 59 and 0 <= second <= 59):
            return text
    except ValueError:
        return text
    hour12 = hour % 12 or 12
    ampm = "AM" if hour < 12 else "PM"
    return f"{month}/{day}/{year} {hour12}:{minute:02d}:{second:02d} {ampm}"


def _is_standalone_consistgrp(consistgrp: str) -> bool:
    return (consistgrp or "").strip().lower() in _STANDALONE_CONSISTGRP


def parse_lsfcconsistgrp(output: str) -> list[dict]:
    """Parse svcinfo lsfcconsistgrp rows into consistency group records."""
    from launchpad.fc_cg_summary import format_cg_policy

    groups: list[dict] = []
    for record in _table_records(output):
        name = _get(record, "name")
        if not name:
            continue
        groups.append(
            {
                "id": _get(record, "id"),
                "name": name,
                "status": _get(record, "status", "state"),
                "map_count": _normalize_map_count(
                    _get(
                        record,
                        "FC_mapping_count",
                        "fc_mapping_count",
                        "mapping_count",
                        "map_count",
                    )
                ),
                "policy": format_cg_policy(record),
                "flash_time": format_flash_time_display(
                    _get(record, "flash_time", "Flash_time", "flashTime")
                ),
            }
        )
    return groups


def parse_lsfcmap_rows(output: str) -> list[dict]:
    """Parse svcinfo lsfcmap rows into FlashCopy map records."""
    maps: list[dict] = []
    for record in _table_records(output):
        name = _get(record, "name")
        if not name:
            continue
        maps.append(
            {
                "id": _get(record, "id"),
                "name": name,
                "source": _get(
                    record,
                    "source_vdisk_name",
                    "source",
                    "source_volume",
                ),
                "target": _get(
                    record,
                    "target_vdisk_name",
                    "target",
                    "target_volume",
                ),
                "status": _get(record, "status", "state"),
                "progress": _get(record, "progress"),
                "start_time": _get(
                    record,
                    "start_time",
                    "Start_time",
                    "flash_time",
                    "Flash_time",
                ),
                "consistgrp": _get(
                    record,
                    "group_name",
                    "consistgrp",
                    "FC_group_name",
                    "fc_group_name",
                ),
            }
        )
    return maps


def partition_maps(maps: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split maps into group members and stand-alone maps."""
    in_groups: list[dict] = []
    stand_alone: list[dict] = []
    for mapping in maps:
        consistgrp = str(mapping.get("consistgrp") or "")
        if _is_standalone_consistgrp(consistgrp):
            stand_alone.append(mapping)
        else:
            in_groups.append(mapping)
    return in_groups, stand_alone


def enrich_group_map_counts(groups: list[dict], maps: list[dict]) -> list[dict]:
    """Set group map_count from parsed map membership when available."""
    membership_counts: dict[str, int] = {}
    for mapping in maps:
        consistgrp = str(mapping.get("consistgrp") or "").strip()
        if _is_standalone_consistgrp(consistgrp):
            continue
        membership_counts[consistgrp] = membership_counts.get(consistgrp, 0) + 1

    enriched: list[dict] = []
    for group in groups:
        updated = dict(group)
        name = str(updated.get("name") or "")
        membership = membership_counts.get(name, 0)
        existing = updated.get("map_count")
        existing_numeric = (
            int(existing)
            if existing is not None and str(existing).strip().isdigit()
            else 0
        )
        if membership > 0:
            updated["map_count"] = membership
        elif existing is None or existing_numeric == 0:
            updated["map_count"] = membership
        enriched.append(updated)
    return enriched


def volume_capacity_index(lsvdisk_output: str) -> dict[str, dict]:
    """Build a volume-name index of capacity labels and byte sizes from lsvdisk output."""
    index: dict[str, dict] = {}
    for volume in parse_lsvdisk_volumes(lsvdisk_output):
        name = str(volume.get("name") or "")
        if not name:
            continue
        capacity = str(volume.get("capacity") or "")
        parsed = _parse_size_bytes(capacity)
        index[name] = {
            "capacity": capacity,
            "bytes": int(parsed) if parsed is not None else None,
        }
    return index


def enrich_maps_with_source_size(
    maps: list[dict], index: dict[str, dict]
) -> list[dict]:
    """Copy maps and attach source volume size fields from a capacity index."""
    enriched: list[dict] = []
    for mapping in maps:
        updated = dict(mapping)
        source = str(updated.get("source") or "")
        entry = index.get(source)
        if entry:
            updated["source_size"] = entry.get("capacity") or ""
            updated["source_size_bytes"] = entry.get("bytes")
        else:
            updated["source_size"] = ""
        enriched.append(updated)
    return enriched


def sum_source_size_bytes(maps: list[dict]) -> int:
    """Sum source_size_bytes across maps, skipping unknown sizes."""
    total = 0
    for mapping in maps:
        bytes_val = mapping.get("source_size_bytes")
        if bytes_val is not None:
            total += int(bytes_val)
    return total


def format_cg_total_size(maps: list[dict]) -> str:
    """Format combined source size for a consistency group, or empty when unknown."""
    total = sum_source_size_bytes(maps)
    if total > 0:
        return _format_bytes(total)
    return ""


def _flash_time_from_detail(output: str) -> str:
    """Extract flash/start time from detailed lsfcconsistgrp key:value output."""
    fields = _parse_key_values(output or "")
    return format_flash_time_display(
        str(fields.get("flash_time") or "").strip()
        or str(fields.get("Flash_time") or "").strip()
        or str(fields.get("start_time") or "").strip()
        or str(fields.get("Start_time") or "").strip()
    )


def _earliest_map_start_time(maps: list[dict], group_name: str) -> str:
    times: list[str] = []
    for mapping in maps:
        if str(mapping.get("consistgrp") or "").strip() != group_name:
            continue
        start = str(mapping.get("start_time") or "").strip()
        if start:
            times.append(start)
    if not times:
        return ""
    # Prefer chronological min on raw compact values, then format for display.
    return format_flash_time_display(min(times))


def enrich_groups_flash_time(
    groups: list[dict],
    maps: list[dict],
    run_cmd: Callable[[str], str] | None = None,
) -> list[dict]:
    """Fill blank flash_time from detailed CG view and/or member map start_time."""
    for group in groups:
        if str(group.get("flash_time") or "").strip():
            continue
        name = str(group.get("name") or "").strip()
        if not name:
            continue
        if run_cmd is not None:
            try:
                detail = run_cmd(f"svcinfo lsfcconsistgrp -delim : {cli_token(name)}")
                flash = _flash_time_from_detail(detail)
                if not flash:
                    detail = run_cmd(f"svcinfo lsfcconsistgrp {cli_token(name)}")
                    flash = _flash_time_from_detail(detail)
                if flash:
                    group["flash_time"] = format_flash_time_display(flash)
                    continue
            except Exception:
                pass
        earliest = _earliest_map_start_time(maps, name)
        if earliest:
            group["flash_time"] = earliest
    return groups


def collect_fc_consistgrp_inventory(
    run_cmd: Callable[[str], str],
) -> tuple[list[dict], list[dict]]:
    """Collect and parse `lsfcconsistgrp` + `lsfcmap` inventory over SSH."""
    groups_output = run_cmd("svcinfo lsfcconsistgrp -delim :")
    if not groups_output.strip():
        groups_output = run_cmd("svcinfo lsfcconsistgrp")
    maps_output = run_cmd("svcinfo lsfcmap -delim :")
    if not maps_output.strip():
        maps_output = run_cmd("svcinfo lsfcmap")

    groups = parse_lsfcconsistgrp(groups_output)
    maps = parse_lsfcmap_rows(maps_output)
    groups = enrich_group_map_counts(groups, maps)
    groups = enrich_groups_flash_time(groups, maps, run_cmd)

    index: dict = {}
    try:
        vols_output = run_cmd("svcinfo lsvdisk -delim :")
        if not str(vols_output or "").strip():
            vols_output = run_cmd("svcinfo lsvdisk")
        index = volume_capacity_index(vols_output)
    except Exception:
        index = {}
    maps = enrich_maps_with_source_size(maps, index)
    return groups, maps


def preview_ok(steps: list[SnapStep], warnings: list[str]) -> bool:
    """Return True when preview has no hard blocking errors."""
    return not any(w.startswith("ERROR:") for w in warnings)


def _group_names(groups: list[dict]) -> set[str]:
    return {str(group.get("name") or "") for group in groups if group.get("name")}


def _maps_by_name(maps: list[dict]) -> dict[str, dict]:
    return {str(mapping.get("name") or ""): mapping for mapping in maps if mapping.get("name")}


def _maps_in_group(maps: list[dict], group_name: str) -> list[dict]:
    return [
        mapping
        for mapping in maps
        if str(mapping.get("consistgrp") or "").strip() == group_name
    ]


def _safe_token(value: str, warnings: list[str], *, label: str) -> str | None:
    try:
        return cli_token(str(value or "").strip())
    except ValueError as exc:
        warnings.append(f"ERROR: {label}: {exc}")
        return None


def build_fc_consistgrp_steps(
    action: str,
    payload: dict,
    *,
    groups: list[dict],
    maps: list[dict],
) -> tuple[list[SnapStep], list[str]]:
    """Build ordered CLI steps and advisory/blocking warnings for a CG action."""
    warnings: list[str] = []
    steps: list[SnapStep] = []

    if action not in ACTIONS:
        warnings.append(f"ERROR: Unknown action {action!r}")
        return steps, warnings

    group_names = _group_names(groups)
    maps_by_name = _maps_by_name(maps)

    if action == "create_group":
        name = _safe_token(str(payload.get("name") or ""), warnings, label="group name")
        if name is None:
            return steps, warnings
        cmd = f"svctask mkfcconsistgrp -name {name}"
        if name in group_names:
            steps.append(
                SnapStep(
                    kind="mkfcconsistgrp",
                    purpose="create consistency group",
                    cmd=cmd,
                    skip=True,
                    reason="consistency group already exists",
                )
            )
        else:
            steps.append(
                SnapStep(
                    kind="mkfcconsistgrp",
                    purpose="create consistency group",
                    cmd=cmd,
                )
            )
        return steps, warnings

    if action == "assign_maps":
        group_name = _safe_token(
            str(payload.get("group_name") or ""), warnings, label="group name"
        )
        if group_name is None:
            return steps, warnings
        if group_name not in group_names:
            warnings.append(f"ERROR: Consistency group {group_name} not found")
            return steps, warnings

        map_names = payload.get("map_names") or []
        if not isinstance(map_names, list):
            warnings.append("ERROR: map_names must be a list")
            return steps, warnings

        for raw_map_name in map_names:
            map_name = _safe_token(str(raw_map_name or ""), warnings, label="map name")
            if map_name is None:
                continue
            mapping = maps_by_name.get(map_name)
            if mapping is None:
                warnings.append(f"ERROR: FlashCopy map {map_name} not found")
                continue

            current_group = str(mapping.get("consistgrp") or "").strip()
            if current_group == group_name:
                steps.append(
                    SnapStep(
                        kind="chfcmap",
                        purpose=f"assign map {map_name} to consistency group",
                        cmd=f"svctask chfcmap -consistgrp {group_name} {map_name}",
                        skip=True,
                        reason=f"map already in consistency group {group_name}",
                    )
                )
                continue
            if current_group and not _is_standalone_consistgrp(current_group):
                warnings.append(
                    f"Map {map_name} is already in consistency group {current_group}"
                )

            steps.append(
                SnapStep(
                    kind="chfcmap",
                    purpose=f"assign map {map_name} to consistency group",
                    cmd=f"svctask chfcmap -consistgrp {group_name} {map_name}",
                )
            )
        return steps, warnings

    if action == "remove_maps":
        map_names = payload.get("map_names") or []
        if not isinstance(map_names, list):
            warnings.append("ERROR: map_names must be a list")
            return steps, warnings

        for raw_map_name in map_names:
            map_name = _safe_token(str(raw_map_name or ""), warnings, label="map name")
            if map_name is None:
                continue
            mapping = maps_by_name.get(map_name)
            if mapping is None:
                warnings.append(f"ERROR: FlashCopy map {map_name} not found")
                continue

            current_group = str(mapping.get("consistgrp") or "").strip()
            if _is_standalone_consistgrp(current_group):
                steps.append(
                    SnapStep(
                        kind="chfcmap",
                        purpose=f"remove map {map_name} from consistency group",
                        cmd=f"svctask chfcmap -consistgrp null {map_name}",
                        skip=True,
                        reason="map is already stand-alone",
                    )
                )
                continue

            steps.append(
                SnapStep(
                    kind="chfcmap",
                    purpose=f"remove map {map_name} from consistency group",
                    cmd=f"svctask chfcmap -consistgrp null {map_name}",
                )
            )
        return steps, warnings

    if action == "start_group":
        group_name = _safe_token(
            str(payload.get("group_name") or ""), warnings, label="group name"
        )
        if group_name is None:
            return steps, warnings
        if group_name not in group_names:
            warnings.append(f"ERROR: Consistency group {group_name} not found")
            return steps, warnings

        steps.extend(
            [
                SnapStep(
                    kind="prestartfcconsistgrp",
                    purpose="prepare consistency group start",
                    cmd=f"svctask prestartfcconsistgrp {group_name}",
                ),
                SnapStep(
                    kind="startfcconsistgrp",
                    purpose="start consistency group",
                    cmd=f"svctask startfcconsistgrp {group_name}",
                ),
            ]
        )
        return steps, warnings

    if action == "delete_group":
        group_name = _safe_token(
            str(payload.get("group_name") or ""), warnings, label="group name"
        )
        if group_name is None:
            return steps, warnings

        member_maps = _maps_in_group(maps, group_name)
        if member_maps:
            warnings.append(f"ERROR: Consistency group {group_name} is not empty")
            return steps, warnings

        cmd = f"svctask rmfcconsistgrp {group_name}"
        if group_name not in group_names:
            steps.append(
                SnapStep(
                    kind="rmfcconsistgrp",
                    purpose="delete consistency group",
                    cmd=cmd,
                    skip=True,
                    reason="consistency group already absent",
                )
            )
        else:
            steps.append(
                SnapStep(
                    kind="rmfcconsistgrp",
                    purpose="delete consistency group",
                    cmd=cmd,
                )
            )
        return steps, warnings

    warnings.append(f"ERROR: Unhandled action {action!r}")
    return steps, warnings
