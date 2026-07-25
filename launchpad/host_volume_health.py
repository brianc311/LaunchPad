"""Host & volume health helpers — offline/degraded filters and shared parsers."""

from __future__ import annotations

from launchpad.flashsystem_fc import parse_fc_hosts, parse_lsvdisk_volumes
from launchpad.volume_find import (
    is_volume_find_eligible,
    parse_showhost_hosts,
    parse_showvv_volumes,
    vendor_for_profile,
)

__all__ = [
    "is_volume_find_eligible",
    "normalize_gui_url",
    "parse_fc_hosts",
    "parse_lsvdisk_volumes",
    "parse_showhost_hosts",
    "parse_showvv_volumes",
    "status_is_offline_or_degraded",
    "vendor_for_profile",
]


def status_is_offline_or_degraded(status: str) -> bool:
    folded = str(status or "").casefold()
    return "offline" in folded or "degraded" in folded


def normalize_gui_url(url: str) -> str:
    stripped = str(url or "").strip()
    if not stripped:
        return ""
    if "://" not in stripped:
        return f"https://{stripped}"
    return stripped
