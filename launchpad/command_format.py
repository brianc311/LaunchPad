def format_command_lines(commands: list[tuple[str, str]]) -> str:
    return "\n".join(f"{label}|{command}" for label, command in commands)


def parse_command_lines(text: str) -> list[tuple[str, str]]:
    commands: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            label, command = line.split("|", 1)
            label = label.strip()
            command = command.strip()
        else:
            command = line
            label = command.split()[0] if command else "Command"
        if command:
            commands.append((label, command))
    return commands


def resolve_card_commands(
    device_profile: str,
    custom_commands: str,
    *,
    instance_id: str = "",
    dscli_path: str = "",
    dscli_hmc: str = "",
    username: str = "",
    password: str = "",
) -> list[tuple[str, str]]:
    # Inline import avoids circular import with storage_presets → command_format.
    from launchpad.dscli_wrap import wrap_dscli_labeled_commands
    from launchpad.storage_presets import (
        ensure_hpe_capacity_commands,
        ensure_svc_fc_commands,
        ensure_svc_health_commands,
        preset_commands_for_profile,
    )

    parsed = parse_command_lines(custom_commands)
    if parsed:
        commands = parsed
    else:
        commands = preset_commands_for_profile(device_profile)
    commands = ensure_svc_fc_commands(device_profile, commands)
    commands = ensure_svc_health_commands(device_profile, commands)
    commands = ensure_hpe_capacity_commands(device_profile, commands)
    commands = apply_command_placeholders(commands, instance_id=instance_id)
    if device_profile.strip().lower() == "ibm_ds8884":
        commands = wrap_dscli_labeled_commands(
            commands,
            dscli_path=dscli_path,
            hmc_host=dscli_hmc,
            username=username,
            password=password,
        )
    return commands


def _is_pool_capacity_command(label: str, command: str) -> bool:
    haystack = f"{label} {command}".lower()
    label_lower = label.lower()
    if any(token in haystack for token in ("showcpg", "lsmdiskgrp", "lsextpool")):
        return True
    if "showspace -cpg" in haystack or "showspace-cpg" in haystack:
        return True
    if "capacity - cpg" in label_lower or "capacity - pools" in label_lower:
        return True
    if "capacity - pool" in label_lower and "capacity - pools" not in label_lower:
        return True
    return False


def drop_pool_capacity_results(
    results: list[dict] | None,
) -> list[dict]:
    """Remove showcpg / lsmdiskgrp (and similar) rows from merged command results."""
    if not results:
        return []
    return [
        item
        for item in results
        if not _is_pool_capacity_command(
            str(item.get("label") or ""),
            str(item.get("command") or ""),
        )
    ]


def filter_capacity_focus_commands(
    commands: list[tuple[str, str]],
    *,
    include_pools: bool = True,
) -> list[tuple[str, str]]:
    """Keep only capacity-oriented CLI commands for faster Capacity Report refresh.

    When include_pools is False, drop showcpg / lsmdiskgrp / capacity - cpg /
    capacity - pools (and similar pool labels). Keep showsys / lssystem.
    """
    kept: list[tuple[str, str]] = []
    for label, command in commands:
        haystack = f"{label} {command}".lower()
        if not include_pools and _is_pool_capacity_command(label, command):
            continue
        if "capacity" in haystack:
            kept.append((label, command))
            continue
        if any(
            token in haystack
            for token in (
                "showsys",
                "showcpg",
                "showspace",
                "lssystem",
                "lsmdiskgrp",
                "lsextpool",
                "df -h",
            )
        ):
            kept.append((label, command))
    if not include_pools:
        return kept
    return kept or list(commands)


def apply_command_placeholders(
    commands: list[tuple[str, str]],
    *,
    instance_id: str = "",
) -> list[tuple[str, str]]:
    token = instance_id.strip()
    if not token:
        return list(commands)
    resolved: list[tuple[str, str]] = []
    for label, command in commands:
        resolved.append(
            (
                label,
                command.replace("YOUR_INSTANCE_ID", token).replace("{instance_id}", token),
            )
        )
    return resolved
