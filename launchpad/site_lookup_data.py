"""Pure helpers for Site Lookup payloads."""

from __future__ import annotations

from typing import Any

from launchpad.flashsystem_fc import (
    parse_fc_hosts,
    parse_host_lun_maps,
    parse_lsvdisk_volumes,
)
from launchpad.storage_presets import HPE_SHELL_PROFILES
from launchpad.volume_find import (
    parse_showhost_hosts,
    parse_showhost_pathsum_status,
    parse_showvv_volumes,
    apply_pathsum_status_to_hosts,
)


def _command_blob(item: dict) -> str:
    return f"{item.get('label') or ''} {item.get('command') or ''}".lower()


def shape_volumes_for_lookup(rows: list[dict]) -> list[dict[str, Any]]:
    shaped: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        shaped.append(
            {
                "name": name,
                "uid": str(row.get("uid") or row.get("vdisk_UID") or ""),
                "capacity": str(row.get("capacity") or ""),
                "pool": str(
                    row.get("pool")
                    or row.get("pool_or_cpg")
                    or row.get("mdisk_grp_name")
                    or ""
                ),
                "status": str(row.get("status") or row.get("state") or ""),
            }
        )
    return shaped


def shape_hosts_for_lookup(rows: list[dict]) -> list[dict[str, Any]]:
    shaped: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("host_name") or row.get("name") or "").strip()
        if not name:
            continue
        wwpns = str(row.get("wwpns") or "").split()
        port_count = str(row.get("port_count") or row.get("ports") or "").strip()
        if not port_count and wwpns:
            port_count = str(len(wwpns))
        shaped.append(
            {
                "host_name": name,
                "name": name,
                "status": str(row.get("status") or row.get("state") or ""),
                "type": str(row.get("type") or row.get("host_type") or row.get("persona") or ""),
                "port_count": port_count,
                "ports": port_count,
                "protocol": str(row.get("protocol") or "SCSI"),
                "wwpns": " ".join(wwpns),
            }
        )
    return shaped


def showvv_inventory_note(
    command_results: list[dict] | None,
    *,
    raw_showvv: str | None = None,
) -> str | None:
    """Explain why HPE volumes may be empty (failed / empty / unparseable showvv)."""
    if raw_showvv is not None:
        text = str(raw_showvv or "").strip()
        if not text:
            return "Volumes empty because showvv returned no output"
        if "permission denied" in text.lower():
            return "Volumes empty because showvv returned Permission denied"
        return (
            "Volumes empty because showvv output could not be parsed "
            "(unexpected table format)"
        )
    for item in command_results or []:
        if not isinstance(item, dict):
            continue
        cmd = _command_blob(item)
        if "showvv" not in cmd:
            continue
        err = str(item.get("error") or "").strip()
        output = str(item.get("output") or "").strip()
        if err:
            return f"Volumes empty because showvv failed: {err}"
        if output and "permission denied" in output.lower():
            return "Volumes empty because showvv returned Permission denied"
        if not output:
            return "Volumes empty because showvv returned no output"
        return (
            "Volumes empty because showvv output could not be parsed "
            "(unexpected table format)"
        )
    return "Volumes empty — showvv not in cached results; use Live Refresh"


def inventory_from_command_results(
    command_results: list[dict] | None,
    *,
    device_profile: str = "",
) -> tuple[list[dict], list[dict], list[dict]]:
    """Parse hosts, volumes, and maps from health SSH command results.

    Supports IBM Spectrum Virtualize (lshost / lsvdisk / maps) and HPE 3PAR/Primera
    (showhost / showvv).
    """
    hosts: list[dict] = []
    volumes: list[dict] = []
    maps: list[dict] = []
    path_status: dict[str, str] = {}
    profile = str(device_profile or "").strip()
    is_hpe = profile in HPE_SHELL_PROFILES or profile.startswith("hpe_")

    for item in command_results or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        cmd = _command_blob(item)
        output = str(item.get("output") or "")
        if not output.strip():
            continue
        if is_hpe or "showhost" in cmd or "showvv" in cmd:
            if "showhost" in cmd and "pathsum" in cmd:
                path_status = parse_showhost_pathsum_status(output) or path_status
            elif not hosts and "showhost" in cmd:
                hosts = shape_hosts_for_lookup(parse_showhost_hosts(output))
            if not volumes and "showvv" in cmd:
                volumes = shape_volumes_for_lookup(parse_showvv_volumes(output))
        if not hosts and ("lshost" in cmd and "vdisk" not in cmd):
            hosts = shape_hosts_for_lookup(parse_fc_hosts(output))
        if (
            not volumes
            and "lsvdisk" in cmd
            and "lshostvdiskmap" not in cmd
            and "lsvdiskhostmap" not in cmd
        ):
            volumes = shape_volumes_for_lookup(parse_lsvdisk_volumes(output))
        if not maps and (
            "lshostvdiskmap" in cmd or "lsvdiskhostmap" in cmd or "host lun" in cmd
        ):
            maps = parse_host_lun_maps(output)

    if hosts and path_status:
        apply_pathsum_status_to_hosts(hosts, path_status)

    return hosts, volumes, maps


def filter_lookup_cards(cards: list[dict]) -> list[dict]:
    out: list[dict] = []
    for card in cards:
        if card.get("id") is None:
            continue
        name = str(card.get("name") or "").strip()
        if not name:
            continue
        out.append(card)
    return out


def match_contingency_groups(groups: list[dict], *, card_name: str) -> list[dict]:
    needle = (card_name or "").strip().lower()
    if not needle:
        return []
    matched: list[dict] = []
    for group in groups or []:
        hay = " ".join(
            [
                str(group.get("name") or ""),
                str(group.get("storage_hint") or ""),
                str(group.get("location") or ""),
            ]
        ).lower()
        if needle in hay or hay.find(needle) >= 0 or any(
            needle in str(group.get(k) or "").lower() for k in ("name", "storage_hint", "location")
        ):
            # Prefer exact-ish: storage_hint or name equals card, or card name contained in hint/name
            hint = str(group.get("storage_hint") or "").strip().lower()
            gname = str(group.get("name") or "").strip().lower()
            if needle == hint or needle == gname or needle in hint or needle in gname or hint in needle:
                matched.append(group)
    return matched


def _card_meta(card: dict) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "name": card.get("name") or "",
        "host": card.get("host") or "",
        "model": card.get("model") or "",
        "device_profile": card.get("device_profile") or "",
        "serial": card.get("serial_number") or card.get("serial") or "",
    }


def _shape_pools(pools: list[dict] | None) -> list[dict[str, Any]]:
    shaped: list[dict[str, Any]] = []
    for pool in pools or []:
        if not isinstance(pool, dict):
            continue
        name = str(pool.get("name") or "").strip()
        if not name:
            continue
        shaped.append(
            {
                "name": name,
                "total_bytes": pool.get("total_bytes"),
                "used_bytes": pool.get("used_bytes"),
                "free_bytes": pool.get("free_bytes"),
                "used_pct": pool.get("used_pct"),
            }
        )
    return shaped


def _volumes_from_maps_and_cgs(maps: list[dict], cgs: list[dict]) -> list[dict]:
    names: dict[str, dict] = {}
    for row in maps or []:
        vname = str(row.get("vdisk_name") or "").strip()
        if vname and vname not in names:
            names[vname] = {"name": vname, "uid": "", "capacity": "", "pool": "", "status": ""}
    for group in cgs or []:
        for vol in group.get("volumes") or []:
            if isinstance(vol, dict):
                vname = str(vol.get("name") or "").strip()
            else:
                vname = str(vol or "").strip()
            if vname and vname not in names:
                names[vname] = {"name": vname, "uid": "", "capacity": "", "pool": "", "status": ""}
    return list(names.values())


def _normalize_cgs(groups: list[dict]) -> list[dict]:
    out: list[dict] = []
    for group in groups or []:
        out.append(
            {
                "id": str(group.get("id") or ""),
                "name": str(group.get("name") or ""),
                "status": str(group.get("status") or ""),
                "location": str(group.get("location") or ""),
                "volumes": group.get("volumes") or [],
                "maps": group.get("maps") or [],
            }
        )
    return out


def _build_payload(
    *,
    card: dict,
    hosts: list[dict],
    volumes: list[dict],
    maps: list[dict],
    consistency_groups: list[dict],
    pools: list[dict],
    source: str,
    refreshed_at: str | None,
    error: str | None = None,
    warning: str | None = None,
) -> dict[str, Any]:
    return {
        "card": _card_meta(card),
        "stats": {
            "hosts": len(hosts),
            "volumes": len(volumes),
            "pools": len(pools),
            "nodes": int(card.get("node_count") or 0),
            "consistency_groups": len(consistency_groups),
        },
        "hosts": hosts,
        "volumes": volumes,
        "mappings": maps,
        "consistency_groups": consistency_groups,
        "pools": pools,
        "source": source,
        "refreshed_at": refreshed_at,
        "error": error,
        "warning": warning,
    }


def payload_has_inventory(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in ("hosts", "volumes", "mappings", "pools", "consistency_groups"):
        rows = payload.get(key)
        if isinstance(rows, list) and rows:
            return True
    return False


def payload_from_offline_snapshot(snapshot: dict) -> dict[str, Any]:
    card = snapshot.get("card") if isinstance(snapshot.get("card"), dict) else {}
    hosts = list(snapshot.get("hosts") or [])
    volumes = list(snapshot.get("volumes") or [])
    maps = list(snapshot.get("mappings") or [])
    cgs = list(snapshot.get("consistency_groups") or [])
    pools = _shape_pools(snapshot.get("pools") if isinstance(snapshot.get("pools"), list) else [])
    return _build_payload(
        card=card,
        hosts=hosts,
        volumes=volumes,
        maps=maps,
        consistency_groups=cgs,
        pools=pools,
        source="offline",
        refreshed_at=snapshot.get("refreshed_at"),
    )


def payload_from_lun_offline(
    snapshot: dict,
    *,
    card: dict | None = None,
) -> dict[str, Any]:
    meta = dict(card or {})
    if not meta.get("id"):
        meta["id"] = snapshot.get("card_id")
    if not meta.get("name"):
        meta["name"] = snapshot.get("site_name") or ""
    if not meta.get("host"):
        meta["host"] = snapshot.get("host") or ""
    if not meta.get("device_profile"):
        meta["device_profile"] = snapshot.get("device_profile") or ""
    hosts = list(snapshot.get("hosts") or []) if isinstance(snapshot.get("hosts"), list) else []
    volumes = list(snapshot.get("volumes") or []) if isinstance(snapshot.get("volumes"), list) else []
    return _build_payload(
        card=meta,
        hosts=hosts,
        volumes=volumes,
        maps=[],
        consistency_groups=[],
        pools=[],
        source="offline_lun",
        refreshed_at=str(snapshot.get("updated_at") or "").strip() or None,
    )


def payload_from_card_cache(
    card: dict,
    *,
    contingency_groups: list[dict] | None = None,
    command_results: list[dict] | None = None,
) -> dict[str, Any]:
    hosts = shape_hosts_for_lookup(list(card.get("fc_hosts") or []))
    maps = list(card.get("fc_mappings") or [])
    pools = _shape_pools(card.get("pools") if isinstance(card.get("pools"), list) else [])
    matched = match_contingency_groups(contingency_groups or [], card_name=str(card.get("name") or ""))
    cgs = _normalize_cgs(matched)
    parsed_hosts, parsed_volumes, parsed_maps = inventory_from_command_results(
        command_results,
        device_profile=str(card.get("device_profile") or ""),
    )
    if not hosts and parsed_hosts:
        hosts = parsed_hosts
    if not maps and parsed_maps:
        maps = parsed_maps
    volumes = (
        list(parsed_volumes)
        if parsed_volumes
        else _volumes_from_maps_and_cgs(maps, matched)
    )
    profile = str(card.get("device_profile") or "")
    is_hpe = profile in HPE_SHELL_PROFILES or profile.startswith("hpe_")
    warning = None
    if is_hpe and not volumes:
        warning = showvv_inventory_note(command_results)
    return _build_payload(
        card=card,
        hosts=hosts,
        volumes=volumes,
        maps=maps,
        consistency_groups=cgs,
        pools=pools,
        source="cache",
        refreshed_at=None,
        warning=warning,
    )


def payload_from_live(
    *,
    card: dict,
    hosts: list[dict],
    volumes: list[dict],
    maps: list[dict],
    consist_groups: list[dict],
    pools: list[dict] | None = None,
    contingency_groups: list[dict] | None = None,
    refreshed_at: str | None = None,
    warning: str | None = None,
) -> dict[str, Any]:
    shaped_pools = _shape_pools(pools if pools is not None else card.get("pools"))
    if consist_groups:
        cgs = _normalize_cgs(consist_groups)
        source = "ssh"
    else:
        matched = match_contingency_groups(
            contingency_groups or [], card_name=str(card.get("name") or "")
        )
        cgs = _normalize_cgs(matched)
        source = "ssh+cg_fallback" if cgs else "ssh"
    vols = list(volumes) if volumes else _volumes_from_maps_and_cgs(maps, cgs)
    return _build_payload(
        card=card,
        hosts=list(hosts or []),
        volumes=vols,
        maps=list(maps or []),
        consistency_groups=cgs,
        pools=shaped_pools,
        source=source,
        refreshed_at=refreshed_at,
        warning=warning,
    )
