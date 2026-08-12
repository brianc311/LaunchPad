from pathlib import Path

DASH = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
DIALOG = Path("launchpad/ui/health_alert_dialog.py").read_text(encoding="utf-8")
CARD = Path("launchpad/ui/card_widget.py").read_text(encoding="utf-8")


def test_health_alert_dialog_module():
    assert "class HealthAlertDialog" in DIALOG
    assert "HEALTH_ALERT_POLL_MS" in DIALOG
    assert "group_health_alerts" in DIALOG
    assert "Critical Health Alert" in DIALOG
    assert 'text="Suppress"' in DIALOG
    assert "Alarm off" in DIALOG
    assert "Alarm on" in DIALOG
    assert "on_alarm_toggle" in DIALOG
    assert 'f"Snooze {minutes}"' in DIALOG
    assert "enumerate((5, 10, 15, 20)" in DIALOG
    assert 'text="Close"' in DIALOG
    assert "resolve_health_alert_art" in DIALOG
    assert "CTkImage" in DIALOG


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
    assert "ensure_health_alert_art_dir()" in DASH
    assert "set_health_alert_overlay" in DASH


def test_card_widget_has_health_alert_overlay_contract():
    assert "def set_health_alert_overlay(" in CARD
    assert "def clear_health_alert_overlay(" in CARD
    assert 'text="Suppress"' in CARD
    assert 'f"Snooze {minutes}"' in CARD
    assert '"Alarm on" if alarm_muted else "Alarm off"' in CARD
    assert 'text="Close"' in CARD
