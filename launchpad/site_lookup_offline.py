"""Persisted Site Lookup offline snapshots (settings-backed)."""

from __future__ import annotations

from typing import Any

SITE_LOOKUP_OFFLINE_SETTING = "site_lookup_offline_inventory"


def normalize_snapshot(raw: dict | None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    try:
        card_id = int(raw.get("card_id") if raw.get("card_id") is not None else (raw.get("card") or {}).get("id"))
    except (TypeError, ValueError):
        return None
    card = raw.get("card") if isinstance(raw.get("card"), dict) else {}
    return {
        "card_id": card_id,
        "card": {
            "id": card_id,
            "name": str(card.get("name") or raw.get("name") or ""),
            "host": str(card.get("host") or raw.get("host") or ""),
            "model": str(card.get("model") or ""),
            "device_profile": str(card.get("device_profile") or raw.get("device_profile") or ""),
            "serial": str(card.get("serial") or card.get("serial_number") or ""),
        },
        "hosts": list(raw.get("hosts") or []) if isinstance(raw.get("hosts"), list) else [],
        "volumes": list(raw.get("volumes") or []) if isinstance(raw.get("volumes"), list) else [],
        "mappings": list(raw.get("mappings") or []) if isinstance(raw.get("mappings"), list) else [],
        "consistency_groups": (
            list(raw.get("consistency_groups") or [])
            if isinstance(raw.get("consistency_groups"), list)
            else []
        ),
        "pools": list(raw.get("pools") or []) if isinstance(raw.get("pools"), list) else [],
        "refreshed_at": str(raw.get("refreshed_at") or "").strip() or None,
    }


def normalize_store(raw: Any) -> dict[str, dict]:
    if isinstance(raw, dict):
        out: dict[str, dict] = {}
        for key, value in raw.items():
            cleaned = normalize_snapshot(value)
            if cleaned is not None:
                out[str(cleaned["card_id"])] = cleaned
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


def snapshot_from_live_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    card = payload.get("card") if isinstance(payload.get("card"), dict) else {}
    try:
        card_id = int(card.get("id"))
    except (TypeError, ValueError):
        return None
    return normalize_snapshot(
        {
            "card_id": card_id,
            "card": card,
            "hosts": payload.get("hosts") or [],
            "volumes": payload.get("volumes") or [],
            "mappings": payload.get("mappings") or [],
            "consistency_groups": payload.get("consistency_groups") or [],
            "pools": payload.get("pools") or [],
            "refreshed_at": payload.get("refreshed_at"),
        }
    )
