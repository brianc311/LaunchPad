"""Build preview/create CLI steps for contingency group _snap copies."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from launchpad.flashsystem_fc import _get, _table_records

_SIZE_RE = re.compile(
    r"^(-?\d+(?:\.\d+)?)\s*(TiB|TB|GB|MB|KB|PB|B)?$",
    re.IGNORECASE,
)
_FCMAP_MAX_LEN = 63
_SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_]+")
_CLI_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass
class SnapStep:
    kind: str
    purpose: str
    cmd: str
    skip: bool = False
    reason: str = ""


def cli_token(value: str) -> str:
    """Return a safe unquoted FlashSystem CLI token."""
    token = str(value or "").strip()
    if not token:
        raise ValueError("Unsafe empty CLI token")
    if not _CLI_TOKEN_RE.fullmatch(token):
        raise ValueError(f"Unsafe CLI token: {token!r}")
    return token


def parse_capacity_to_gb(capacity: str) -> float | None:
    raw = (capacity or "").strip().replace(",", "")
    if not raw:
        return None
    match = _SIZE_RE.match(raw)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "B").upper()
    if unit == "TIB":
        return amount * 1024
    multipliers_to_gb = {
        "B": 1 / (1024**3),
        "KB": 1 / (1024**2),
        "MB": 1 / 1024,
        "GB": 1,
        "TB": 1024,
        "PB": 1024**2,
    }
    return amount * multipliers_to_gb.get(unit, 1 / (1024**3))


def safe_fcmap_name(source: str, target: str) -> str:
    source_token = _SAFE_TOKEN_RE.sub("_", str(source or "").strip()) or "src"
    target_token = _SAFE_TOKEN_RE.sub("_", str(target or "").strip()) or "tgt"
    name = f"fc_{source_token}_to_{target_token}"
    if len(name) > _FCMAP_MAX_LEN:
        name = name[:_FCMAP_MAX_LEN]
    return name


def parse_lsvdisk_names(output: str) -> set[str]:
    names: set[str] = set()
    for record in _table_records(output):
        name = _get(record, "name")
        if name:
            names.add(name)
    return names


def parse_lsfcmap_names(output: str) -> set[str]:
    names: set[str] = set()
    for record in _table_records(output):
        name = _get(record, "name")
        if name:
            names.add(name)
    return names


def parse_lshostvdiskmap_keys(output: str) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for record in _table_records(output):
        host = _get(record, "host_name", "host")
        vdisk = _get(record, "vdisk_name", "volume_name", "vdisk")
        if host and not vdisk:
            vdisk = _get(record, "name")
        elif vdisk and not host:
            host = _get(record, "name")
        scsi = _get(record, "SCSI_id", "scsi_id", "lun", "UID")
        if host and vdisk:
            keys.add((host, scsi, vdisk))
    return keys


def _inventory_sets(inventory: dict[str, Any] | None) -> tuple[set[str], set[str], set[tuple[str, str, str]]]:
    inv = inventory or {}
    vdisks = set(inv.get("vdisks") or [])
    fcmaps = set(inv.get("fcmaps") or [])
    hostmaps = set(inv.get("hostmaps") or [])
    return vdisks, fcmaps, hostmaps


def build_snap_steps(
    group: dict,
    *,
    inventory: dict | None = None,
) -> tuple[list[SnapStep], list[str]]:
    warnings: list[str] = []
    steps: list[SnapStep] = []

    storage_hint = str(group.get("storage_hint") or "").strip()
    if not storage_hint:
        warnings.append("Missing storage_hint; cannot resolve target array")

    vdisks, fcmaps, hostmaps = _inventory_sets(inventory)
    volumes = group.get("volumes") or []
    maps = group.get("maps") or []

    snap_volumes = [
        v
        for v in volumes
        if isinstance(v, dict) and str(v.get("role") or "").lower() == "snap"
    ]

    for snap_vol in snap_volumes:
        snap_name = str(snap_vol.get("name") or "").strip()
        source_name = str(snap_vol.get("source_volume") or "").strip()
        pool = str(snap_vol.get("pool") or "").strip()
        capacity = str(snap_vol.get("capacity") or "").strip()
        try:
            snap_name = cli_token(snap_name)
            source_name = cli_token(source_name)
        except ValueError as exc:
            warnings.append(str(exc))
            continue
        try:
            pool = cli_token(pool) if pool else ""
        except ValueError as exc:
            warnings.append(str(exc))
            pool = ""

        if inventory is not None and source_name not in vdisks:
            warnings.append(f"Source volume {source_name} not found on array")

        needs_create = snap_name not in vdisks
        size_gb = parse_capacity_to_gb(capacity)

        if needs_create:
            if not pool:
                warnings.append(f"Missing pool for snap volume {snap_name}")
            if size_gb is None:
                warnings.append(
                    f"Missing or invalid size/capacity for snap volume {snap_name}"
                )

        if needs_create and pool and size_gb is not None:
            size_value = int(size_gb) if size_gb == int(size_gb) else size_gb
            mkvdisk_cmd = (
                f"svctask mkvdisk -name {snap_name} -mdiskgrp {pool} "
                f"-size {size_value} -unit gb"
            )
            steps.append(
                SnapStep(
                    kind="mkvdisk",
                    purpose="create target volume",
                    cmd=mkvdisk_cmd,
                )
            )
        else:
            size_value = int(size_gb) if size_gb is not None and size_gb == int(size_gb) else 0
            mkvdisk_cmd = (
                f"svctask mkvdisk -name {snap_name} -mdiskgrp {pool or 'POOL'} "
                f"-size {size_value} -unit gb"
            )
            steps.append(
                SnapStep(
                    kind="mkvdisk",
                    purpose="create target volume",
                    cmd=mkvdisk_cmd,
                    skip=not needs_create,
                    reason="target volume already exists" if not needs_create else "",
                )
            )

        fc_name = cli_token(safe_fcmap_name(source_name, snap_name))
        fcmap_cmd = (
            f"svctask mkfcmap -source {source_name} -target {snap_name} -name {fc_name}"
        )
        skip_fcmap = fc_name in fcmaps
        steps.append(
            SnapStep(
                kind="mkfcmap",
                purpose="create FlashCopy map",
                cmd=fcmap_cmd,
                skip=skip_fcmap,
                reason="FlashCopy map already exists" if skip_fcmap else "",
            )
        )

        steps.append(
            SnapStep(
                kind="startfcmap",
                purpose="start FlashCopy",
                cmd=f"svctask startfcmap {fc_name}",
                skip=skip_fcmap,
                reason="FlashCopy map already exists" if skip_fcmap else "",
            )
        )

        snap_maps = [
            m
            for m in maps
            if isinstance(m, dict)
            and str(m.get("volume") or "") == snap_name
            and str(m.get("role") or "").lower() == "snap"
        ]
        for mapping in snap_maps:
            host = str(mapping.get("host") or "").strip()
            scsi_id = str(mapping.get("scsi_id") or "").strip()
            try:
                host = cli_token(host)
                scsi_id = cli_token(scsi_id)
            except ValueError as exc:
                warnings.append(str(exc))
                continue
            hostmap_key = (host, scsi_id, snap_name)
            skip_hostmap = hostmap_key in hostmaps
            hostmap_cmd = f"svctask mkvdiskhostmap -host {host} -scsi {scsi_id} {snap_name}"
            steps.append(
                SnapStep(
                    kind="hostmap",
                    purpose="map snap volume to host",
                    cmd=hostmap_cmd,
                    skip=skip_hostmap,
                    reason="host map already exists" if skip_hostmap else "",
                )
            )

    return steps, warnings


def resolve_card_by_storage_hint(
    cards: list[Any],
    hint: str,
) -> Any | None:
    normalized_hint = str(hint or "").strip().casefold()
    if not normalized_hint:
        return None
    for card in cards:
        name = card.get("name") if isinstance(card, dict) else getattr(card, "name", "")
        if str(name or "").strip().casefold() == normalized_hint:
            return card
    return None


def collect_inventory(run_cmd: Callable[[str], str]) -> dict[str, set[Any]]:
    commands = {
        "vdisks": ("svcinfo lsvdisk -delim :", "svcinfo lsvdisk"),
        "fcmaps": ("svcinfo lsfcmap -delim :", "svcinfo lsfcmap"),
        "hostmaps": (
            "svcinfo lshostvdiskmap -delim :",
            "svcinfo lshostvdiskmap",
        ),
    }
    parsers = {
        "vdisks": parse_lsvdisk_names,
        "fcmaps": parse_lsfcmap_names,
        "hostmaps": parse_lshostvdiskmap_keys,
    }
    inventory: dict[str, set[Any]] = {}
    for key, (delimited, fallback) in commands.items():
        output = run_cmd(delimited)
        if not output.strip():
            output = run_cmd(fallback)
        inventory[key] = parsers[key](output)
    return inventory


def run_snap_steps(
    steps: list[SnapStep],
    run_cmd: Callable[[str], str],
) -> dict[str, Any]:
    log: list[dict[str, Any]] = []
    for step in steps:
        entry = {
            "kind": step.kind,
            "purpose": step.purpose,
            "cmd": step.cmd,
            "skipped": step.skip,
        }
        if step.skip:
            entry["reason"] = step.reason
            log.append(entry)
            continue
        try:
            entry["output"] = run_cmd(step.cmd)
        except Exception as exc:
            entry["ok"] = False
            entry["error"] = str(exc)
            log.append(entry)
            return {"ok": False, "log": log, "warnings": []}
        entry["ok"] = True
        log.append(entry)
    return {"ok": True, "log": log, "warnings": []}
