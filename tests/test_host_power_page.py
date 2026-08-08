from pathlib import Path

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


def test_host_power_precheck_markers():
    assert "/api/host-power/prechecks" in HOST_POWER_HTML
    assert "/api/host-power/precheck" in HOST_POWER_HTML
    assert 'id="prechecks"' in HOST_POWER_HTML
    assert 'data-letter="A"' in HOST_POWER_HTML
    assert 'data-letter="F"' in HOST_POWER_HTML
    assert "read-only" in HOST_POWER_HTML.lower() or "Precheck" in HOST_POWER_HTML


def test_dashboard_lists_host_power_tool():
    path = Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    text = path.read_text(encoding="utf-8")
    assert '"Host Power"' in text
    assert "_open_host_power" in text


def test_card_widget_supports_power_off_callback():
    path = Path(__file__).parents[1] / "launchpad" / "ui" / "card_widget.py"
    text = path.read_text(encoding="utf-8")
    assert "on_power_off" in text
    assert "Power off" in text


def test_dashboard_power_off_only_for_ssh_hadoop_linux():
    path = Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    text = path.read_text(encoding="utf-8")
    assert '"on_power_off"' in text
    assert (
        'if card.card_type == "ssh" and card.device_profile == "hadoop_linux"'
        in text
    )
