from datetime import datetime

from launchpad.health_alert_state import (
    CONNECTIVITY_SENTINEL,
    DEFAULT_ACTIVE_ISSUES_SINCE,
    acknowledge,
    cards_have_health_signal,
    collect_critical_candidates,
    empty_state,
    ensure_first_seen,
    grandfather_fingerprints,
    issue_fingerprint,
    issue_is_visible,
    list_popup_alerts,
    load_state,
    open_issue_fingerprints_for_baseline,
    prepare_health_issue_limit,
    parse_active_issues_since,
    pause_card,
    prune_acknowledgements,
    set_active_issues_since,
    set_alarm,
    set_limit_new_issues,
    visible_health_issues,
)


def test_warn_not_popup_candidate():
    card = {
        "id": 1,
        "name": "Site",
        "error": None,
        "health_issues": [
            {
                "severity": "warn",
                "category": "capacity",
                "message": "Pool X is 81% full",
                "server": "Site",
            }
        ],
    }
    assert collect_critical_candidates(card, monitor_on=True) == []


def test_unreachable_is_connectivity_critical():
    card = {
        "id": 2,
        "name": "Valparaiso, IN",
        "error": "SSH timeout",
        "health_issues": [],
        "metrics": None,
    }
    items = collect_critical_candidates(card, monitor_on=True)
    assert len(items) == 1
    assert items[0]["category"] == "connectivity"
    assert "Valparaiso" in items[0]["card_name"]
    assert items[0]["fingerprint"] == issue_fingerprint(2, "connectivity", CONNECTIVITY_SENTINEL)


def test_total_command_failure_collapses_to_connectivity():
    """Shape produced when refresh_card fails every preset command."""
    card = {
        "id": 2,
        "name": "Valparaiso, IN",
        "error": "3 of 10 command(s) failed",
        "metrics": None,
        "health_issues": [
            {
                "severity": "critical",
                "category": "command",
                "message": "Health - Nodes failed",
                "server": "Valparaiso, IN",
            },
            {
                "severity": "critical",
                "category": "command",
                "message": "Health - Alerts failed",
                "server": "Valparaiso, IN",
            },
            {
                "severity": "critical",
                "category": "command",
                "message": "Capacity - Pools % failed",
                "server": "Valparaiso, IN",
            },
        ],
    }
    items = collect_critical_candidates(card, monitor_on=True)
    assert len(items) == 1
    assert items[0]["category"] == "connectivity"
    assert items[0]["message"] == "3 of 10 command(s) failed"
    assert items[0]["fingerprint"] == issue_fingerprint(2, "connectivity", CONNECTIVITY_SENTINEL)


def test_partial_command_failure_keeps_real_issues():
    card = {
        "id": 3,
        "name": "Site C",
        "error": "1 of 10 command(s) failed",
        "metrics": {},
        "health_issues": [
            {
                "severity": "critical",
                "category": "command",
                "message": "Health - Alerts failed",
                "server": "Site C",
            },
            {
                "severity": "critical",
                "category": "drive",
                "message": "Drive 2 is offline",
                "server": "Site C",
            },
        ],
    }
    items = collect_critical_candidates(card, monitor_on=True)
    assert len(items) == 2
    assert {item["category"] for item in items} == {"command", "drive"}


def test_controller_duplicates_node_canister_offline():
    card = {
        "id": 4,
        "name": "Site D",
        "error": None,
        "health_issues": [
            {
                "severity": "critical",
                "category": "controller",
                "message": "Controller node1 is offline",
                "server": "Site D",
            },
            {
                "severity": "critical",
                "category": "node",
                "message": "Node node1 is offline",
                "server": "Site D",
            },
        ],
    }
    items = collect_critical_candidates(card, monitor_on=True)
    assert len(items) == 1
    assert items[0]["category"] == "controller"


def test_drive_degraded_is_critical_candidate():
    card = {
        "id": 4,
        "name": "C",
        "error": None,
        "health_issues": [
            {
                "severity": "warn",
                "category": "drive",
                "message": "Drive 2 is degraded",
                "server": "C",
            }
        ],
    }
    items = collect_critical_candidates(card, monitor_on=True)
    assert len(items) == 1
    assert items[0]["severity"] == "critical"


def test_acknowledge_until_clear():
    state = empty_state()
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = acknowledge(state, fp)
    card = {
        "id": 1,
        "name": "A",
        "error": None,
        "health_issues": [
            {
                "severity": "critical",
                "category": "drive",
                "message": "Drive 0 is offline",
                "server": "A",
            }
        ],
    }
    open_ = list_popup_alerts([card], {1: True}, state, now=1000.0)
    assert open_ == []
    state = prune_acknowledgements(state, set())  # issue cleared
    card_clear = {"id": 1, "name": "A", "error": None, "health_issues": []}
    assert list_popup_alerts([card_clear], {1: True}, state, now=1000.0) == []
    open2 = list_popup_alerts([card], {1: True}, state, now=1000.0)
    assert len(open2) == 1


def test_pause_and_alarm_mute():
    state = empty_state()
    card = {
        "id": 3,
        "name": "B",
        "error": None,
        "health_issues": [
            {
                "severity": "critical",
                "category": "node",
                "message": "Node n1 is offline",
                "server": "B",
            }
        ],
    }
    state = pause_card(state, 3, 10, now=1000.0)
    assert list_popup_alerts([card], {3: True}, state, now=1000.0) == []
    assert (
        len(list_popup_alerts([card], {3: True}, state, now=1000.0 + 10 * 60 + 1)) == 1
    )
    state = set_alarm(empty_state(), 3, True)
    assert list_popup_alerts([card], {3: True}, state, now=5000.0) == []


def _ts(year: int, month: int, day: int) -> float:
    return datetime(year, month, day, 12, 0, 0).timestamp()


def _drive_issue(message: str = "Drive 0 is offline") -> dict:
    return {
        "severity": "critical",
        "category": "drive",
        "message": message,
        "server": "A",
    }


def test_normalize_165_json_keeps_mute_and_defaults_limit():
    raw = '{"acknowledged": ["old"], "alarm_muted": {"7": true}, "paused_until": {}}'
    state = load_state(raw)
    assert state["alarm_muted"]["7"] is True
    assert state["acknowledged"] == ["old"]
    assert state["limit_new_issues"] is True
    assert state["active_issues_since"] == DEFAULT_ACTIVE_ISSUES_SINCE
    assert state["first_seen"] == {}
    assert state["grandfathered"] == []
    assert state["baseline_applied"] is False
    assert state["pending_grandfather"] is False


def test_parse_active_issues_since_iso_and_us():
    assert parse_active_issues_since("2026-08-14") == "2026-08-14"
    assert parse_active_issues_since("8/14/2026") == "2026-08-14"
    assert parse_active_issues_since("08/14/26") == "2026-08-14"
    assert parse_active_issues_since("") is None
    assert parse_active_issues_since("not-a-date") is None
    assert parse_active_issues_since("2026-13-40") is None


def test_grandfathered_hidden_when_limit_on():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = empty_state()
    state = grandfather_fingerprints(state, {fp})
    state = ensure_first_seen(state, {fp}, now=_ts(2026, 8, 20))
    assert issue_is_visible(state, fp, now=_ts(2026, 8, 20)) is False
    issues = visible_health_issues([_drive_issue()], 1, state, now=_ts(2026, 8, 20))
    assert issues == []


def test_limit_off_shows_grandfathered():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = set_limit_new_issues(empty_state(), False)
    state = grandfather_fingerprints(state, {fp})
    assert issue_is_visible(state, fp, now=_ts(2026, 8, 20)) is True
    issues = visible_health_issues([_drive_issue()], 1, state, now=_ts(2026, 8, 20))
    assert len(issues) == 1


def test_first_seen_before_cutoff_hidden_on_or_after_visible():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    before = empty_state()
    before = set_active_issues_since(before, "2026-08-14")
    before["first_seen"] = {fp: _ts(2026, 8, 13)}
    assert issue_is_visible(before, fp, now=_ts(2026, 8, 20)) is False

    after = empty_state()
    after = set_active_issues_since(after, "2026-08-14")
    after["first_seen"] = {fp: _ts(2026, 8, 14)}
    assert issue_is_visible(after, fp, now=_ts(2026, 8, 20)) is True

    later = empty_state()
    later["first_seen"] = {fp: _ts(2026, 8, 15)}
    assert issue_is_visible(later, fp, now=_ts(2026, 8, 20)) is True


def test_moving_date_back_does_not_un_grandfather():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = grandfather_fingerprints(empty_state(), {fp})
    state["first_seen"] = {fp: _ts(2026, 8, 20)}
    state = set_active_issues_since(state, "2026-08-01")
    assert issue_is_visible(state, fp, now=_ts(2026, 8, 20)) is False


def test_missing_first_seen_is_visible_when_not_grandfathered():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = empty_state()
    assert issue_is_visible(state, fp, now=1000.0) is True


def test_ensure_first_seen_does_not_overwrite():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = empty_state()
    state = ensure_first_seen(state, {fp}, now=_ts(2026, 8, 14))
    first = state["first_seen"][fp]
    state = ensure_first_seen(state, {fp}, now=_ts(2026, 8, 20))
    assert state["first_seen"][fp] == first


def test_list_popup_alerts_hides_grandfathered_when_limit_on():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    card = {
        "id": 1,
        "name": "A",
        "error": None,
        "health_issues": [_drive_issue()],
    }
    state = grandfather_fingerprints(empty_state(), {fp})
    state["first_seen"] = {fp: _ts(2026, 8, 20)}
    assert list_popup_alerts([card], {1: True}, state, now=_ts(2026, 8, 20)) == []
    state = set_limit_new_issues(state, False)
    assert len(list_popup_alerts([card], {1: True}, state, now=_ts(2026, 8, 20))) == 1


def test_list_popup_alerts_hides_first_seen_before_cutoff():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    card = {
        "id": 1,
        "name": "A",
        "error": None,
        "health_issues": [_drive_issue()],
    }
    state = empty_state()
    state["first_seen"] = {fp: _ts(2026, 8, 13)}
    assert list_popup_alerts([card], {1: True}, state, now=_ts(2026, 8, 20)) == []


def test_prepare_first_upgrade_grandfathers_open_issues_once():
    card = {
        "id": 1,
        "name": "A",
        "error": None,
        "health_issues": [_drive_issue()],
    }
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = prepare_health_issue_limit(empty_state(), [card], now=_ts(2026, 8, 14))
    assert state["baseline_applied"] is True
    assert fp in state["grandfathered"]
    assert fp in state["first_seen"]

    later = {
        "id": 1,
        "name": "A",
        "error": None,
        "health_issues": [_drive_issue(), _drive_issue("Drive 9 is offline")],
    }
    fp_new = issue_fingerprint(1, "drive", "Drive 9 is offline")
    state2 = prepare_health_issue_limit(state, [later], now=_ts(2026, 8, 15))
    assert fp_new not in state2["grandfathered"]
    assert fp_new in state2["first_seen"]
    assert issue_is_visible(state2, fp_new, now=_ts(2026, 8, 15)) is True


def test_prune_drops_inactive_first_seen_and_grandfathered_return_is_new():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = grandfather_fingerprints(empty_state(), {fp})
    state = ensure_first_seen(state, {fp}, now=_ts(2026, 8, 13))
    state["baseline_applied"] = True
    cleared = prune_acknowledgements(state, set())
    assert fp not in cleared["grandfathered"]
    assert fp not in cleared["first_seen"]

    returned = {
        "id": 1,
        "name": "A",
        "error": None,
        "health_issues": [_drive_issue()],
    }
    after = prepare_health_issue_limit(cleared, [returned], now=_ts(2026, 8, 20))
    # baseline already applied, so recurrence is not re-grandfathered
    assert fp not in after["grandfathered"]
    assert issue_is_visible(after, fp, now=_ts(2026, 8, 20)) is True
    assert len(list_popup_alerts([returned], {1: True}, after, now=_ts(2026, 8, 20))) == 1


def test_pending_grandfather_runs_on_next_prepare():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = empty_state()
    state["baseline_applied"] = True
    state["pending_grandfather"] = True
    card = {
        "id": 1,
        "name": "A",
        "error": None,
        "health_issues": [_drive_issue()],
    }
    out = prepare_health_issue_limit(state, [card], now=_ts(2026, 8, 20))
    assert fp in out["grandfathered"]
    assert out["pending_grandfather"] is False


def test_cards_have_health_signal():
    unpolled = {"id": 1, "name": "A", "error": None, "metrics": None, "health_issues": []}
    assert cards_have_health_signal([unpolled]) is False
    assert cards_have_health_signal([]) is False

    metrics_only = {
        "id": 1,
        "name": "A",
        "error": None,
        "metrics": {"cpu": 1},
        "health_issues": [],
    }
    assert cards_have_health_signal([metrics_only]) is True

    with_issues = {
        "id": 1,
        "name": "A",
        "error": None,
        "metrics": None,
        "health_issues": [_drive_issue()],
    }
    assert cards_have_health_signal([with_issues]) is True


def test_open_issue_fingerprints_for_baseline_live_ok():
    unpolled = {"id": 1, "name": "A", "error": None, "metrics": None, "health_issues": []}
    fps, live_ok = open_issue_fingerprints_for_baseline([unpolled])
    assert fps == set()
    assert live_ok is False
    fps, live_ok = open_issue_fingerprints_for_baseline([])
    assert fps == set()
    assert live_ok is False

    leftover = {
        "id": 1,
        "name": "A",
        "error": None,
        "metrics": {"cpu": 1},
        "health_issues": [_drive_issue()],
    }
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    fps, live_ok = open_issue_fingerprints_for_baseline([leftover])
    assert live_ok is True
    assert fp in fps

    healthy = {
        "id": 1,
        "name": "A",
        "error": None,
        "metrics": {"cpu": 1},
        "health_issues": [],
    }
    fps, live_ok = open_issue_fingerprints_for_baseline([healthy])
    assert live_ok is True
    assert fps == set()


def test_prepare_empty_issues_does_not_apply_baseline():
    state = empty_state()
    assert state["baseline_applied"] is False
    empty_card = {"id": 1, "name": "A", "error": None, "metrics": None, "health_issues": []}
    out = prepare_health_issue_limit(state, [empty_card], now=_ts(2026, 8, 14))
    assert out["baseline_applied"] is False
    assert out["grandfathered"] == []

    leftover = {
        "id": 1,
        "name": "A",
        "error": None,
        "metrics": {"cpu": 1},
        "health_issues": [_drive_issue()],
    }
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    out2 = prepare_health_issue_limit(out, [leftover], now=_ts(2026, 8, 14))
    assert out2["baseline_applied"] is True
    assert fp in out2["grandfathered"]


def test_prepare_healthy_polled_array_applies_empty_baseline():
    state = empty_state()
    healthy = {"id": 1, "name": "A", "error": None, "metrics": {"cpu": 1}, "health_issues": []}
    out = prepare_health_issue_limit(state, [healthy], now=_ts(2026, 8, 14))
    assert out["baseline_applied"] is True
    assert out["grandfathered"] == []
