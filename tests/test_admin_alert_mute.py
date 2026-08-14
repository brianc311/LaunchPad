from pathlib import Path

from launchpad.health_alert_state import (
    HEALTH_ALERT_SETTING,
    dump_state,
    empty_state,
    fingerprints_for_card,
    grandfather_fingerprints,
    load_state,
    parse_active_issues_since,
    set_active_issues_since,
    set_alarm,
    set_limit_new_issues,
    set_pending_grandfather,
)


def test_admin_view_has_alerts_mute_control():
    source = Path("launchpad/ui/admin_view.py").read_text(encoding="utf-8")
    assert "Alerts" in source
    assert "set_alarm" in source
    assert "_persist_card_alert_mute" in source
    assert "_on_card_alerts_toggle" in source
    assert "card_alerts_switch" in source or "card_alerts_var" in source


def test_set_alarm_round_trip_in_setting_blob():
    state = empty_state()
    state = set_alarm(state, 42, True)
    blob = dump_state(state)
    loaded = load_state(blob)
    assert loaded["alarm_muted"].get("42") is True
    state = set_alarm(loaded, 42, False)
    assert "42" not in state["alarm_muted"]
    assert HEALTH_ALERT_SETTING == "health_alert_state"


def test_admin_branding_has_active_issues_since_controls():
    source = Path("launchpad/ui/admin_view.py").read_text(encoding="utf-8")
    assert "Limit to new issues" in source
    assert "Off shows all Active Issues and popups, including older ones." in source
    assert "Active issues since" in source
    assert "Save date" in source
    assert "_save_active_issues_since" in source
    assert "_on_limit_new_issues_toggle" in source
    assert "limit_new_issues_switch" in source or "limit_new_issues_var" in source


def test_save_date_while_on_grandfathers_open_fingerprints():
    card = {
        "id": 4,
        "name": "Array",
        "error": None,
        "health_issues": [
            {
                "severity": "warn",
                "category": "node",
                "message": "Node n1 is degraded",
                "server": "Array",
            }
        ],
    }
    fps = fingerprints_for_card(card)
    assert fps
    state = set_limit_new_issues(empty_state(), True)
    state = set_active_issues_since(state, "2026-08-14")
    state = grandfather_fingerprints(state, fps)
    blob = dump_state(state)
    loaded = load_state(blob)
    assert loaded["active_issues_since"] == "2026-08-14"
    assert loaded["limit_new_issues"] is True
    assert set(loaded["grandfathered"]) == fps


def test_invalid_date_parse_does_not_change_previous():
    assert parse_active_issues_since(" ") is None
    state = set_active_issues_since(empty_state(), "2026-08-14")
    assert parse_active_issues_since("abc") is None
    assert state["active_issues_since"] == "2026-08-14"


def test_pending_grandfather_flag_round_trip():
    state = set_pending_grandfather(empty_state(), True)
    loaded = load_state(dump_state(state))
    assert loaded["pending_grandfather"] is True
