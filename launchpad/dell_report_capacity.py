"""Choose system vs raw vs pool rollup for Dell Report rows."""

from __future__ import annotations

from typing import Any

from launchpad.flashsystem_health import capacity_summary_from_pools

_POOL_ROLLUP_NAMES = frozenset({"all cpgs", "all pools", "all cpg"})


def _is_pool_rollup_name(name: str) -> bool:
    return (name or "").strip().lower() in _POOL_ROLLUP_NAMES


def _usable(
    summary: dict[str, Any] | None,
    *,
    allow_pool_rollup: bool = True,
) -> dict[str, Any] | None:
    if not summary:
        return None
    if float(summary.get("total_bytes") or 0) <= 0:
        return None
    if not allow_pool_rollup and _is_pool_rollup_name(str(summary.get("name") or "")):
        return None
    return summary


def select_dell_capacity_summary(
    *,
    capacity_summary: dict[str, Any] | None,
    raw_capacity_summary: dict[str, Any] | None = None,
    pools: list | None = None,
    include_pools: bool = True,
) -> dict[str, Any] | None:
    """CPG off → raw then non-rollup system; CPG on → system then pools then raw."""
    raw = _usable(raw_capacity_summary, allow_pool_rollup=True)
    if not include_pools:
        system = _usable(capacity_summary, allow_pool_rollup=False)
        return raw or system

    system = _usable(capacity_summary, allow_pool_rollup=True)
    pool_sum = None
    if pools:
        pool_sum = _usable(capacity_summary_from_pools(pools), allow_pool_rollup=True)
    return system or pool_sum or raw


def select_dell_array_snapshot_summary(
    *,
    capacity_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Array/system usable only; never pools or raw."""
    return _usable(capacity_summary, allow_pool_rollup=False)
