"""Promote Hadoop-named General SSH cards to hadoop_linux for Host Power."""

from __future__ import annotations

from launchpad.command_format import format_command_lines, parse_command_lines
from launchpad.host_power_ops import host_power_precheck_catalog, precheck_letter_from_label
from launchpad.storage_presets import (
    HADOOP_LINUX_COMMANDS,
    STORAGE_PROFILES,
    preset_command_text,
)

POWER_LABEL_PREFIX = "Power -"


def looks_like_hadoop_host(
    name: str,
    *,
    category: str = "",
    host: str = "",
) -> bool:
    haystack = f"{name} {category} {host}".lower()
    return "hadoop" in haystack or "hdp" in haystack


def _has_power_commands(custom_commands: str) -> bool:
    return any(
        label.startswith(POWER_LABEL_PREFIX)
        for label, _ in parse_command_lines(custom_commands)
    )


def _present_precheck_letters(custom_commands: str) -> set[str]:
    letters: set[str] = set()
    for label, _ in parse_command_lines(custom_commands):
        letter = precheck_letter_from_label(label)
        if letter:
            letters.add(letter)
    return letters


def _missing_precheck_tuples(custom_commands: str) -> list[tuple[str, str]]:
    present = _present_precheck_letters(custom_commands)
    return [
        (item.label, item.command)
        for item in host_power_precheck_catalog()
        if item.letter not in present
    ]


def _merge_hadoop_linux_presets(custom_commands: str) -> str:
    existing = parse_command_lines(custom_commands)
    if not existing:
        return preset_command_text("hadoop_linux")
    additions: list[tuple[str, str]] = []
    if not _has_power_commands(custom_commands):
        additions.extend(
            (label, command)
            for label, command in HADOOP_LINUX_COMMANDS
            if label.startswith(POWER_LABEL_PREFIX)
        )
    additions.extend(_missing_precheck_tuples(custom_commands))
    if not additions:
        return custom_commands
    body = custom_commands.rstrip()
    suffix = format_command_lines(additions)
    if body:
        return f"{body}\n{suffix}"
    return suffix


def ensure_hadoop_linux_cards(db) -> int:
    """Set device_profile/commands so Host Power can list Hadoop SSH cards.

    - General SSH cards (empty profile) whose name/category/host looks like
      Hadoop are promoted to ``hadoop_linux`` with Power - presets merged in.
    - Existing ``hadoop_linux`` cards missing Power - commands get those
      presets appended (existing custom lines kept).
    - Storage/other profiles are left alone even if the name mentions Hadoop.
    """
    updated = 0
    for card in db.list_cards():
        if card.card_type != "ssh":
            continue
        profile = (card.device_profile or "").strip()
        looks = looks_like_hadoop_host(
            card.name,
            category=getattr(card, "category", "") or "",
            host=getattr(card, "host", "") or "",
        )

        if profile == "hadoop_linux":
            new_commands = _merge_hadoop_linux_presets(card.custom_commands or "")
            if new_commands == (card.custom_commands or ""):
                continue
            _patch_card(db, card, device_profile="hadoop_linux", custom_commands=new_commands)
            updated += 1
            continue

        if profile and profile in STORAGE_PROFILES:
            continue
        if profile and profile != "":
            # Unknown non-empty profile: only promote when it looks like Hadoop
            # and profile is not a known storage platform (already handled).
            # Leave vultr_* and other explicit profiles alone.
            continue
        if not looks:
            continue

        new_commands = _merge_hadoop_linux_presets(card.custom_commands or "")
        _patch_card(db, card, device_profile="hadoop_linux", custom_commands=new_commands)
        updated += 1
    return updated


def _patch_card(db, card, *, device_profile: str, custom_commands: str) -> None:
    db.update_card(
        card.id,
        {
            "name": card.name,
            "card_type": card.card_type,
            "host": card.host,
            "port": card.port,
            "serial_number": card.serial_number,
            "username": card.username,
            "encrypted_password": card.encrypted_password,
            "encrypted_sudo_password": getattr(card, "encrypted_sudo_password", ""),
            "encrypted_key_passphrase": card.encrypted_key_passphrase,
            "encrypted_key": card.encrypted_key,
            "url": card.url,
            "icon": card.icon,
            "category": card.category,
            "sort_order": card.sort_order,
            "glow_color": card.glow_color,
            "key_file_path": card.key_file_path,
            "device_profile": device_profile,
            "custom_commands": custom_commands,
        },
    )
