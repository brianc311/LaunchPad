"""Host & volume health helpers — offline/degraded filters and shared parsers."""

from __future__ import annotations

from typing import Any

from launchpad.flashsystem_fc import parse_fc_hosts, parse_lsvdisk_volumes
from launchpad.volume_find import (
    is_volume_find_eligible,
    parse_showhost_hosts,
    parse_showvv_volumes,
    vendor_for_profile,
)

__all__ = [
    "filter_problem_hosts",
    "filter_problem_volumes",
    "is_volume_find_eligible",
    "normalize_gui_url",
    "resolve_gui_url",
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


def resolve_gui_url(url: str = "", host: str = "") -> str:
    """Prefer Admin GUI URL; fall back to management host as https://host."""
    return normalize_gui_url(url) or normalize_gui_url(host)


def _row_status(row: dict[str, str]) -> str:
    # Prefer health fields; never treat HPE ownership columns (Mstr/Rd) as status.
    for key in ("status", "detailed_state", "state"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def filter_problem_hosts(
    rows: list[dict[str, str]],
    *,
    card_name: str,
    host: str,
    vendor: str,
    card_id: int | None = None,
) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for row in rows:
        status = _row_status(row)
        if not status_is_offline_or_degraded(status):
            continue
        entry: dict[str, Any] = {
            "card_name": card_name,
            "host": host,
            "vendor": vendor,
            "host_name": str(row.get("host_name") or row.get("name") or "").strip(),
            "status": status,
            "wwpns": str(row.get("wwpns") or "").strip(),
        }
        if card_id is not None:
            entry["card_id"] = int(card_id)
        problems.append(entry)
    return problems


def filter_problem_volumes(
    rows: list[dict[str, str]],
    *,
    card_name: str,
    host: str,
    vendor: str,
    card_id: int | None = None,
) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for row in rows:
        status = _row_status(row)
        if not status_is_offline_or_degraded(status):
            continue
        pool = str(row.get("pool_or_cpg") or row.get("pool") or "").strip()
        entry: dict[str, Any] = {
            "card_name": card_name,
            "host": host,
            "vendor": vendor,
            "volume_name": str(row.get("name") or row.get("volume_name") or "").strip(),
            "pool_or_cpg": pool,
            "status": status,
        }
        if card_id is not None:
            entry["card_id"] = int(card_id)
        problems.append(entry)
    return problems