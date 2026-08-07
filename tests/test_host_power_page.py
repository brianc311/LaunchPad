from launchpad.host_power import HOST_POWER_HTML, HOST_POWER_PATH


def test_host_power_markers():
    assert HOST_POWER_PATH == "/host-power"
    assert "Host Power" in HOST_POWER_HTML
    assert "/api/host-power/cards" in HOST_POWER_HTML
    assert "/api/host-power/preview" in HOST_POWER_HTML
    assert "/api/host-power/run" in HOST_POWER_HTML
    assert "confirm" in HOST_POWER_HTML
    assert "card_id" in HOST_POWER_HTML
    assert "{{APP_VERSION}}" in HOST_POWER_HTML
