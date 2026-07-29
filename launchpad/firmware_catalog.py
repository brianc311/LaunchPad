"""Per-device_profile firmware release catalogs and behind-count helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from launchpad.storage_presets import HPE_SHELL_PROFILES, SVC_PROFILES

FIRMWARE_CATALOG_SETTING = "firmware_catalog"
FIRMWARE_AUTO_ADD_SETTING = "firmware_auto_add_from_scans"
_DS8884 = "ibm_ds8884"


def eligible_firmware_profiles() -> list[str]:
    return sorted(set(SVC_PROFILES) | set(HPE_SHELL_PROFILES) | {_DS8884})


def normalize_catalog(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key, value in raw.items():
        profile = str(key or "").strip().lower()
        if not profile:
            continue
        seen: set[str] = set()
        ordered: list[str] = []
        items = value if isinstance(value, list) else []
        for item in items:
            version = str(item or "").strip()
            if not version or version in seen:
                continue
            seen.add(version)
            ordered.append(version)
        out[profile] = ordered
    return out


def load_firmware_catalog(db) -> dict[str, list[str]]:
    raw = db.get_setting(FIRMWARE_CATALOG_SETTING, "") or ""
    if not str(raw).strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return normalize_catalog(parsed)


def save_firmware_catalog(db, catalog: dict[str, list[str]]) -> dict[str, list[str]]:
    normalized = normalize_catalog(catalog)
    db.set_setting(FIRMWARE_CATALOG_SETTING, json.dumps(normalized))
    return normalized


def get_profile_catalog(catalog: dict[str, list[str]], profile: str) -> list[str]:
    key = str(profile or "").strip().lower()
    return list(catalog.get(key) or [])


def latest_in_catalog(versions: list[str]) -> str:
    return versions[-1] if versions else ""


def versions_behind(current: str, versions: list[str]) -> str:
    cur = str(current or "").strip()
    if not cur or not versions:
        return "unknown"
    try:
        idx = versions.index(cur)
    except ValueError:
        return "unknown"
    return str(len(versions) - idx - 1)


def load_firmware_auto_add(db) -> bool:
    raw = str(db.get_setting(FIRMWARE_AUTO_ADD_SETTING, "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def save_firmware_auto_add(db, enabled: bool) -> bool:
    value = bool(enabled)
    db.set_setting(FIRMWARE_AUTO_ADD_SETTING, "true" if value else "false")
    return value


def version_sort_key(version: str) -> tuple:
    parts = re.split(r"(\d+)", str(version or "").strip())
    key = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return tuple(key)


def insert_version_sorted(versions: list[str], new_version: str) -> tuple[list[str], bool]:
    new_v = str(new_version or "").strip()
    out = list(versions)
    if not new_v or new_v in out:
        return out, False
    new_key = version_sort_key(new_v)
    idx = 0
    while idx < len(out) and version_sort_key(out[idx]) <= new_key:
        idx += 1
    out.insert(idx, new_v)
    return out, True


def grow_catalog_from_currents(
    catalog: dict[str, list[str]],
    currents: list[tuple[str, str]],
) -> tuple[dict[str, list[str]], int]:
    updated = {k: list(v) for k, v in (catalog or {}).items()}
    inserted = 0
    for profile, current in currents:
        profile_key = str(profile or "").strip().lower()
        cur = str(current or "").strip()
        if not profile_key or not cur:
            continue
        existing = list(updated.get(profile_key) or [])
        new_list, did = insert_version_sorted(existing, cur)
        if did:
            updated[profile_key] = new_list
            inserted += 1
    return updated, inserted
