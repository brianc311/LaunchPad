"""Persisted vCenters directory (settings-backed JSON list)."""

from __future__ import annotations

import json
import uuid
from typing import Any

SETTING_VCENTERS_DIRECTORY = "vcenters_directory"


def vcenter_default_url(address: str) -> str:
    return f"https://{str(address).strip()}/ui"


def effective_vcenter_url(record: dict) -> str:
    override = str(record.get("url") or "").strip()
    if override:
        return override
    return vcenter_default_url(str(record.get("address") or ""))


def normalize_vcenter(raw: dict, *, assign_id: bool = False) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("vCenter must be an object")
    name = str(raw.get("name") or "").strip()
    location = str(raw.get("location") or "").strip()
    address = str(raw.get("address") or "").strip()
    url = str(raw.get("url") or "").strip()
    if not name:
        raise ValueError("name is required")
    if not address:
        raise ValueError("address is required")
    if "://" in address:
        raise ValueError("address must be an IP or hostname")
    if url and not (
        url.lower().startswith("http://") or url.lower().startswith("https://")
    ):
        raise ValueError("url must start with http:// or https://")
    record_id = str(raw.get("id") or "").strip()
    if not record_id:
        if not assign_id:
            raise ValueError("id is required")
        record_id = uuid.uuid4().hex
    return {
        "id": record_id,
        "name": name,
        "location": location,
        "address": address,
        "url": url,
    }


def normalize_vcenters(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(normalize_vcenter(item, assign_id=True))
        except ValueError:
            continue
    out.sort(key=lambda row: row["name"].casefold())
    return out


def parse_vcenters_setting(raw: str | None) -> list[dict]:
    text = str(raw or "").strip() or "[]"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return normalize_vcenters(parsed)


def upsert_vcenter(store: list[dict], raw: dict) -> list[dict]:
    cleaned = normalize_vcenter(raw, assign_id=True)
    by_id = {row["id"]: row for row in normalize_vcenters(store)}
    by_id[cleaned["id"]] = cleaned
    return normalize_vcenters(list(by_id.values()))


def delete_vcenter(store: list[dict], vcenter_id: str) -> list[dict]:
    target = str(vcenter_id or "").strip()
    kept = [row for row in normalize_vcenters(store) if row["id"] != target]
    return kept
