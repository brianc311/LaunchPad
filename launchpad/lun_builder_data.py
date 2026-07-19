"""LUN Builder build seeds, normalization, expand, and validation helpers."""

from __future__ import annotations

import re
from typing import Any

from launchpad.storage_presets import (
    DEVICE_PROFILES,
    HP_3PAR_PROFILES,
    SVC_PROFILES,
)

LUN_BUILDS_SETTING = "lun_builds"

_LUN_BUILDER_PROFILE_KEYS: tuple[str, ...] = (
    "hpe_3par_8200",
    "hpe_3par_8450",
    "hpe_primera_600",
    "ibm_ds8884",
    "flashsystem_5200",
    "flashsystem_7200",
    "flashsystem_7300",
    "flashsystem_9200",
    "flashsystem_9500",
    "ibm_svc_2145",
    "ibm_storwize_v7000",
    "ibm_storwize_v7000_g2",
    "ibm_storwize_v7000_g3",
    "ibm_xiv_114",
    "ibm_xiv_gen3",
)

LUN_BUILDER_PROFILES: list[tuple[str, str]] = [
    (key, DEVICE_PROFILES[key]) for key in _LUN_BUILDER_PROFILE_KEYS
]

_LIVE_RUN_PROFILES = frozenset(
    SVC_PROFILES | HP_3PAR_PROFILES | frozenset({"hpe_primera_600"})
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def supports_live_run(profile_key: str) -> bool:
    return str(profile_key or "").strip() in _LIVE_RUN_PROFILES


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    return text in ("1", "true", "yes", "y", "on")


def _normalize_count(value: Any) -> int:
    if value is None or value == "":
        return 1
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_str_list(raw: Any) -> list[str]:
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.replace(";", ",").split(",")]
        return [part for part in parts if part]
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def normalize_host_row(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    lpar_name = str(raw.get("lpar_name") or "").strip()
    if not lpar_name:
        return None
    slot_raw = raw.get("slot")
    slot = str(slot_raw).strip() if slot_raw is not None else ""
    remote_slot_raw = raw.get("remote_slot")
    remote_slot = (
        str(remote_slot_raw).strip() if remote_slot_raw is not None else ""
    )
    return {
        "lpar_name": lpar_name,
        "slot": slot,
        "state": str(raw.get("state") or "").strip(),
        "required": _as_bool(raw.get("required")),
        "type": str(raw.get("type") or "").strip(),
        "remote_lpar": str(raw.get("remote_lpar") or "").strip(),
        "remote_slot": remote_slot,
        "wwpn1": str(raw.get("wwpn1") or "").strip(),
        "wwpn2": str(raw.get("wwpn2") or "").strip(),
        "physical_fc_slot": str(raw.get("physical_fc_slot") or "").strip(),
        "managed_system_name": str(raw.get("managed_system_name") or "").strip(),
        "managed_system_serial": str(
            raw.get("managed_system_serial") or ""
        ).strip(),
        "notes": str(raw.get("notes") or "").strip(),
    }


def normalize_lun_row(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    purpose = str(raw.get("purpose") or raw.get("name") or "").strip()
    return {
        "purpose": purpose,
        "count": _normalize_count(raw.get("count")),
        "size": str(raw.get("size") or "").strip(),
        "shared": _as_bool(raw.get("shared")),
        "storage_profile": str(raw.get("storage_profile") or "").strip(),
        "pool_or_cpg": str(raw.get("pool_or_cpg") or "").strip(),
        "host_names": _normalize_str_list(raw.get("host_names")),
        "scsi_or_lun_id": str(raw.get("scsi_or_lun_id") or "").strip(),
        "card_hint": str(raw.get("card_hint") or "").strip(),
        "cluster": str(raw.get("cluster") or raw.get("group") or "").strip(),
    }


def normalize_build(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    build_id = str(raw.get("id") or "").strip()
    if not build_id:
        return None
    hosts_raw = raw.get("hosts") or []
    luns_raw = raw.get("luns") or []
    hosts: list[dict[str, Any]] = []
    if isinstance(hosts_raw, list):
        for item in hosts_raw:
            cleaned = normalize_host_row(item)
            if cleaned:
                hosts.append(cleaned)
    luns: list[dict[str, Any]] = []
    if isinstance(luns_raw, list):
        for item in luns_raw:
            cleaned = normalize_lun_row(item)
            if cleaned is not None:
                luns.append(cleaned)
    return {
        "id": build_id,
        "name": str(raw.get("name") or "").strip(),
        "location": str(raw.get("location") or "").strip(),
        "notes": str(raw.get("notes") or "").strip(),
        "updated_at": str(raw.get("updated_at") or "").strip(),
        "hosts": hosts,
        "luns": luns,
    }


def normalize_builds(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        cleaned = normalize_build(item)
        if cleaned is not None:
            out.append(cleaned)
    return out


def upsert_build(builds: list[dict], build: dict) -> list[dict]:
    build_id = str(build.get("id") or "").strip()
    result: list[dict] = []
    replaced = False
    for existing in builds:
        if str(existing.get("id") or "").strip() == build_id:
            result.append(build)
            replaced = True
        else:
            result.append(existing)
    if not replaced:
        result.append(build)
    return result


def delete_build(builds: list[dict], build_id: str) -> list[dict]:
    target = str(build_id or "").strip()
    return [b for b in builds if str(b.get("id") or "").strip() != target]


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "build"


def new_build_id(name: str, existing: list[dict]) -> str:
    taken = {str(b.get("id") or "").strip() for b in existing}
    base = _slugify(name)
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def expand_lun_batch(lun: dict) -> list[dict]:
    purpose = str(lun.get("purpose") or "").strip()
    count = _normalize_count(lun.get("count"))
    if count < 1:
        count = 1
    size = str(lun.get("size") or "").strip()
    pool_or_cpg = str(lun.get("pool_or_cpg") or "").strip()
    shared = _as_bool(lun.get("shared"))
    storage_profile = str(lun.get("storage_profile") or "").strip()
    host_names = _normalize_str_list(lun.get("host_names"))
    scsi_or_lun_id = str(lun.get("scsi_or_lun_id") or "").strip()
    card_hint = str(lun.get("card_hint") or "").strip()
    cluster = str(lun.get("cluster") or "").strip()
    rows: list[dict] = []
    for index in range(count):
        if count == 1:
            name = purpose
        else:
            name = f"{purpose}_{index + 1:02d}"
        rows.append(
            {
                "name": name,
                "size": size,
                "pool_or_cpg": pool_or_cpg,
                "shared": shared,
                "storage_profile": storage_profile,
                "host_names": list(host_names),
                "scsi_or_lun_id": scsi_or_lun_id,
                "card_hint": card_hint,
                "cluster": cluster,
                "source_batch": purpose,
            }
        )
    return rows


def validate_build_for_preview(build: dict | None) -> list[str]:
    if not isinstance(build, dict):
        return ["Build is required."]
    messages: list[str] = []
    luns = build.get("luns") or []
    if not luns:
        messages.append("At least one LUN spec is required.")
        return messages
    for index, lun in enumerate(luns, start=1):
        if not isinstance(lun, dict):
            messages.append(f"LUN row {index}: invalid row.")
            continue
        prefix = f"LUN row {index}"
        purpose = str(lun.get("purpose") or "").strip()
        if not purpose:
            messages.append(f"{prefix}: purpose is required.")
        count = lun.get("count")
        try:
            count_value = int(count)
        except (TypeError, ValueError):
            count_value = 0
        if count_value < 1:
            messages.append(f"{prefix}: count must be at least 1.")
        if not str(lun.get("size") or "").strip():
            messages.append(f"{prefix}: size is required.")
        if not str(lun.get("pool_or_cpg") or "").strip():
            messages.append(f"{prefix}: pool_or_cpg is required.")
        if not str(lun.get("storage_profile") or "").strip():
            messages.append(f"{prefix}: storage_profile is required.")
    return messages
