from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from launchpad.flashsystem_fc import (
    parse_fabric_logins,
    parse_fc_hosts,
    parse_host_lun_maps,
    parse_lsvdisk_volumes,
)
from launchpad.inventory_sync import build_inventory_sync
from launchpad.storage_presets import is_svc_fc_profile

LUN_OFFLINE_INVENTORY_SETTING = "lun_offline_inventory"


def _device_profile(card: dict | object) -> str:
    if isinstance(card, dict):
        return str(card.get("device_profile") or "").strip()
    return str(getattr(card, "device_profile", "") or "").strip()


def is_lun_offline_inventory_eligible(card: dict | object, *, monitor_on: bool) -> bool:
    if not monitor_on:
        return False
    return is_svc_fc_profile(_device_profile(card))


def normalize_snapshot(raw: dict | None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    try:
        card_id = int(raw.get("card_id"))
    except (TypeError, ValueError):
        return None
    hosts = raw.get("hosts") if isinstance(raw.get("hosts"), list) else []
    volumes = raw.get("volumes") if isinstance(raw.get("volumes"), list) else []
    return {
        "card_id": card_id,
        "site_name": str(raw.get("site_name") or "").strip(),
        "host": str(raw.get("host") or "").strip(),
        "device_profile": str(raw.get("device_profile") or "").strip(),
        "updated_at": str(raw.get("updated_at") or "").strip(),
        "hosts": hosts,
        "volumes": volumes,
        "last_error": raw.get("last_error"),
        "last_error_at": raw.get("last_error_at"),
    }


def normalize_store(raw: Any) -> dict[str, dict]:
    if isinstance(raw, dict):
        out: dict[str, dict] = {}
        for key, value in raw.items():
            cleaned = normalize_snapshot(value)
            if cleaned is not None:
                out[str(cleaned.get("card_id") or key)] = cleaned
        return out
    if isinstance(raw, list):
        out = {}
        for item in raw:
            cleaned = normalize_snapshot(item)
            if cleaned is not None:
                out[str(cleaned["card_id"])] = cleaned
        return out
    return {}


def upsert_snapshot(store: dict[str, dict], snapshot: dict) -> dict[str, dict]:
    cleaned = normalize_snapshot(snapshot)
    if cleaned is None:
        return dict(store)
    out = dict(store)
    out[str(cleaned["card_id"])] = cleaned
    return out


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_snapshot_error(
    store: dict[str, dict],
    *,
    card_id: int,
    error: str,
    site_name: str = "",
    host: str = "",
    device_profile: str = "",
) -> dict[str, dict]:
    key = str(card_id)
    out = dict(store)
    prior = out.get(key)
    if isinstance(prior, dict):
        row = dict(prior)
    else:
        row = {
            "card_id": card_id,
            "site_name": site_name,
            "host": host,
            "device_profile": device_profile,
            "updated_at": "",
            "hosts": [],
            "volumes": [],
        }
    row["last_error"] = str(error or "").strip()
    row["last_error_at"] = _utc_now_iso()
    out[key] = row
    return out


def _outputs_for(
    command_results: list[dict] | None,
    *needles: str,
    exclude: tuple[str, ...] = (),
) -> str:
    for item in command_results or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        blob = f"{item.get('label') or ''} {item.get('command') or ''}".lower()
        if exclude and any(token in blob for token in exclude):
            continue
        if any(n in blob for n in needles):
            return str(item.get("output") or "")
    return ""


def _volume_rows(volumes: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for volume in volumes:
        name = str(volume.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "pool": str(volume.get("pool") or "").strip(),
                "capacity": str(volume.get("capacity") or "").strip(),
                "status": str(volume.get("status") or "").strip(),
            }
        )
    return rows


def snapshot_from_command_results(
    *,
    card_id: int,
    site_name: str,
    host: str,
    device_profile: str,
    command_results: list[dict] | None,
    updated_at: str | None = None,
) -> dict:
    hosts_out = _outputs_for(
        command_results,
        "lshost",
        "fc - hosts",
        exclude=("lshostvdiskmap", "lsvdiskhostmap", "host lun"),
    )
    maps_out = _outputs_for(command_results, "lshostvdiskmap", "host lun")
    volumes_out = _outputs_for(command_results, "lsvdisk", "memory - volumes")
    fabric_out = _outputs_for(command_results, "lsfabric")

    hosts = parse_fc_hosts(hosts_out)
    maps = parse_host_lun_maps(maps_out)
    volumes = parse_lsvdisk_volumes(volumes_out)
    fabric = parse_fabric_logins(fabric_out)

    sync = build_inventory_sync(
        hosts=hosts,
        volumes=volumes,
        maps=maps,
        card_name=site_name,
        storage_profile=device_profile,
        storage_hint=host,
        fabric_or_host_wwpns=fabric,
        allow_empty=True,
    )

    return {
        "card_id": card_id,
        "site_name": site_name,
        "host": host,
        "device_profile": device_profile,
        "updated_at": updated_at or _utc_now_iso(),
        "hosts": sync["hosts"],
        "volumes": _volume_rows(volumes),
        "last_error": None,
        "last_error_at": None,
    }


def summarize_snapshot(snapshot: dict) -> dict:
    hosts = snapshot.get("hosts") if isinstance(snapshot.get("hosts"), list) else []
    volumes = snapshot.get("volumes") if isinstance(snapshot.get("volumes"), list) else []
    return {
        "card_id": snapshot.get("card_id"),
        "site_name": snapshot.get("site_name") or "",
        "host": snapshot.get("host") or "",
        "updated_at": snapshot.get("updated_at") or "",
        "host_count": len(hosts),
        "volume_count": len(volumes),
        "last_error": snapshot.get("last_error"),
    }
