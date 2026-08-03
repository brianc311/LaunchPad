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
) -> list[tuple[str, str]]:
    # Inline import avoids circular import with storage_presets → command_format.
    from launchpad.storage_presets import (
        ensure_hpe_capacity_commands,
        ensure_svc_fc_commands,
        preset_commands_for_profile,
    )

    parsed = parse_command_lines(custom_commands)
    if parsed:
        commands = parsed
    else:
        commands = preset_commands_for_profile(device_profile)
    commands = ensure_svc_fc_commands(device_profile, commands)
    commands = ensure_hpe_capacity_commands(device_profile, commands)
    return apply_command_placeholders(commands, instance_id=instance_id)


def filter_capacity_focus_commands(
    commands: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Keep only capacity-oriented CLI commands for faster Capacity Report refresh."""
    kept: list[tuple[str, str]] = []
    for label, command in commands:
        haystack = f"{label} {command}".lower()
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
