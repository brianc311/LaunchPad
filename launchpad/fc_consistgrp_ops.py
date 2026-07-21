"""Parse FlashCopy consistency group and map inventory from FlashSystem CLI output."""

from __future__ import annotations

from launchpad.flashsystem_fc import _get, _table_records

_STANDALONE_CONSISTGRP = frozenset({"", "0", "no", "none"})


def _normalize_map_count(value: str | int | None) -> str | int:
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    return text


def _is_standalone_consistgrp(consistgrp: str) -> bool:
    return (consistgrp or "").strip().lower() in _STANDALONE_CONSISTGRP


def parse_lsfcconsistgrp(output: str) -> list[dict]:
    """Parse svcinfo lsfcconsistgrp rows into consistency group records."""
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
