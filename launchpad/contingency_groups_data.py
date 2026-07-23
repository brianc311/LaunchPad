"""Contingency group seeds, normalization, and FC filter helpers."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

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


def _woodland_hills_ca() -> dict[str, Any]:
    esx_hosts = [
        "PEN-WODESX-VM01",
        "PEN-WODESX-VM02",
        "PEN-WODESX-VM03",
        "PEN-WODESX-VM04",
    ]
    vio_hosts = ["pwoovio01a", "pwoovio01b", "pwoovio02a", "pwoovio02b"]
    hosts = [
        _host("AWD1_New_as400", port_count=8, wwpns=[]),
        *[_host(name, port_count=2, wwpns=[]) for name in esx_hosts],
        *[_host(name, port_count=2, wwpns=[]) for name in vio_hosts],
    ]
    esx_uids = {
        1: "60050768128100A7D000000000000000",
        2: "60050768128100A7D000000000000001",
        3: "60050768128100A7D000000000000002",
        4: "60050768128100A7D000000000000017",
    }
    volumes: list[dict[str, Any]] = [
        _volume(f"AWD1_AS400_{i}", pool="WOO_Pool1", capacity="500.00 GiB")
        for i in range(1, 7)
    ]
    volumes.extend(
        _volume(
            f"WOO_ESX_DataStore_{i}",
            pool="WOO_Pool1",
            capacity="4.00 TiB",
            uid=esx_uids[i],
        )
        for i in range(1, 5)
    )
    for vio in vio_hosts:
        for n in (1, 2):
            uid = ""
            if vio == "pwoovio02b" and n == 1:
                uid = "60050768128100A7D00000000000000F"
            elif vio == "pwoovio02b" and n == 2:
                uid = "60050768128100A7D000000000000010"
            volumes.append(
                _volume(
                    f"{vio}_root_{n}",
                    pool="WOO_Pool1",
                    capacity="100.00 GiB",
                    uid=uid,
                )
            )
    maps: list[dict[str, str]] = []
    for i in range(1, 7):
        maps.extend(
            _maps_all_hosts(f"AWD1_AS400_{i}", ["AWD1_New_as400"], str(i - 1))
        )
    for i in range(1, 5):
        maps.extend(
            _maps_all_hosts(f"WOO_ESX_DataStore_{i}", esx_hosts, str(i - 1))
        )
    for vio in vio_hosts:
        for n in (1, 2):
            maps.extend(
                _maps_all_hosts(f"{vio}_root_{n}", [vio], str(n - 1))
            )
    return {
        "id": "woodland-hills-ca",
        "name": "Woodland Hills, CA",
        "location": "Woodland Hills, CA",
        "storage_hint": "v5kwoo-g3c1",
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
        generate_snap_rows(_woodland_hills_ca()),
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
    linked_snap_by_source: dict[str, str] = {}
    for vol in volumes:
        if str(vol.get("role") or "").lower() != "snap":
            continue
        source = str(vol.get("source_volume") or "").strip()
        snap_name = str(vol.get("name") or "").strip()
        if source and snap_name and source not in linked_snap_by_source:
            linked_snap_by_source[source] = snap_name
    for vol in list(volumes):
        role = str(vol.get("role") or "source").lower()
        name = str(vol.get("name") or "")
        if role == "snap" or name.endswith(SNAP_SUFFIX):
            continue
        if name in linked_snap_by_source:
            target = linked_snap_by_source[name]
        else:
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
                linked_snap_by_source[name] = target
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


def _resolve_snap_target(source_name: str, volumes: list, by_name: dict) -> dict | None:
    for vol in volumes:
        if (
            isinstance(vol, dict)
            and str(vol.get("role") or "").lower() == "snap"
            and str(vol.get("source_volume") or "") == source_name
        ):
            return vol
    return by_name.get(snap_volume_name(source_name))


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
        target = _resolve_snap_target(source_name, volumes, by_name)
        target_name = str(target.get("name") or "") if isinstance(target, dict) else ""
        snap_maps = [
            mapping
            for mapping in maps
            if isinstance(mapping, dict)
            and target_name
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
        target = _resolve_snap_target(source_name, volumes, by_name)
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


def group_matches_card(group: dict, card: dict) -> bool:
    card_candidates: list[str] = []
    card_name = str(card.get("name") or "").strip().lower()
    if card_name:
        card_candidates.append(card_name)
        card_candidates.append(_slugify(card_name))
    card_id = str(card.get("id") or "").strip().lower()
    if card_id:
        card_candidates.append(card_id)
        card_candidates.append(_slugify(card_id))
    if not card_candidates:
        return False
    group_fields = [
        str(group.get("id") or "").strip().lower(),
        str(group.get("name") or "").strip().lower(),
        str(group.get("location") or "").strip().lower(),
        str(group.get("storage_hint") or "").strip().lower(),
        _slugify(str(group.get("name") or "")),
    ]
    return any(candidate in group_fields for candidate in card_candidates)


def stub_group_for_card(card: dict, existing: list[dict]) -> dict:
    card_name = str(card.get("name") or "").strip()
    group_id = new_group_id(card_name, existing)
    stub = normalize_group(
        {
            "id": group_id,
            "name": card_name,
            "location": card_name,
            "storage_hint": card_name,
            "notes": "",
            "updated_at": "",
            "hosts": [],
            "volumes": [],
            "maps": [],
        }
    )
    return stub or {
        "id": group_id,
        "name": card_name,
        "location": card_name,
        "storage_hint": card_name,
        "notes": "",
        "updated_at": "",
        "hosts": [],
        "volumes": [],
        "maps": [],
    }


def ensure_groups_for_cards(groups: list[dict], cards: list[dict]) -> list[dict]:
    out = list(groups)
    for card in cards:
        card_name = str(card.get("name") or "").strip()
        if not card_name:
            continue
        if any(group_matches_card(group, card) for group in out):
            continue
        out.append(stub_group_for_card(card, out))
    return normalize_groups(out)


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
