"""Backward-compatible re-exports — use storage_presets for new code."""

from launchpad.storage_presets import (
    DEVICE_PROFILES,
    FLASHSYSTEM_COMMANDS,
    FLASHSYSTEM_PROFILES,
    is_flashsystem_profile,
    preset_command_text,
    preset_commands_for_profile,
)

__all__ = [
    "DEVICE_PROFILES",
    "FLASHSYSTEM_COMMANDS",
    "FLASHSYSTEM_PROFILES",
    "is_flashsystem_profile",
    "preset_command_text",
    "preset_commands_for_profile",
]
