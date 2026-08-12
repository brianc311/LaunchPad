from launchpad.health_alert_state import (
    CONNECTIVITY_SENTINEL,
    acknowledge,
    collect_critical_candidates,
    empty_state,
    issue_fingerprint,
    list_popup_alerts,
    pause_card,
    prune_acknowledgements,
    set_alarm,
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
