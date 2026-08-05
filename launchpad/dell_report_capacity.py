"""Choose system vs raw vs pool rollup for Dell Report rows."""

from __future__ import annotations

from typing import Any

from launchpad.flashsystem_health import capacity_summary_from_pools


def _usable(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not summary:
        return None
    if float(summary.get("total_bytes") or 0) <= 0:
        return None
    return summary


def select_dell_capacity_summary(
    *,
    capacity_summary: dict[str, Any] | None,
    raw_capacity_summary: dict[str, Any] | None = None,
    pools: list | None = None,
    include_pools: bool = True,
) -> dict[str, Any] | None:
    """CPG off → raw then system; CPG on → system then pools then raw."""
    system = _usable(capacity_summary)
    raw = _usable(raw_capacity_summary)
    pool_sum = None
    if include_pools and pools:
        pool_sum = _usable(capacity_summary_from_pools(pools))

    if not include_pools:
        return raw or system
    return system or pool_sum or raw
