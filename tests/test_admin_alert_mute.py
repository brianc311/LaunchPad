from pathlib import Path

from launchpad.health_alert_state import (
    HEALTH_ALERT_SETTING,
    dump_state,
    empty_state,
    load_state,
    set_alarm,
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
