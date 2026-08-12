"""Shared health alert acknowledge, pause, and mute state."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

HEALTH_ALERT_SETTING = "health_alert_state"

PAUSE_MINUTES = frozenset({5, 10, 15, 20})

_DRIVE_CATEGORIES = frozenset({"nvme", "disk", "mdisk", "drive"})
_OFFLINE_DEGRADED = frozenset(
    {"offline", "degraded", "failed", "error", "down", "missing", "inactive", "fault"}
)


def issue_fingerprint(card_id: int | str, category: str, message: str) -> str:
    normalized = " ".join(str(message or "").split())
    return f"{card_id}:{category}:{normalized}"


def empty_state() -> dict[str, Any]:
    return {"acknowledged": [], "alarm_muted": {}, "paused_until": {}}


def _normalize_state(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    acknowledged = data.get("acknowledged")
    if not isinstance(acknowledged, list):
        acknowledged = []
    acknowledged = [str(item) for item in acknowledged if str(item).strip()]

    alarm_muted = data.get("alarm_muted")
    if not isinstance(alarm_muted, dict):
        alarm_muted = {}
    alarm_muted = {
        str(key): bool(value)
        for key, value in alarm_muted.items()
        if bool(value)
    }

    paused_until = data.get("paused_until")
    if not isinstance(paused_until, dict):
        paused_until = {}
    normalized_paused: dict[str, float] = {}
    for key, value in paused_until.items():
        try:
            normalized_paused[str(key)] = float(value)
        except (TypeError, ValueError):
            continue

    return {
        "acknowledged": acknowledged,
        "alarm_muted": alarm_muted,
        "paused_until": normalized_paused,
    }


def load_state(raw: str | None) -> dict[str, Any]:
    if not raw:
        return empty_state()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return empty_state()
    return _normalize_state(parsed)


def dump_state(state: dict[str, Any]) -> str:
    return json.dumps(_normalize_state(state))


def acknowledge(state: dict[str, Any], fingerprint: str) -> dict[str, Any]:
    out = _normalize_state(state)
    acks = list(out["acknowledged"])
    fp = str(fingerprint)
    if fp not in acks:
        acks.append(fp)
    out["acknowledged"] = acks
    return out


def pause_card(
    state: dict[str, Any],
    card_id: int | str,
    minutes: int,
    *,
    now: float,
) -> dict[str, Any]:
    if minutes not in PAUSE_MINUTES:
        raise ValueError(f"minutes must be one of {sorted(PAUSE_MINUTES)}")
    out = _normalize_state(state)
    out["paused_until"][str(card_id)] = float(now) + minutes * 60
    return out


def set_alarm(state: dict[str, Any], card_id: int | str, muted: bool) -> dict[str, Any]:
    out = _normalize_state(state)
    key = str(card_id)
    if muted:
        out["alarm_muted"][key] = True
    else:
        out["alarm_muted"].pop(key, None)
    return out


def prune_acknowledgements(
    state: dict[str, Any], active_fingerprints: set[str]
) -> dict[str, Any]:
    out = _normalize_state(state)
    active = {str(fp) for fp in active_fingerprints}
    out["acknowledged"] = [fp for fp in out["acknowledged"] if fp in active]
    return out


def _monitor_on(monitor_states: dict[Any, Any], card_id: Any) -> bool:
    if card_id in monitor_states:
        return bool(monitor_states[card_id])
    key = str(card_id)
    if key in monitor_states:
        return bool(monitor_states[key])
    return False


def _has_useful_health_data(card: dict[str, Any]) -> bool:
    health_issues = card.get("health_issues") or []
    if health_issues:
        return True
    metrics = card.get("metrics")
    return metrics not in (None, {}, [])


def _indicates_offline_degraded(issue: dict[str, Any]) -> bool:
    message = str(issue.get("message") or "").lower()
    status = str(issue.get("status") or "").lower()
    return any(term in message or term in status for term in _OFFLINE_DEGRADED)


def _candidate(
    card_id: Any,
    card_name: str,
    category: str,
    message: str,
    severity: str,
) -> dict[str, Any]:
    return {
        "fingerprint": issue_fingerprint(card_id, category, message),
        "card_id": card_id,
        "card_name": card_name,
        "category": category,
        "message": message,
        "severity": severity,
    }


def collect_critical_candidates(card: dict[str, Any], *, monitor_on: bool) -> list[dict[str, Any]]:
    if not monitor_on:
        return []

    card_id = card.get("id")
    card_name = str(card.get("name") or "")
    error = card.get("error")
    health_issues = card.get("health_issues") or []

    if error and not _has_useful_health_data(card):
        message = str(error)
        return [
            _candidate(
                card_id,
                card_name,
                "connectivity",
                message,
                "critical",
            )
        ]

    candidates: list[dict[str, Any]] = []
    for issue in health_issues:
        if not isinstance(issue, dict):
            continue
        category = str(issue.get("category") or "")
        message = str(issue.get("message") or "")
        severity = str(issue.get("severity") or "")
        is_critical = severity == "critical"
        if not is_critical and category in _DRIVE_CATEGORIES:
            if _indicates_offline_degraded(issue):
                is_critical = True
                severity = "critical"
        if not is_critical:
            continue
        candidates.append(_candidate(card_id, card_name, category, message, severity))
    return candidates


def list_popup_alerts(
    cards: list[dict[str, Any]],
    monitor_states: dict[Any, Any],
    state: dict[str, Any],
    *,
    now: float,
) -> list[dict[str, Any]]:
    normalized = _normalize_state(state)
    acknowledged = set(normalized["acknowledged"])
    alarm_muted = normalized["alarm_muted"]
    paused_until = normalized["paused_until"]
    alerts: list[dict[str, Any]] = []

    for card in cards:
        card_id = card.get("id")
        key = str(card_id)
        if not _monitor_on(monitor_states, card_id):
            continue
        pause_end = paused_until.get(key)
        if pause_end is not None and now < pause_end:
            continue
        if alarm_muted.get(key):
            continue
        for candidate in collect_critical_candidates(card, monitor_on=True):
            if candidate["fingerprint"] not in acknowledged:
                alerts.append(deepcopy(candidate))
    return alerts
