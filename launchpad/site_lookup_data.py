from __future__ import annotations

from typing import Any

from launchpad.storage_presets import SVC_PROFILES


def is_svc_card(card: dict[str, Any]) -> bool:
    return str(card.get("device_profile") or "").strip() in SVC_PROFILES


def filter_svc_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [card for card in cards if is_svc_card(card)]


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def match_contingency_groups(
    groups: list[dict[str, Any]], *, card_name: str
) -> list[dict[str, Any]]:
    key = _norm(card_name)
    if not key:
        return []
    matched: list[dict[str, Any]] = []
    for group in groups:
        needles = (
            group.get("name"),
            group.get("location"),
            group.get("storage_hint"),
            group.get("id"),
        )
        if any(_norm(item) == key for item in needles):
            matched.append(group)
    return matched


def _card_meta(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "name": str(card.get("name") or ""),
        "host": str(card.get("host") or ""),
        "model": str(card.get("model") or ""),
        "serial": str(card.get("serial_number") or card.get("serial") or ""),
        "device_profile": str(card.get("device_profile") or ""),
    }


def _host_row(raw: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("host_name") or raw.get("name") or "").strip()
    return {
        "name": name,
        "status": str(raw.get("status") or ""),
        "type": str(raw.get("type") or "Generic"),
        "ports": str(raw.get("port_count") or raw.get("ports") or ""),
        "protocol": str(raw.get("protocol") or ""),
    }


def _volume_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(raw.get("name") or raw.get("vdisk_name") or "").strip(),
        "uid": str(raw.get("uid") or raw.get("vdisk_UID") or ""),
        "capacity": str(raw.get("capacity") or ""),
        "pool": str(raw.get("pool") or raw.get("mdisk_grp_name") or ""),
        "status": str(raw.get("status") or ""),
    }


def _map_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": str(raw.get("host_name") or raw.get("host") or "").strip(),
        "volume": str(raw.get("vdisk_name") or raw.get("volume") or raw.get("name") or "").strip(),
        "scsi_id": str(raw.get("scsi_id") or raw.get("SCSI_id") or ""),
        "io_group": str(raw.get("io_group_name") or raw.get("io_group") or ""),
    }


def _cg_row_from_live(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw.get("id") or ""),
        "name": str(raw.get("name") or "").strip(),
        "status": str(raw.get("status") or ""),
        "type": str(raw.get("type") or ""),
    }


def _cg_row_from_group(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(group.get("id") or ""),
        "name": str(group.get("name") or "").strip(),
        "status": "LaunchPad",
        "type": "contingency_group",
        "location": str(group.get("location") or ""),
        "volume_count": len(group.get("volumes") or []),
        "host_count": len(group.get("hosts") or []),
        "map_count": len(group.get("maps") or []),
    }


def _volumes_from_maps(maps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in maps:
        name = str(row.get("volume") or "").strip()
        if name and name not in seen:
            seen[name] = {"name": name, "uid": "", "capacity": "", "pool": "", "status": ""}
    return list(seen.values())


def _stats(hosts, volumes, mappings, cgs) -> dict[str, int]:
    return {
        "hosts": len(hosts),
        "volumes": len(volumes),
        "mappings": len(mappings),
        "cgs": len(cgs),
    }


def payload_from_card_cache(
    card: dict[str, Any],
    *,
    contingency_groups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    hosts = [_host_row(h) for h in (card.get("fc_hosts") or []) if _host_row(h)["name"]]
    mappings = [
        row
        for m in (card.get("fc_mappings") or [])
        if (row := _map_row(m))["host"] or row["volume"]
    ]
    volumes = _volumes_from_maps(mappings)
    for vol in card.get("fc_volumes") or []:
        row = _volume_row(vol)
        if row["name"] and row["name"] not in {v["name"] for v in volumes}:
            volumes.append(row)
    matched = match_contingency_groups(
        contingency_groups or [], card_name=str(card.get("name") or "")
    )
    for group in matched:
        for vol in group.get("volumes") or []:
            row = _volume_row(vol if isinstance(vol, dict) else {"name": vol})
            if row["name"] and row["name"] not in {v["name"] for v in volumes}:
                volumes.append(row)
    cgs = [_cg_row_from_group(g) for g in matched]
    return {
        "card": _card_meta(card),
        "stats": _stats(hosts, volumes, mappings, cgs),
        "hosts": hosts,
        "volumes": volumes,
        "mappings": mappings,
        "consistency_groups": cgs,
        "source": "cache",
        "refreshed_at": None,
        "error": None,
    }


def payload_from_ssh(
    *,
    card: dict[str, Any],
    hosts: list[dict[str, Any]],
    volumes: list[dict[str, Any]],
    maps: list[dict[str, Any]],
    consist_groups: list[dict[str, Any]],
    contingency_groups: list[dict[str, Any]] | None = None,
    refreshed_at: str | None = None,
) -> dict[str, Any]:
    host_rows = [_host_row(h) for h in hosts if _host_row(h)["name"]]
    volume_rows = [_volume_row(v) for v in volumes if _volume_row(v)["name"]]
    map_rows = [
        row
        for m in maps
        if (row := _map_row(m))["host"] or row["volume"]
    ]
    live_cgs = [_cg_row_from_live(g) for g in consist_groups if str(g.get("name") or "").strip()]
    if live_cgs:
        cgs = live_cgs
        source = "ssh"
    else:
        matched = match_contingency_groups(
            contingency_groups or [], card_name=str(card.get("name") or "")
        )
        cgs = [_cg_row_from_group(g) for g in matched]
        source = "ssh+cg_fallback"
    return {
        "card": _card_meta(card),
        "stats": _stats(host_rows, volume_rows, map_rows, cgs),
        "hosts": host_rows,
        "volumes": volume_rows,
        "mappings": map_rows,
        "consistency_groups": cgs,
        "source": source,
        "refreshed_at": refreshed_at,
        "error": None,
    }
