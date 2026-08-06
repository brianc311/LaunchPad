"""Alert banner text/severity for Capacity Excel exports."""

from __future__ import annotations

from typing import Any

BANNER_WARN_FILL = "F59E0B"
BANNER_CRITICAL_FILL = "EF4444"
BANNER_FONT_COLOR = "FFFFFF"


def banner_message_for_max_pct(max_pct: float) -> str | None:
    if max_pct < 80:
        return None
    if max_pct >= 99.5:
        return "CRITICAL: Please check storage — drives are full."
    if max_pct >= 90:
        return "CRITICAL: Please check storage — capacity over 90%."
    return "WARNING: Please check storage — capacity over 80%."


def capacity_excel_banner_summary(
    *,
    pool_used_pcts: list[float],
    site_used_pcts: list[float] | None = None,
    site_keys_over: set[str] | None = None,
) -> dict[str, Any] | None:
    site_pcts = list(site_used_pcts or [])
    all_pcts = list(pool_used_pcts) + site_pcts
    max_pct = max(all_pcts) if all_pcts else 0.0
    base = banner_message_for_max_pct(max_pct)
    if base is None:
        return None
    pool_count = sum(1 for pct in pool_used_pcts if pct >= 80)
    if site_keys_over is not None:
        site_count = len(site_keys_over)
    else:
        site_count = sum(1 for pct in site_pcts if pct >= 80)
    severity = "critical" if max_pct >= 90 else "warn"
    return {
        "severity": severity,
        "max_pct": float(max_pct),
        "site_count": site_count,
        "pool_count": pool_count,
        "message": f"{base} ({site_count} site(s) / {pool_count} pool(s) over threshold)",
    }
