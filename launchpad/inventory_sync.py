from __future__ import annotations

import re
from collections import Counter
from typing import Any

from launchpad.contingency_groups_data import generate_snap_rows


def is_flashcopy_target_name(name: str) -> bool:
    text = str(name or "").strip()
    if not text:
        return False
    # Matches *_snap, *_snapN, *_Snap1, and ..._snap_...
    return bool(re.search(r"(?i)(^|_)snap\d*(_|$)", text))


def flashcopy_source_candidate(name: str) -> str | None:
    text = str(name or "").strip()
    if not is_flashcopy_target_name(text):
        return None
    candidate = re.sub(r"(?i)_snap\d*(?=_|$)", "", text)
    candidate = re.sub(r"(?i)^snap\d*_?", "", candidate)
    candidate = candidate.strip("_")
    return candidate or None


def _split_values(raw: Any) -> list[str]:
    if isinstance(raw, (list, tuple, set)):
        values = raw
    else:
        values = re.split(r"[;,]", str(raw or ""))
    return [str(value).strip() for value in values if str(value).strip()]


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "group"


def _wwpns_by_host(raw: Any) -> dict[str, list[str]]:
    if isinstance(raw, dict):
        return {
            str(name): sorted(set(_split_values(values)))
            for name, values in raw.items()
        }
    by_host: dict[str, set[str]] = {}
    if not isinstance(raw, list):
        return {}
    for login in raw:
        if not isinstance(login, dict):
            continue
        name = str(login.get("host_name") or login.get("host") or "").strip()
        values = _split_values(
            login.get("remote_wwpn")
            or login.get("wwpns")
            or login.get("host_wwpns")
        )
        if name:
            by_host.setdefault(name, set()).update(values)
    return {name: sorted(values) for name, values in by_host.items()}


def _lun_host_row(name: str, wwpn1: str = "", wwpn2: str = "") -> dict[str, Any]:
    return {
        "lpar_name": name,
        "slot": "",
        "state": "",
        "required": False,
        "type": "Generic",
        "remote_lpar": "",
        "remote_slot": "",
        "wwpn1": wwpn1,
        "wwpn2": wwpn2,
        "physical_fc_slot": "",
        "managed_system_name": "",
        "managed_system_serial": "",
        "notes": "",
        "done": False,
    }


def build_inventory_sync(
    *,
    hosts: list[dict[str, Any]],
    volumes: list[dict[str, Any]],
    maps: list[dict[str, Any]],
    card_name: str,
    storage_profile: str,
    storage_hint: str = "",
    fabric_or_host_wwpns: Any = None,
    group_id: str = "",
    allow_empty: bool = False,
) -> dict[str, Any]:
    """Shape pulled storage inventory for LUN Builder and Contingency Groups."""
    skipped_snaps = sum(
        is_flashcopy_target_name(str(volume.get("name") or ""))
        for volume in volumes
    )
    kept_volumes = [
        volume
        for volume in volumes
        if str(volume.get("name") or "").strip()
        and not is_flashcopy_target_name(str(volume.get("name") or ""))
    ]
    warnings: list[str] = []
    if not hosts and not kept_volumes and not allow_empty:
        raise ValueError("Refusing empty inventory sync")

    fallback_wwpns = _wwpns_by_host(fabric_or_host_wwpns)
    lun_hosts: list[dict[str, Any]] = []
    cg_hosts: list[dict[str, Any]] = []
    for host in hosts:
        name = str(host.get("host_name") or host.get("name") or "").strip()
        if not name:
            continue
        wwpns = _split_values(
            host.get("wwpns") or host.get("host_wwpns") or fallback_wwpns.get(name)
        )
        if not wwpns:
            lun_hosts.append(_lun_host_row(name))
        else:
            for index in range(0, len(wwpns), 2):
                lun_hosts.append(
                    _lun_host_row(
                        name,
                        wwpns[index],
                        wwpns[index + 1] if index + 1 < len(wwpns) else "",
                    )
                )
        try:
            port_count = int(host.get("port_count") or len(wwpns) or 2)
        except (TypeError, ValueError):
            port_count = len(wwpns) or 2
        cg_hosts.append(
            {
                "name": name,
                "status": str(host.get("status") or "Online").strip() or "Online",
                "host_type": "Generic",
                "port_count": max(0, port_count),
                "protocol": "SCSI",
                "wwpns": wwpns,
            }
        )

    kept_names = {str(volume.get("name") or "").strip() for volume in kept_volumes}
    source_maps: list[dict[str, str]] = []
    maps_by_volume: dict[str, list[dict[str, Any]]] = {}
    for mapping in maps:
        volume_name = str(
            mapping.get("vdisk_name") or mapping.get("volume") or ""
        ).strip()
        if volume_name not in kept_names:
            continue
        host_name = str(mapping.get("host_name") or mapping.get("host") or "").strip()
        scsi_id = str(mapping.get("scsi_id") or "").strip()
        maps_by_volume.setdefault(volume_name, []).append(mapping)
        source_maps.append(
            {
                "volume": volume_name,
                "host": host_name,
                "scsi_id": scsi_id,
                "role": "source",
            }
        )

    pools = [
        str(volume.get("pool") or "").strip()
        for volume in kept_volumes
        if str(volume.get("pool") or "").strip()
    ]
    dominant_pool = Counter(pools).most_common(1)[0][0] if pools else ""
    luns: list[dict[str, Any]] = []
    cg_volumes: list[dict[str, str]] = []
    for volume in kept_volumes:
        name = str(volume.get("name") or "").strip()
        volume_maps = maps_by_volume.get(name, [])
        host_names = list(
            dict.fromkeys(
                str(mapping.get("host_name") or mapping.get("host") or "").strip()
                for mapping in volume_maps
                if str(mapping.get("host_name") or mapping.get("host") or "").strip()
            )
        )
        scsi_ids = {
            str(mapping.get("scsi_id") or "").strip() for mapping in volume_maps
        }
        luns.append(
            {
                "purpose": name,
                "count": 1,
                "exact_name": True,
                "name_prefix": "",
                "size": str(volume.get("capacity") or "").strip(),
                "pool_or_cpg": str(volume.get("pool") or "").strip(),
                "storage_profile": storage_profile,
                "card_hint": card_name,
                "host_names": host_names,
                "shared": len(host_names) > 1,
                "scsi_or_lun_id": next(iter(scsi_ids)) if len(scsi_ids) == 1 else "",
                "cluster": "",
                "done": False,
            }
        )
        cg_volumes.append(
            {
                "name": name,
                "capacity": str(volume.get("capacity") or "").strip(),
                "pool": str(volume.get("pool") or "").strip(),
                "uid": str(volume.get("uid") or "").strip(),
                "protocol": "SCSI",
                "role": "source",
                "source_volume": "",
            }
        )

    claimed_sources: set[str] = set()
    live_snaps = 0
    for volume in volumes:
        name = str(volume.get("name") or "").strip()
        if not is_flashcopy_target_name(name):
            continue
        candidate = flashcopy_source_candidate(name)
        if candidate not in kept_names:
            continue
        if candidate in claimed_sources:
            continue
        cg_volumes.append(
            {
                "name": name,
                "capacity": str(volume.get("capacity") or "").strip(),
                "pool": str(volume.get("pool") or "").strip(),
                "uid": str(volume.get("uid") or "").strip(),
                "protocol": "SCSI",
                "role": "snap",
                "source_volume": candidate,
            }
        )
        claimed_sources.add(candidate)
        live_snaps += 1

    group = generate_snap_rows(
        {
            "id": group_id or _slugify(card_name),
            "name": card_name,
            "location": card_name,
            "storage_hint": storage_hint,
            "notes": "",
            "updated_at": "",
            "hosts": cg_hosts,
            "volumes": cg_volumes,
            "maps": source_maps,
        }
    )
    return {
        "hosts": lun_hosts,
        "luns": luns,
        "defaults": {
            "default_storage_profile": storage_profile,
            "default_pool_or_cpg": dominant_pool,
            "default_card_hint": card_name,
        },
        "group": group,
        "pulled": {
            "hosts": len(hosts),
            "volumes": len(kept_volumes),
            "maps": len(source_maps),
            "skipped_snaps": skipped_snaps,
            "live_snaps": live_snaps,
        },
        "warnings": warnings,
    }
