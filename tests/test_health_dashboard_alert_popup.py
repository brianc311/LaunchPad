from launchpad.health_server import DASHBOARD_HTML


def test_dashboard_has_health_alert_modal_markup():
    html = DASHBOARD_HTML
    for text in (
        "health-alert-modal",
        "Acknowledge",
        "Alarm off",
        "Pause 5 min",
        "Pause 10 min",
        "Pause 15 min",
        "Pause 20 min",
        "/api/health-alerts",
        "/api/health-alerts/acknowledge",
        "/api/health-alerts/pause",
        "/api/health-alerts/alarm",
    ):
        assert text in html


def test_dashboard_polls_health_alerts_on_interval():
    html = DASHBOARD_HTML
    assert "pollHealthAlerts" in html
    assert "30000" in html
