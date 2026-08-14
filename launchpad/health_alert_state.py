"""Shared health alert acknowledge, pause, and mute state."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime
from typing import Any

HEALTH_ALERT_SETTING = "health_alert_state"
CONNECTIVITY_SENTINEL = "connectivity"

DEFAULT_ACTIVE_ISSUES_SINCE = "2026-08-14"

PAUSE_MINUTES = frozenset({5, 10, 15, 20})

_DRIVE_CATEGORIES = frozenset({"nvme", "disk", "mdisk", "drive"})
_OFFLINE_DEGRADED = frozenset(
    {"offline", "degraded", "failed", "error", "down", "missing", "inactive", "fault"}
)


def issue_fingerprint(card_id: int | str, category: str, message: str) -> str:
    normalized = " ".join(str(message or "").split())
    return f"{card_id}:{category}:{normalized}"


def same_health_alert_card_id(left: Any, right: Any) -> bool:
    """True when two alert card ids refer to the same card (int/str safe)."""
    if left is None or right is None:
        return False
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return str(left) == str(right)


def empty_state() -> dict[str, Any]:
    return {
        "acknowledged": [],
        "alarm_muted": {},
        "paused_until": {},
        "limit_new_issues": True,
        "active_issues_since": DEFAULT_ACTIVE_ISSUES_SINCE,
        "first_seen": {},
        "grandfathered": [],
        "baseline_applied": False,
        "pending_grandfather": False,
    }


def parse_active_issues_since(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


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

    limit_new_issues = data.get("limit_new_issues")
    if not isinstance(limit_new_issues, bool):
        limit_new_issues = True

    active_issues_since = parse_active_issues_since(
        str(data.get("active_issues_since") or "")
    ) or DEFAULT_ACTIVE_ISSUES_SINCE

    first_seen_raw = data.get("first_seen")
    if not isinstance(first_seen_raw, dict):
        first_seen_raw = {}
    first_seen: dict[str, float] = {}
    for key, value in first_seen_raw.items():
        try:
            first_seen[str(key)] = float(value)
        except (TypeError, ValueError):
            continue

    grandfathered_raw = data.get("grandfathered")
    if not isinstance(grandfathered_raw, list):
        grandfathered_raw = []
    grandfathered = [str(item) for item in grandfathered_raw if str(item).strip()]

    baseline_applied = bool(data.get("baseline_applied"))
    pending_grandfather = bool(data.get("pending_grandfather"))

    return {
        "acknowledged": acknowledged,
        "alarm_muted": alarm_muted,
        "paused_until": normalized_paused,
        "limit_new_issues": limit_new_issues,
        "active_issues_since": active_issues_since,
        "first_seen": first_seen,
        "grandfathered": grandfathered,
        "baseline_applied": baseline_applied,
        "pending_grandfather": pending_grandfather,
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


def set_limit_new_issues(state: dict[str, Any], enabled: bool) -> dict[str, Any]:
    out = _normalize_state(state)
    out["limit_new_issues"] = bool(enabled)
    return out


def set_active_issues_since(state: dict[str, Any], iso_date: str) -> dict[str, Any]:
    parsed = parse_active_issues_since(iso_date)
    if parsed is None:
        raise ValueError("active_issues_since must be YYYY-MM-DD")
    out = _normalize_state(state)
    out["active_issues_since"] = parsed
    return out


def grandfather_fingerprints(
    state: dict[str, Any], fingerprints: set[str] | list[str]
) -> dict[str, Any]:
    out = _normalize_state(state)
    existing = set(out["grandfathered"])
    for fp in fingerprints:
        text = str(fp).strip()
        if text:
            existing.add(text)
    out["grandfathered"] = sorted(existing)
    return out


def ensure_first_seen(
    state: dict[str, Any], fingerprints: set[str], *, now: float
) -> dict[str, Any]:
    out = _normalize_state(state)
    first_seen = dict(out["first_seen"])
    for fp in fingerprints:
        key = str(fp)
        if key and key not in first_seen:
            first_seen[key] = float(now)
    out["first_seen"] = first_seen
    return out


def issue_fingerprint_for_issue(card_id: int | str, issue: dict[str, Any]) -> str:
    category = str(issue.get("category") or "")
    fingerprint_message = issue.get("fingerprint_message")
    message = (
        str(fingerprint_message)
        if fingerprint_message is not None
        else str(issue.get("message") or "")
    )
    return issue_fingerprint(card_id, category, message)


def _cutoff_date(state: dict[str, Any]) -> date:
    parsed = parse_active_issues_since(str(state.get("active_issues_since") or ""))
    return date.fromisoformat(parsed or DEFAULT_ACTIVE_ISSUES_SINCE)


def issue_is_visible(state: dict[str, Any], fingerprint: str, *, now: float) -> bool:
    del now  # cutoff uses stored first_seen, not the call clock
    normalized = _normalize_state(state)
    if not normalized["limit_new_issues"]:
        return True
    fp = str(fingerprint)
    if fp in set(normalized["grandfathered"]):
        return False
    seen = normalized["first_seen"].get(fp)
    if seen is None:
        return True
    seen_day = datetime.fromtimestamp(float(seen)).date()
    return seen_day >= _cutoff_date(normalized)


def visible_health_issues(
    issues: list[Any],
    card_id: int | str,
    state: dict[str, Any],
    *,
    now: float,
) -> list[Any]:
    visible: list[Any] = []
    for issue in issues or []:
        if not isinstance(issue, dict):
            continue
        fp = issue_fingerprint_for_issue(card_id, issue)
        if issue_is_visible(state, fp, now=now):
            visible.append(issue)
    return visible


def prune_acknowledgements(
    state: dict[str, Any], active_fingerprints: set[str]
) -> dict[str, Any]:
    out = _normalize_state(state)
    active = {str(fp) for fp in active_fingerprints}
    out["acknowledged"] = [fp for fp in out["acknowledged"] if fp in active]
    out["grandfathered"] = [fp for fp in out["grandfathered"] if fp in active]
    out["first_seen"] = {
        fp: ts for fp, ts in out["first_seen"].items() if fp in active
    }
    return out


def set_pending_grandfather(state: dict[str, Any], pending: bool) -> dict[str, Any]:
    out = _normalize_state(state)
    out["pending_grandfather"] = bool(pending)
    return out


def prepare_health_issue_limit(
    state: dict[str, Any],
    cards: list[dict[str, Any]],
    *,
    now: float,
) -> dict[str, Any]:
    out = _normalize_state(state)
    fps: set[str] = set()
    for card in cards:
        fps |= fingerprints_for_card(card)
    if (not out["baseline_applied"]) or out["pending_grandfather"]:
        if cards_have_health_signal(cards):
            out = grandfather_fingerprints(out, fps)
            out["baseline_applied"] = True
            out["pending_grandfather"] = False
    out = ensure_first_seen(out, fps, now=now)
    return prune_acknowledgements(out, fps)


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


def _issues_are_only_command_failures(health_issues: list[Any]) -> bool:
    issues = [issue for issue in health_issues if isinstance(issue, dict)]
    if not issues:
        return False
    return all(str(issue.get("category") or "") == "command" for issue in issues)


def _issue_entity_key(message: str) -> str | None:
    parts = str(message or "").split()
    if len(parts) >= 2:
        return parts[1].lower()
    return None


def _dedupe_node_controller_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    controller_entities = {
        entity
        for candidate in candidates
        if candidate.get("category") == "controller"
        and (
            entity := _issue_entity_key(
                str(candidate.get("_dedupe_message") or candidate.get("message") or "")
            )
        )
    }
    deduped = (
        candidates
        if not controller_entities
        else [
            candidate
            for candidate in candidates
            if not (
                candidate.get("category") == "node"
                and _issue_entity_key(
                    str(candidate.get("_dedupe_message") or candidate.get("message") or "")
                )
                in controller_entities
            )
        ]
    )
    for candidate in deduped:
        candidate.pop("_dedupe_message", None)
    return deduped


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
    *,
    fingerprint_message: str | None = None,
) -> dict[str, Any]:
    fp_message = message if fingerprint_message is None else fingerprint_message
    return {
        "fingerprint": issue_fingerprint(card_id, category, fp_message),
        "card_id": card_id,
        "card_name": card_name,
        "category": category,
        "message": message,
        "severity": severity,
        "_dedupe_message": fp_message,
    }


def collect_critical_candidates(card: dict[str, Any], *, monitor_on: bool) -> list[dict[str, Any]]:
    if not monitor_on:
        return []

    card_id = card.get("id")
    card_name = str(card.get("name") or "")
    error = card.get("error")
    health_issues = card.get("health_issues") or []

    if error and (
        not _has_useful_health_data(card)
        or _issues_are_only_command_failures(health_issues)
    ):
        message = str(error)
        return [
            _candidate(
                card_id,
                card_name,
                "connectivity",
                message,
                "critical",
                fingerprint_message=CONNECTIVITY_SENTINEL,
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
        fingerprint_message = issue.get("fingerprint_message")
        candidates.append(
            _candidate(
                card_id,
                card_name,
                category,
                message,
                severity,
                fingerprint_message=(
                    None if fingerprint_message is None else str(fingerprint_message)
                ),
            )
        )
    return _dedupe_node_controller_candidates(candidates)


def fingerprints_for_card(card: dict[str, Any]) -> set[str]:
    card_id = card.get("id")
    fps: set[str] = set()
    for issue in card.get("health_issues") or []:
        if isinstance(issue, dict):
            fps.add(issue_fingerprint_for_issue(card_id, issue))
    for candidate in collect_critical_candidates(card, monitor_on=True):
        fps.add(str(candidate["fingerprint"]))
    return fps


def cards_have_health_signal(cards: list[dict[str, Any]]) -> bool:
    for card in cards:
        if fingerprints_for_card(card) or _has_useful_health_data(card):
            return True
    return False


def open_issue_fingerprints_for_baseline(
    cards: list[dict[str, Any]],
) -> tuple[set[str], bool]:
    if not cards or not cards_have_health_signal(cards):
        return set(), False
    fps: set[str] = set()
    for card in cards:
        fps |= fingerprints_for_card(card)
    return fps, True


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
            fp = candidate["fingerprint"]
            if fp in acknowledged:
                continue
            if not issue_is_visible(normalized, fp, now=now):
                continue
            alerts.append(deepcopy(candidate))
    return alerts
