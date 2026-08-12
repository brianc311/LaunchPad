from pathlib import Path

DASH = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
DIALOG = Path("launchpad/ui/health_alert_dialog.py").read_text(encoding="utf-8")


def test_health_alert_dialog_module():
    assert "class HealthAlertDialog" in DIALOG
    assert "HEALTH_ALERT_POLL_MS" in DIALOG
    assert "group_health_alerts" in DIALOG
    assert "Critical Health Alert" in DIALOG
    assert "Acknowledge" in DIALOG
    assert "Alarm off" in DIALOG
    assert "Alarm on" in DIALOG
    assert "on_alarm_toggle" in DIALOG
    assert 'f"Pause {minutes} min"' in DIALOG
    assert "enumerate((5, 10, 15, 20)" in DIALOG


def test_dashboard_wires_health_alert_poll():
    assert "_schedule_health_alert_poll" in DASH
    assert "_refresh_health_alerts" in DASH
    assert "HEALTH_ALERT_POLL_MS" in DASH
    assert "HealthAlertDialog" in DASH
    assert "get_health_server" in DASH
    assert "get_health_alerts" in DASH
    assert "play_health_alert_beep" in DASH
    assert "beeped_this_poll" in DASH
    assert "set_health_alarm_muted" in DASH
