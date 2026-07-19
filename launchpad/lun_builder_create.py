"""Build and run sanitized storage CLI steps for LUN Builder."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from launchpad.contingency_snap_create import cli_token, parse_capacity_to_gb
from launchpad.lun_builder_data import expand_lun_batch, supports_live_run
from launchpad.storage_presets import HP_3PAR_PROFILES, SVC_PROFILES


def _command_token(value: Any) -> str:
    """Return a non-option CLI token for storage commands."""
    token = cli_token(value)
    if token.startswith("-"):
        raise ValueError(f"Unsafe CLI token: {token!r}")
    return token


def _size_gb(value: str) -> int | float:
    size_gb = parse_capacity_to_gb(value)
    if size_gb is None or size_gb <= 0:
        raise ValueError(f"Invalid LUN size: {value!r}")
    return int(size_gb) if size_gb == int(size_gb) else size_gb


def _inventory_for_card(
    inventory_by_card: dict[str, Any] | None,
    card_hint: str,
) -> dict[str, Any]:
    if inventory_by_card is None:
        return {}
    inventory = inventory_by_card.get(card_hint)
    return inventory if isinstance(inventory, dict) else {}


def _step(
    *,
    kind: str,
    label: str,
    cmd: str,
    card_hint: str,
    profile: str,
    live: bool,
    skip: bool = False,
    reason: str = "",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
        "cmd": cmd,
        "card_hint": card_hint,
        "profile": profile,
        "live": live,
        "skip": skip,
        "reason": reason,
    }


def build_lun_steps(
    build: dict,
    inventory_by_card: dict | None,
) -> list[dict]:
    """Expand a build into sanitized preview/create command steps."""
    steps: list[dict[str, Any]] = []
    host_lun_offsets: dict[str, int] = {}
    used_host_lun_ids: dict[str, set[int]] = {}

    for lun in build.get("luns") or []:
        expanded_rows = expand_lun_batch(lun)
        for row_index, row in enumerate(expanded_rows):
            name = _command_token(row.get("name"))
            pool = _command_token(row.get("pool_or_cpg"))
            profile = cli_token(row.get("storage_profile"))
            card_hint = str(row.get("card_hint") or "").strip()
            size_text = str(row.get("size") or "").strip()
            size_gb = _size_gb(size_text)
            live = supports_live_run(profile)

            if profile in SVC_PROFILES:
                inventory = _inventory_for_card(inventory_by_card, card_hint)
                existing_vdisks = set(inventory.get("vdisks") or [])
                skip_create = name in existing_vdisks
                steps.append(
                    _step(
                        kind="mkvdisk",
                        label=f"Create volume {name}",
                        cmd=(
                            f"svctask mkvdisk -name {name} -mdiskgrp {pool} "
                            f"-size {size_gb} -unit gb"
                        ),
                        card_hint=card_hint,
                        profile=profile,
                        live=True,
                        skip=skip_create,
                        reason="volume already exists" if skip_create else "",
                    )
                )
                existing_hostmaps = set(inventory.get("hostmaps") or [])
                for host in row.get("host_names") or []:
                    host_token = _command_token(host)
                    scsi = _lun_id(
                        row,
                        host_token,
                        row_index,
                        host_lun_offsets,
                        used_host_lun_ids,
                    )
                    hostmap_key = (host_token, str(scsi), name)
                    skip_map = hostmap_key in existing_hostmaps
                    steps.append(
                        _step(
                            kind="mkvdiskhostmap",
                            label=f"Map {name} to {host_token}",
                            cmd=(
                                "svctask mkvdiskhostmap "
                                f"-host {host_token} -scsi {scsi} {name}"
                            ),
                            card_hint=card_hint,
                            profile=profile,
                            live=True,
                            skip=skip_map,
                            reason="host map already exists" if skip_map else "",
                        )
                    )
                continue

            if profile in HP_3PAR_PROFILES or profile == "hpe_primera_600":
                size_arg = f"{math.ceil(size_gb)}g"
                steps.append(
                    _step(
                        kind="createvv",
                        label=f"Create virtual volume {name}",
                        cmd=f"createvv {pool} {name} {size_arg}",
                        card_hint=card_hint,
                        profile=profile,
                        live=True,
                    )
                )
                for host in row.get("host_names") or []:
                    host_token = _command_token(host)
                    lun_id = _lun_id(
                        row,
                        host_token,
                        row_index,
                        host_lun_offsets,
                        used_host_lun_ids,
                    )
                    steps.append(
                        _step(
                            kind="createvlun",
                            label=f"Export {name} to {host_token}",
                            cmd=f"createvlun {name} {lun_id} {host_token}",
                            card_hint=card_hint,
                            profile=profile,
                            live=True,
                        )
                    )
                continue

            size_token = cli_token(size_text)
            if profile == "ibm_ds8884":
                command = (
                    f"dscli mkfbvol -extpool {pool} -cap {size_token} {name}"
                )
            else:
                command = (
                    f"vol_create vol={name} size={size_token} pool={pool}"
                )
            steps.append(
                _step(
                    kind="plan",
                    label=f"Plan volume {name}",
                    cmd=command,
                    card_hint=card_hint,
                    profile=profile,
                    live=live,
                )
            )

    return steps


def _lun_id(
    row: dict,
    host: str,
    row_index: int,
    host_lun_offsets: dict[str, int],
    used_host_lun_ids: dict[str, set[int]],
) -> int:
    raw = str(row.get("scsi_or_lun_id") or "").strip()
    used_ids = used_host_lun_ids.setdefault(host, set())
    if raw:
        token = _command_token(raw)
        try:
            lun_id = int(token) + row_index
        except ValueError as exc:
            raise ValueError(f"Invalid LUN ID: {raw!r}") from exc
        if lun_id in used_ids:
            raise ValueError(f"LUN ID {lun_id} is already used for host {host}")
        used_ids.add(lun_id)
        return lun_id
    lun_id = host_lun_offsets.get(host, 0)
    while lun_id in used_ids:
        lun_id += 1
    host_lun_offsets[host] = lun_id + 1
    used_ids.add(lun_id)
    return lun_id


def run_lun_steps(
    steps: list[dict],
    run_cmd_for_card: Callable[[str, str], str],
) -> list[dict]:
    """Run live, non-skipped steps and return an operator-facing log."""
    results: list[dict[str, Any]] = []
    for step in steps:
        result = dict(step)
        if not step.get("live"):
            result["status"] = "plan-only"
            results.append(result)
            continue
        if step.get("skip"):
            result["status"] = "skipped"
            results.append(result)
            continue
        try:
            result["output"] = run_cmd_for_card(
                str(step.get("card_hint") or ""),
                str(step.get("cmd") or ""),
            )
            result["status"] = "ok"
        except Exception as exc:
            result["status"] = "failed"
            result["error"] = str(exc)
            results.append(result)
            break
        results.append(result)
    return results
