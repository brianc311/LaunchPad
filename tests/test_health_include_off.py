"""Health Dashboard can hide monitoring-off sites like Capacity Report."""

from launchpad.health_server import DASHBOARD_HTML


def test_health_dashboard_has_include_off_toggle():
    assert 'id="include-off-toggle"' in DASHBOARD_HTML
    assert "Include monitoring-off sites" in DASHBOARD_HTML
    assert "function visibleCards" in DASHBOARD_HTML
