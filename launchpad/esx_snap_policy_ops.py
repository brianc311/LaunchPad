"""IBM ESX-snap snapshot policy + volume group preview/run helpers."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime

from launchpad.contingency_snap_create import SnapStep, cli_token
from launchpad.flashsystem_fc import _get, _table_records

POLICY_NAME = "ESX-snap"
VG_SUFFIX = "_ESX-snap"
VG_MAX_LEN = 63
FIRMWARE_MSG = "Snapshot policies need IBM Storage Virtualize 8.5.1 or later"

_UNSAFE = re.compile(r"[^A-Za-z0-9_]+")
_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


def sanitize_site_token(card_name: str) -> str:
    text = _UNSAFE.sub("_", str(card_name or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "Site"


def default_vg_name(card_name: str) -> str:
    site = sanitize_site_token(card_name)
    max_site = VG_MAX_LEN - len(VG_SUFFIX)
    if len(site) > max_site:
        site = site[:max_site].rstrip("_") or "Site"
        if len(site) > max_site:
            site = site[:max_site]
    return f"{site}{VG_SUFFIX}"


def parse_hhmm(start_time: str) -> tuple[int, int] | None:
    match = _HHMM.fullmatch(str(start_time or "").strip())
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def backup_start_token(start_time: str, *, now: datetime | None = None) -> str:
    parsed = parse_hhmm(start_time)
    if parsed is None:
        raise ValueError("start_time must be HH:MM")
    hour, minute = parsed
    stamp = now or datetime.now()
    return f"{stamp.year % 100:02d}{stamp.month:02d}{stamp.day:02d}{hour:02d}{minute:02d}"


def parse_named_objects(output: str) -> set[str]:
    names: set[str] = set()
    for record in _table_records(output):
        name = _get(record, "name")
        if name:
            names.add(name)
    return names


def parse_lsvdisk_membership(output: str) -> list[dict[str, str]]:
    volumes: list[dict[str, str]] = []
    for record in _table_records(output):
        name = _get(record, "name", "vdisk_name", "volume_name")
        if not name:
            continue
        volumes.append(
            {
                "name": name,
                "capacity": _get(record, "capacity"),
                "volume_group": _get(
                    record, "volume_group", "volume_group_name", "volumegroup"
                ),
            }
        )
    return volumes


def volume_group_of(volume: dict) -> str:
    return str(volume.get("volume_group") or "").strip()


def _canonical_preview_payload(start_time: str, arrays: list[dict]) -> dict:
    canon = []
    for item in arrays:
        names = [str(name) for name in (item.get("volume_names") or [])]
        canon.append(
            {
                "card_id": int(item["card_id"]),
                "vg_name": str(item.get("vg_name") or ""),
                "volume_names": sorted(names),
            }
        )
    canon.sort(key=lambda row: row["card_id"])
    return {"start_time": str(start_time or "").strip(), "arrays": canon}


def preview_hash(start_time: str, arrays: list[dict]) -> str:
    blob = json.dumps(
        _canonical_preview_payload(start_time, arrays),
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def steps_payload(steps: list[SnapStep]) -> list[dict]:
    return [
        {
            "kind": step.kind,
            "purpose": step.purpose,
            "cmd": step.cmd,
            "skip": step.skip,
            "reason": step.reason,
        }
        for step in steps
    ]


def collect_esx_snap_inventory(run_cmd: Callable[[str], str]) -> dict:
    try:
        policy_out = run_cmd("svcinfo lssnapshotpolicy -delim :")
        if not str(policy_out or "").strip():
            policy_out = run_cmd("svcinfo lssnapshotpolicy")
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{FIRMWARE_MSG} ({exc})",
            "policies": set(),
            "volume_groups": set(),
            "volumes": [],
        }
    text = str(policy_out or "").lower()
    if "not a valid command" in text:
        return {
            "ok": False,
            "error": FIRMWARE_MSG,
            "policies": set(),
            "volume_groups": set(),
            "volumes": [],
        }
    vg_out = run_cmd("svcinfo lsvolumegroup -delim :")
    if not str(vg_out or "").strip():
        vg_out = run_cmd("svcinfo lsvolumegroup")
    vols_out = run_cmd("svcinfo lsvdisk -delim :")
    if not str(vols_out or "").strip():
        vols_out = run_cmd("svcinfo lsvdisk")
    volume_groups = parse_named_objects(vg_out)
    volumes = parse_lsvdisk_membership(vols_out)
    _fill_volume_group_members(run_cmd, volume_groups, volumes)
    return {
        "ok": True,
        "error": "",
        "policies": parse_named_objects(policy_out),
        "volume_groups": volume_groups,
        "volumes": volumes,
    }


def _fill_volume_group_members(
    run_cmd: Callable[[str], str],
    volume_groups: set[str],
    volumes: list[dict[str, str]],
) -> None:
    by_name = {str(row.get("name") or ""): row for row in volumes}
    for vg_name in sorted(volume_groups):
        try:
            vg = cli_token(vg_name)
        except ValueError:
            continue
        member_out = run_cmd(f"svcinfo lsvolumegroupmember -delim : {vg}")
        if not str(member_out or "").strip():
            member_out = run_cmd(f"svcinfo lsvolumegroupmember {vg}")
        for record in _table_records(member_out):
            name = _get(record, "name", "vdisk_name", "volume_name")
            if not name:
                continue
            existing = by_name.get(name)
            if existing is None:
                row = {"name": name, "capacity": "", "volume_group": vg_name}
                volumes.append(row)
                by_name[name] = row
                continue
            if not volume_group_of(existing):
                existing["volume_group"] = vg_name


def build_esx_snap_array_steps(
    *,
    vg_name: str,
    volume_names: list[str],
    start_time: str,
    policies: set[str],
    volume_groups: set[str],
    volumes: list[dict],
    now: datetime | None = None,
) -> tuple[list[SnapStep], list[str], bool]:
    warnings: list[str] = []
    steps: list[SnapStep] = []
    try:
        policy = cli_token(POLICY_NAME)
        vg = cli_token(str(vg_name or "").strip())
    except ValueError as exc:
        warnings.append(f"ERROR: {exc}")
        return steps, warnings, False
    if len(vg) > VG_MAX_LEN:
        warnings.append("ERROR: volume group name exceeds 63 characters")
        return steps, warnings, False
    try:
        start = backup_start_token(start_time, now=now)
    except ValueError as exc:
        warnings.append(f"ERROR: {exc}")
        return steps, warnings, False
    if POLICY_NAME in policies:
        warnings.append(f"ERROR: snapshot policy {POLICY_NAME} already exists")
    if vg in volume_groups:
        warnings.append(f"ERROR: volume group {vg} already exists")
    chosen = [str(name).strip() for name in volume_names if str(name).strip()]
    if not chosen:
        warnings.append("ERROR: select at least one volume")
    by_name = {str(row.get("name") or ""): row for row in volumes}
    safe_vols: list[str] = []
    for name in chosen:
        try:
            token = cli_token(name)
        except ValueError as exc:
            warnings.append(f"ERROR: {exc}")
            continue
        live = by_name.get(name)
        if live is None:
            warnings.append(f"ERROR: volume {name} not found on array")
            continue
        existing = volume_group_of(live)
        if existing:
            warnings.append(
                f"ERROR: volume {name} already belongs to volume group {existing}"
            )
            continue
        safe_vols.append(token)
    if any(item.startswith("ERROR:") for item in warnings):
        return steps, warnings, False
    steps.append(
        SnapStep(
            kind="mksnapshotpolicy",
            purpose="create ESX-snap policy (daily, retain 7 days)",
            cmd=(
                "svctask mksnapshotpolicy -backupunit day -backupinterval 1 "
                f"-backupstarttime {start} -retentiondays 7 -name {policy}"
            ),
        )
    )
    steps.append(
        SnapStep(
            kind="mkvolumegroup",
            purpose="create volume group with ESX-snap policy",
            cmd=f"svctask mkvolumegroup -snapshotpolicy {policy} -name {vg}",
        )
    )
    for token in safe_vols:
        steps.append(
            SnapStep(
                kind="addvolumetovolumegroup",
                purpose=f"add volume {token}",
                cmd=f"svctask addvolumetovolumegroup -volumegroup {vg} {token}",
            )
        )
    return steps, warnings, True
