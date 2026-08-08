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


def test_host_power_script_js_strings_do_not_span_lines():
    """Python \"\"\" + JS \"\\n\" becomes a real newline and breaks loadCards()."""
    start = HOST_POWER_HTML.index("<script>")
    end = HOST_POWER_HTML.index("</script>", start)
    script = HOST_POWER_HTML[start:end]
    in_string = False
    escaped = False
    quote = ""
    for index, char in enumerate(script):
        if not in_string:
            if char in {'"', "'"}:
                in_string = True
                quote = char
            continue
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == quote:
            in_string = False
            quote = ""
            continue
        if char == "\n":
            snippet = script[max(0, index - 40) : index + 20]
            raise AssertionError(
                "JS string spans a newline; escape as \\\\n in the Python source. "
                f"Near: {snippet!r}"
            )
    assert "loadCards();" in script


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
