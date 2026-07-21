"""Contingency group seeds, normalization, and FC filter helpers."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from launchpad.lun_builder_data import expand_lun_batch, seed_lun_builder_templates

CONTINGENCY_GROUPS_SETTING = "contingency_groups"

SNAP_SUFFIX = "_snap"

_SEED_UPDATED_AT = "2026-07-17T00:00:00Z"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _host(
    name: str,
    *,
    port_count: int = 2,
    wwpns: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "Online",
        "host_type": "Generic",
        "port_count": port_count,
        "protocol": "SCSI",
        "wwpns": list(wwpns or []),
    }


def _volume(
    name: str,
    *,
    pool: str = "",
    uid: str = "",
    capacity: str = "4.00 TiB",
    role: str = "source",
    source_volume: str = "",
) -> dict[str, Any]:
    return {
        "name": name,
        "capacity": capacity,
        "pool": pool,
        "uid": uid,
        "protocol": "SCSI",
        "role": role,
        "source_volume": source_volume,
    }


def _maps_all_hosts(
    volume: str,
    hosts: list[str],
    scsi_id: str,
    *,
    role: str = "source",
) -> list[dict[str, str]]:
    return [
        {"volume": volume, "host": host, "scsi_id": scsi_id, "role": role}
        for host in hosts
    ]


def _hartford_ct() -> dict[str, Any]:
    host_names = ["pen_hrdcesx_vm01", "pen_hrdcesx_vm02", "pen_hrdcesx_vm03"]
    volumes = [
        _volume("HRDC_ESXI_DS01", pool="Hart_Pool1"),
        _volume("HRDC_ESXI_DS02", pool="Hart_Pool1"),
        _volume("HRDC_ESXI_DS03", pool="Hart_Pool1"),
    ]
    maps: list[dict[str, str]] = []
    for idx, vol in enumerate(volumes):
        maps.extend(_maps_all_hosts(vol["name"], host_names, str(idx)))
    return {
        "id": "hartford-ct",
        "name": "Hartford, CT",
        "location": "Hartford, CT",
        "storage_hint": "",
        "notes": "",
        "updated_at": _SEED_UPDATED_AT,
        "hosts": [_host(n) for n in host_names],
        "volumes": volumes,
        "maps": maps,
    }


def _houston_tx() -> dict[str, Any]:
    host_names = ["pen-houesx-vm03", "pen-houesx-vm04"]
    volumes = [
        _volume(f"HOUSTON_ESX1_DATASTORE_{i}", capacity="", pool="")
        for i in range(1, 5)
    ]
    maps: list[dict[str, str]] = []
    for idx, vol in enumerate(volumes):
        maps.extend(_maps_all_hosts(vol["name"], host_names, str(idx)))
    return {
        "id": "houston-tx",
        "name": "Houston, TX",
        "location": "Houston, TX",
        "storage_hint": "V5kHOU-g3v1",
        "notes": "",
        "updated_at": _SEED_UPDATED_AT,
        "hosts": [_host(n) for n in host_names],
        "volumes": volumes,
        "maps": maps,
    }


def _windsor() -> dict[str, Any]:
    host_names = ["PEN_WINESX_VM01", "PEN_WINESX_VM02", "PEN_WINESX_VM03"]
    wwpns_by_host = {
        "PEN_WINESX_VM01": [
            "51402EC012CFD072",
            "51402EC012CFD073",
            "51402EC012CFD2BE",
            "51402EC012CFD2BF",
        ],
        "PEN_WINESX_VM02": [
            "51402EC012CFD090",
            "51402EC012CFD091",
            "51402EC012CFD2C4",
            "51402EC012CFD2C5",
        ],
        "PEN_WINESX_VM03": [
            "51402EC012C90280",
            "51402EC012C90281",
            "51402EC012C904A4",
            "51402EC012C904A5",
        ],
    }
    uids = [
        "60050768128000A75800000000000000",
        "60050768128000A75800000000000001",
        "60050768128000A75800000000000002",
    ]
    volumes = [
        _volume(f"WIN_ESX_DataStore_{i}", pool="Windsor_G3_Pool0", uid=uids[i - 1])
        for i in range(1, 4)
    ]
    maps: list[dict[str, str]] = []
    for idx, vol in enumerate(volumes):
        maps.extend(_maps_all_hosts(vol["name"], host_names, str(idx)))
    return {
        "id": "windsor",
        "name": "Windsor",
        "location": "Windsor",
        "storage_hint": "v5kwin-g3v1",
        "notes": "",
        "updated_at": _SEED_UPDATED_AT,
        "hosts": [
            _host(n, port_count=4, wwpns=wwpns_by_host[n]) for n in host_names
        ],
        "volumes": volumes,
        "maps": maps,
    }


def _williamston_anderson() -> dict[str, Any]:
    template = next(
        build
        for build in seed_lun_builder_templates()
        if build["id"] == "template-williamston-anderson"
    )
    hosts = [
        _host(name)
        for name in sorted({row["lpar_name"] for row in template["hosts"]})
    ]
    inventory = [
        row
        for lun in template["luns"]
        for row in expand_lun_batch(lun)
    ]
    known_uids = {
        "ADC-Data01": "60050764008101A45800000000000B90",
    }
    volumes = [
        _volume(
            row["name"],
            pool=row["pool_or_cpg"],
            capacity=row["size"],
            uid=known_uids.get(row["name"], ""),
        )
        for row in inventory
    ]
    maps: list[dict[str, str]] = []
    for row in inventory:
        maps.extend(
            _maps_all_hosts(
                row["name"],
                row["host_names"],
                row["scsi_or_lun_id"],
            )
        )
    return {
        "id": "williamston-anderson",
        "name": "Williamston (Anderson)",
        "location": "Williamston (Anderson)",
        "storage_hint": "v7kand-g3v1",
        "notes": "",
        "updated_at": _SEED_UPDATED_AT,
        "hosts": hosts,
        "volumes": volumes,
        "maps": maps,
    }


def seed_contingency_groups() -> list[dict]:
    return [
        generate_snap_rows(_hartford_ct()),
        generate_snap_rows(_houston_tx()),
        generate_snap_rows(_windsor()),
        generate_snap_rows(_williamston_anderson()),
    ]


def snap_volume_name(source_name: str) -> str:
    name = str(source_name or "").strip()
    if name.endswith(SNAP_SUFFIX):
        return name
    return f"{name}{SNAP_SUFFIX}"


def generate_snap_rows(group: dict) -> dict:
    g = normalize_group(group) or {
        "id": "",
        "name": "",
        "location": "",
        "storage_hint": "",
        "notes": "",
        "updated_at": "",
        "hosts": [],
        "volumes": [],
        "maps": [],
    }
    volumes = list(g["volumes"])
    maps = list(g["maps"])
    by_name = {str(v.get("name") or ""): v for v in volumes}
    for vol in list(volumes):
        role = str(vol.get("role") or "source").lower()
        name = str(vol.get("name") or "")
        if role == "snap" or name.endswith(SNAP_SUFFIX):
            continue
        target = snap_volume_name(name)
        if target not in by_name:
            snap = {
                "name": target,
                "capacity": vol.get("capacity") or "",
                "pool": vol.get("pool") or "",
                "uid": "",
                "protocol": vol.get("protocol") or "SCSI",
                "role": "snap",
                "source_volume": name,
            }
            volumes.append(snap)
            by_name[target] = snap
        source_maps = [
            m
            for m in maps
            if str(m.get("volume") or "") == name
            and str(m.get("role") or "source") != "snap"
        ]
        existing_snap_map_keys = {
            (str(m.get("volume")), str(m.get("host")), str(m.get("scsi_id")))
            for m in maps
            if str(m.get("role") or "") == "snap"
        }
        for m in source_maps:
            key = (target, str(m.get("host") or ""), str(m.get("scsi_id") or ""))
            if key in existing_snap_map_keys:
                continue
            maps.append(
                {
                    "volume": target,
                    "host": str(m.get("host") or ""),
                    "scsi_id": str(m.get("scsi_id") or ""),
                    "role": "snap",
                }
            )
            existing_snap_map_keys.add(key)
    g["volumes"] = volumes
    g["maps"] = maps
    return normalize_group(g) or g


def is_snap_volume(vol: dict) -> bool:
    if not isinstance(vol, dict):
        return False
    role = str(vol.get("role") or "source").lower()
    name = str(vol.get("name") or "")
    return role == "snap" or name.endswith(SNAP_SUFFIX)


def source_volumes(group: dict) -> list[dict]:
    out: list[dict] = []
    for vol in group.get("volumes") or []:
        if isinstance(vol, dict) and not is_snap_volume(vol):
            out.append(vol)
    return out


def source_maps_for_volume(group: dict, volume_name: str) -> list[dict]:
    target = str(volume_name or "").strip()
    if not target:
        return []
    out: list[dict] = []
    for mapping in group.get("maps") or []:
        if not isinstance(mapping, dict):
            continue
        if str(mapping.get("volume") or "") != target:
            continue
        if str(mapping.get("role") or "source").lower() == "snap":
            continue
        out.append(mapping)
    return out


def snap_pairs(group: dict) -> list[dict]:
    pairs: list[dict] = []
    volumes = group.get("volumes") or []
    maps = group.get("maps") or []
    by_name = {
        str(vol.get("name") or ""): vol
        for vol in volumes
        if isinstance(vol, dict) and str(vol.get("name") or "")
    }
    for source in source_volumes(group):
        source_name = str(source.get("name") or "")
        target_name = snap_volume_name(source_name)
        target = by_name.get(target_name)
        snap_maps = [
            mapping
            for mapping in maps
            if isinstance(mapping, dict)
            and str(mapping.get("volume") or "") == target_name
            and str(mapping.get("role") or "").lower() == "snap"
        ]
        pairs.append({"source": source, "target": target, "maps": snap_maps})
    return pairs


def validate_wizard_step1(group: dict) -> list[str]:
    warnings: list[str] = []
    sources = source_volumes(group)
    if not sources:
        warnings.append("At least one source volume is required")
        return warnings
    for vol in sources:
        name = str(vol.get("name") or "").strip()
        if not name:
            warnings.append("Source volume name is required")
        pool = str(vol.get("pool") or "").strip()
        if not pool:
            warnings.append(f"Missing pool for source volume {name or '(unnamed)'}")
        capacity = str(vol.get("capacity") or "").strip()
        if not capacity:
            warnings.append(
                f"Missing or invalid size/capacity for source volume {name or '(unnamed)'}"
            )
    return warnings


def validate_wizard_step2(group: dict) -> list[str]:
    warnings: list[str] = []
    volumes = group.get("volumes") or []
    by_name = {
        str(vol.get("name") or ""): vol
        for vol in volumes
        if isinstance(vol, dict) and str(vol.get("name") or "")
    }
    for source in source_volumes(group):
        source_name = str(source.get("name") or "")
        target_name = snap_volume_name(source_name)
        target = by_name.get(target_name)
        if target is None or not is_snap_volume(target):
            warnings.append(f"Missing target volume for source {source_name}")
    return warnings


def _normalize_wwpn(value: str) -> str:
    return re.sub(r"[\s:]", "", str(value or "")).upper()


def _normalize_wwpns(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _normalize_host(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    if not name:
        return None
    try:
        port_count = int(raw.get("port_count") or 2)
    except (TypeError, ValueError):
        port_count = 2
    return {
        "name": name,
        "status": str(raw.get("status") or "Online").strip() or "Online",
        "host_type": str(raw.get("host_type") or "Generic").strip() or "Generic",
        "port_count": max(0, port_count),
        "protocol": str(raw.get("protocol") or "SCSI").strip() or "SCSI",
        "wwpns": _normalize_wwpns(raw.get("wwpns")),
    }


def _normalize_volume(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    if not name:
        return None
    role = str(raw.get("role") or "source").strip().lower()
    if role not in ("source", "snap"):
        role = "source"
    return {
        "name": name,
        "capacity": str(raw.get("capacity") or "").strip(),
        "pool": str(raw.get("pool") or "").strip(),
        "uid": str(raw.get("uid") or "").strip(),
        "protocol": str(raw.get("protocol") or "SCSI").strip() or "SCSI",
        "role": role,
        "source_volume": str(raw.get("source_volume") or "").strip(),
    }


def _normalize_map(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    volume = str(raw.get("volume") or "").strip()
    host = str(raw.get("host") or "").strip()
    if not volume or not host:
        return None
    scsi_raw = raw.get("scsi_id")
    scsi_id = str(scsi_raw).strip() if scsi_raw is not None else ""
    role = str(raw.get("role") or "source").strip().lower()
    if role not in ("source", "snap"):
        role = "source"
    return {"volume": volume, "host": host, "scsi_id": scsi_id, "role": role}


def normalize_group(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    group_id = str(raw.get("id") or "").strip()
    if not group_id:
        return None
    hosts_raw = raw.get("hosts") or []
    volumes_raw = raw.get("volumes") or []
    maps_raw = raw.get("maps") or []
    hosts: list[dict[str, Any]] = []
    if isinstance(hosts_raw, list):
        for item in hosts_raw:
            cleaned = _normalize_host(item)
            if cleaned:
                hosts.append(cleaned)
    volumes: list[dict[str, Any]] = []
    if isinstance(volumes_raw, list):
        for item in volumes_raw:
            cleaned = _normalize_volume(item)
            if cleaned:
                volumes.append(cleaned)
    maps: list[dict[str, str]] = []
    if isinstance(maps_raw, list):
        for item in maps_raw:
            cleaned = _normalize_map(item)
            if cleaned:
                maps.append(cleaned)
    return {
        "id": group_id,
        "name": str(raw.get("name") or "").strip(),
        "location": str(raw.get("location") or "").strip(),
        "storage_hint": str(raw.get("storage_hint") or "").strip(),
        "notes": str(raw.get("notes") or "").strip(),
        "updated_at": str(raw.get("updated_at") or "").strip(),
        "hosts": hosts,
        "volumes": volumes,
        "maps": maps,
    }


def normalize_groups(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        cleaned = normalize_group(item)
        if cleaned is not None:
            out.append(cleaned)
    return out


def upsert_group(groups: list[dict], group: dict) -> list[dict]:
    group_id = str(group.get("id") or "").strip()
    result: list[dict] = []
    replaced = False
    for existing in groups:
        if str(existing.get("id") or "").strip() == group_id:
            result.append(group)
            replaced = True
        else:
            result.append(existing)
    if not replaced:
        result.append(group)
    return result


def delete_group(groups: list[dict], group_id: str) -> list[dict]:
    target = str(group_id or "").strip()
    return [g for g in groups if str(g.get("id") or "").strip() != target]


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "group"


def new_group_id(name: str, existing: list[dict]) -> str:
    taken = {str(g.get("id") or "").strip() for g in existing}
    base = _slugify(name)
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _group_host_names(group: dict) -> set[str]:
    names: set[str] = set()
    for host in group.get("hosts") or []:
        if isinstance(host, dict):
            n = str(host.get("name") or "").strip().lower()
            if n:
                names.add(n)
    return names


def _group_volume_names(group: dict) -> set[str]:
    names: set[str] = set()
    for vol in group.get("volumes") or []:
        if isinstance(vol, dict):
            n = str(vol.get("name") or "").strip().lower()
            if n:
                names.add(n)
    return names


def _group_wwpns(group: dict) -> list[str]:
    wwpns: list[str] = []
    for host in group.get("hosts") or []:
        if not isinstance(host, dict):
            continue
        for w in host.get("wwpns") or []:
            norm = _normalize_wwpn(str(w))
            if norm:
                wwpns.append(norm)
    return wwpns


def group_matches_host(
    group: dict,
    host_name: str,
    wwpns_haystack: str = "",
) -> bool:
    needle = str(host_name or "").strip().lower()
    if needle and needle in _group_host_names(group):
        return True
    haystack = _normalize_wwpn(wwpns_haystack)
    if not haystack:
        return False
    for w in _group_wwpns(group):
        if w and w in haystack:
            return True
    return False


def group_matches_volume(group: dict, volume_name: str) -> bool:
    needle = str(volume_name or "").strip().lower()
    if not needle:
        return False
    return needle in _group_volume_names(group)


def filter_fc_card(card: dict, group: dict | None) -> dict:
    if group is None:
        return card
    out = deepcopy(card)
    hosts_out: list[dict] = []
    for host in card.get("fc_hosts") or []:
        if not isinstance(host, dict):
            continue
        name = str(host.get("host_name") or host.get("name") or "")
        if group_matches_host(group, name):
            hosts_out.append(host)
    maps_out: list[dict] = []
    for mapping in card.get("fc_mappings") or []:
        if not isinstance(mapping, dict):
            continue
        host = str(mapping.get("host_name") or mapping.get("host") or "")
        vdisk = str(mapping.get("vdisk_name") or mapping.get("volume") or "")
        wwpn_hay = str(mapping.get("host_wwpns") or "")
        if group_matches_volume(group, vdisk) or group_matches_host(
            group, host, wwpn_hay
        ):
            maps_out.append(mapping)
    out["fc_hosts"] = hosts_out
    out["fc_mappings"] = maps_out
    return out
