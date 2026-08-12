from launchpad.health_server import DASHBOARD_HTML


def test_dashboard_has_health_alert_modal_markup():
    html = DASHBOARD_HTML
    for text in (
        "health-alert-modal",
        "Suppress",
        "Alarm off",
        "Alarm on",
        "isCardAlarmMuted",
        "toggleCurrentHealthAlarm",
        "alarm-on-btn",
        "Snooze…",
        'data-minutes="5">5 min',
        'data-minutes="10">10 min',
        'data-minutes="15">15 min',
        'data-minutes="20">20 min',
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


def test_dashboard_escape_advances_health_alert_queue():
    html = DASHBOARD_HTML
    assert "closeHealthAlertModal(true)" in html


def test_dashboard_applies_and_clears_health_alert_art_background():
    html = DASHBOARD_HTML
    assert "group.art_url" in html
    assert "healthAlertArtEl.style.backgroundImage" in html
    assert 'healthAlertArtEl.style.backgroundImage = ""' in html
