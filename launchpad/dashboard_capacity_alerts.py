"""Derive Connection Dashboard capacity alert badges/strip from Health Server cards."""

from __future__ import annotations

import re
from typing import Any

CAPACITY_ALERT_POLL_MS = 30_000

_CAPACITY_MSG_RE = re.compile(
    r"%\s*(full|capacity)|running at\s+\d",
    re.IGNORECASE,
)


def is_capacity_issue(issue: dict[str, Any] | None) -> bool:
    if not issue:
        return False
    if str(issue.get("category") or "").lower() == "capacity":
        return True
    return bool(_CAPACITY_MSG_RE.search(str(issue.get("message") or "")))


def filter_capacity_issues(issues: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [issue for issue in (issues or []) if is_capacity_issue(issue)]


def card_capacity_severity(
    issues: list[dict[str, Any]] | None,
    *,
    monitor_on: bool,
    updated_at: str | None,
) -> str | None:
    if not monitor_on or not (updated_at or "").strip():
        return None
    capacity = filter_capacity_issues(issues)
    if not capacity:
        return None
    if any(str(issue.get("severity") or "").lower() == "critical" for issue in capacity):
        return "critical"
    return "warn"


def fleet_capacity_alert_summary(
    cards: list[dict[str, Any]],
    monitor_states: dict[int, bool],
) -> dict[str, Any]:
    critical_sites = 0
    warn_sites = 0
    for card in cards:
        card_id = int(card.get("id") or card.get("card_id") or 0)
        severity = card_capacity_severity(
            card.get("health_issues"),
            monitor_on=bool(monitor_states.get(card_id, False)),
            updated_at=card.get("updated_at"),
        )
        if severity == "critical":
            critical_sites += 1
        elif severity == "warn":
            warn_sites += 1
    has_alert = critical_sites > 0 or warn_sites > 0
    if not has_alert:
        label = ""
    else:
        parts: list[str] = []
        if critical_sites:
            parts.append(f"CRITICAL capacity: {critical_sites} site(s)")
        if warn_sites:
            parts.append(f"WARNING: {warn_sites} site(s)")
        label = " · ".join(parts)
    return {
        "critical_sites": critical_sites,
        "warn_sites": warn_sites,
        "label": label,
        "has_alert": has_alert,
    }
