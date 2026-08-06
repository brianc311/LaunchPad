"""Pure helpers for Site Lookup payloads."""

from __future__ import annotations

from typing import Any


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
) -> dict[str, Any]:
    hosts = list(card.get("fc_hosts") or [])
    maps = list(card.get("fc_mappings") or [])
    pools = _shape_pools(card.get("pools") if isinstance(card.get("pools"), list) else [])
    matched = match_contingency_groups(contingency_groups or [], card_name=str(card.get("name") or ""))
    cgs = _normalize_cgs(matched)
    volumes = _volumes_from_maps_and_cgs(maps, matched)
    return _build_payload(
        card=card,
        hosts=hosts,
        volumes=volumes,
        maps=maps,
        consistency_groups=cgs,
        pools=pools,
        source="cache",
        refreshed_at=None,
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
    )
