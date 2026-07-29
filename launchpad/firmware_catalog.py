"""Per-device_profile firmware release catalogs and behind-count helpers."""

from __future__ import annotations

import json
from typing import Any

from launchpad.storage_presets import HPE_SHELL_PROFILES, SVC_PROFILES

FIRMWARE_CATALOG_SETTING = "firmware_catalog"
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
