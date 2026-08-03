from pathlib import Path

CARD = Path("launchpad/ui/card_widget.py").read_text(encoding="utf-8")
DASH = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")


def test_glowcard_has_set_capacity_alert():
    assert "def set_capacity_alert(" in CARD
    assert "CRIT" in CARD
    assert "WARN" in CARD


def test_dashboard_wires_capacity_alert_strip():
    assert "_refresh_capacity_alerts" in DASH
    assert "fleet_capacity_alert_summary" in DASH
    assert "CAPACITY_ALERT_POLL_MS" in DASH
    assert "set_capacity_alert" in DASH
